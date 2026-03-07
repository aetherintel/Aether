"""
Lightweight Redis pub/sub event publisher.

Workers call publish_event() after writing results to Neo4j.
The FastAPI backend subscribes via an SSE endpoint and forwards
events to connected browser clients.

All events are published to a single channel: "aether:events"
on Redis db=7 (dedicated, isolated from RQ queues on db 0-6).
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
PUBSUB_DB = 7
PUBSUB_CHANNEL = "aether:events"

_publisher = None


def _get_publisher():
    global _publisher
    if _publisher is None:
        try:
            from redis import Redis
            _publisher = Redis(host=REDIS_HOST, port=REDIS_PORT, db=PUBSUB_DB)
        except Exception as e:
            logger.warning(f"Event publisher: Redis unavailable — events disabled ({e})")
    return _publisher


def publish_event(event_type: str, payload: dict) -> None:
    """
    Publish an event to all SSE subscribers.

    event_type examples:
      "message_status_changed" — a worker finished; status field updated
      "new_message"            — scraper stored a new message
      "new_channel"            — scraper stored a new channel

    payload should always include owner_id so the backend can route
    the event only to the correct user's SSE stream.
    """
    r = _get_publisher()
    if r is None:
        return
    try:
        message = json.dumps({"type": event_type, **payload})
        r.publish(PUBSUB_CHANNEL, message)
    except Exception as e:
        logger.debug(f"Event publish failed (non-critical): {e}")
