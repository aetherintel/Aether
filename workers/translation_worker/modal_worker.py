# workers/translation_worker/modal_worker.py
"""
Thin Modal-forwarding translation worker.
Receives RQ jobs, calls the Modal inference endpoint, writes results to Neo4j,
and chains an emotion job. No local model loaded.
"""
import asyncio
import os
import logging

import httpx
from neo4j import AsyncGraphDatabase
from aether_lib.queue_client import queue_client
from aether_lib.schemas.jobs import EmotionJobPayload
from aether_lib.utils.event_publisher import publish_event

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

MODAL_TRANSLATION_URL = os.getenv("MODAL_TRANSLATION_URL", "")
MODAL_TOKEN_ID = os.getenv("MODAL_TOKEN_ID", "")
MODAL_TOKEN_SECRET = os.getenv("MODAL_TOKEN_SECRET", "")

_HEADERS = {}
if MODAL_TOKEN_ID and MODAL_TOKEN_SECRET:
    _HEADERS = {"Modal-Key": MODAL_TOKEN_ID, "Modal-Secret": MODAL_TOKEN_SECRET}


def translate_and_update(
    message_id: str,
    original_text: str,
    source_language: str = "auto",
    owner_id: str = None,
    case_id: str = None,
    parent_job_id: str = None,
    chained_from: str = None,
    image_text: bool = False,
    audio_text: bool = False,
):
    """RQ job entry point — forwards to Modal, writes result to Neo4j."""
    logger.info(f"📤 Forwarding translation to Modal for {message_id}")

    try:
        resp = httpx.post(
            MODAL_TRANSLATION_URL,
            json={
                "text": original_text,
                "source_language": source_language,
                "target_language": "de",
            },
            headers=_HEADERS,
            timeout=120.0,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"❌ Modal translation failed for {message_id}: {e}")
        raise

    translated_text = resp.json().get("translated_text", "")
    logger.info(f"✅ Modal translation done for {message_id}")

    asyncio.run(_write_neo4j(message_id, translated_text, image_text, audio_text))

    if audio_text:
        status_key = 'audio_translation_status'
        text_key = 'audio_text_translated'
    elif image_text:
        status_key = 'image_translation_status'
        text_key = 'image_text_translated'
    else:
        status_key = 'translation_status'
        text_key = 'translated_text'

    publish_event("message_status_changed", {
        "message_id": message_id,
        "owner_id": owner_id,
        "updates": {status_key: "completed", text_key: translated_text},
    })
    return translated_text


async def _write_neo4j(message_id: str, translated_text: str, image_text: bool, audio_text: bool):
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if audio_text:
        cypher = """
        MATCH (m:Message {mid: $mid})
        SET m.audio_text_translated = $text,
            m.audio_translation_status = 'completed',
            m.audio_translated_at = datetime()
        """
    elif image_text:
        cypher = """
        MATCH (m:Message {mid: $mid})
        SET m.image_text_translated = $text,
            m.image_translation_status = 'completed',
            m.image_translated_at = datetime()
        """
    else:
        cypher = """
        MATCH (m:Message {mid: $mid})
        SET m.translated_text = $text,
            m.translation_status = 'completed',
            m.translated_at = datetime()
        """

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            await session.run(cypher, mid=message_id, text=translated_text)
        logger.info(f"✅ Neo4j translation updated for {message_id}")
    except Exception as e:
        logger.error(f"❌ Neo4j translation update failed for {message_id}: {e}")
        raise
    finally:
        await driver.close()
