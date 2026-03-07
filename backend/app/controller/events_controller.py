"""
Server-Sent Events endpoint.

Clients connect to GET /events/stream and receive a live stream of
JSON events whenever workers finish processing messages or the scraper
stores new data.  The stream is filtered server-side so each user only
receives events that belong to them.

Event shape (newline-delimited SSE):
    data: {"type": "message_status_changed", "message_id": "...", "updates": {...}}\n\n
    data: {"type": "new_message", "channel_id": "...", ...}\n\n
    data: {"type": "new_channel", "channel_id": "...", ...}\n\n
    data: {"type": "heartbeat"}\n\n      (every 30 s to keep the connection alive)
"""
import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis as AsyncRedis

from services.keycloak_service import decode_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
PUBSUB_DB = 7
PUBSUB_CHANNEL = "aether:events"
HEARTBEAT_INTERVAL = 30  # seconds


def _auth_from_query(token: Optional[str] = Query(default=None)) -> dict:
    """
    Validate a JWT passed as ?token=<jwt>.
    Used only by the SSE endpoint because EventSource cannot set headers.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return decode_token(token)


@router.get("/stream")
async def event_stream(user: dict = Depends(_auth_from_query)):
    """
    SSE stream — each authenticated user gets their own filtered view.
    The browser connects once and keeps the connection open.
    """
    owner_id = user["sub"]

    async def generate():
        redis: AsyncRedis | None = None
        pubsub = None
        heartbeat_task: asyncio.Task | None = None

        async def send_heartbeats(queue: asyncio.Queue):
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await queue.put("heartbeat")

        try:
            redis = AsyncRedis(host=REDIS_HOST, port=REDIS_PORT, db=PUBSUB_DB)
            pubsub = redis.pubsub()
            await pubsub.subscribe(PUBSUB_CHANNEL)

            # Queue to merge heartbeats and real events
            event_queue: asyncio.Queue[str] = asyncio.Queue()
            heartbeat_task = asyncio.create_task(send_heartbeats(event_queue))

            while True:
                # Non-blocking read from pub/sub
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if message and message.get("type") == "message":
                    try:
                        data = json.loads(message["data"])
                        event_owner = data.get("owner_id")
                        # Only forward events that belong to this user (or broadcast events with no owner)
                        if event_owner is None or str(event_owner) == str(owner_id):
                            yield f"data: {json.dumps(data)}\n\n"
                    except Exception:
                        pass

                # Drain the heartbeat queue without blocking
                while not event_queue.empty():
                    item = event_queue.get_nowait()
                    if item == "heartbeat":
                        yield 'data: {"type":"heartbeat"}\n\n'

                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"SSE stream error for user {owner_id}: {e}")
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
            if pubsub:
                try:
                    await pubsub.unsubscribe(PUBSUB_CHANNEL)
                    await pubsub.close()
                except Exception:
                    pass
            if redis:
                try:
                    await redis.aclose()
                except Exception:
                    pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables nginx buffering
        },
    )
