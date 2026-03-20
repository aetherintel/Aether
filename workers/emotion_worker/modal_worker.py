# workers/emotion_worker/modal_worker.py
"""
Thin Modal-forwarding emotion worker.
Receives RQ jobs, calls the Modal inference endpoint, writes results to Neo4j.
No local model loaded.
"""
import asyncio
import os
import logging

import httpx
from neo4j import AsyncGraphDatabase
from aether_lib.utils.event_publisher import publish_event

from .neo4j_utils import store_emotions_in_neo4j

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

MODAL_EMOTION_URL = os.getenv("MODAL_EMOTION_URL", "")
MODAL_TOKEN_ID = os.getenv("MODAL_TOKEN_ID", "")
MODAL_TOKEN_SECRET = os.getenv("MODAL_TOKEN_SECRET", "")

_HEADERS = {}
if MODAL_TOKEN_ID and MODAL_TOKEN_SECRET:
    _HEADERS = {"Modal-Key": MODAL_TOKEN_ID, "Modal-Secret": MODAL_TOKEN_SECRET}


def classify_emotion_job(
    message_id: str,
    text: str,
    threshold: float = 0.3,
    top_k: int = 3,
    owner_id: str = None,
    case_id: str = None,
    parent_job_id: str = None,
    chained_from: str = None,
):
    """RQ job entry point — forwards to Modal, writes result to Neo4j."""
    logger.info(f"📤 Forwarding emotion analysis to Modal for {message_id}")

    try:
        resp = httpx.post(
            MODAL_EMOTION_URL,
            json={"text": text, "threshold": threshold, "top_k": top_k},
            headers=_HEADERS,
            timeout=120.0,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"❌ Modal emotion failed for {message_id}: {e}")
        raise

    emotions = resp.json().get("emotions", [])
    logger.info(f"✅ Modal emotion done for {message_id}: {len(emotions)} labels")

    asyncio.run(_write_neo4j(message_id, emotions, owner_id))

    publish_event("message_status_changed", {
        "message_id": message_id,
        "owner_id": owner_id,
        "updates": {"emotion_status": "completed"},
    })

    return emotions


async def _write_neo4j(message_id: str, emotions: list, owner_id: str):
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        await store_emotions_in_neo4j(driver, message_id, emotions, owner_id)
    finally:
        await driver.close()
