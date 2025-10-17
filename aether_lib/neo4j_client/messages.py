# lib/neo4j/messages.py
"""
Neo4j operations for messages
"""
from .connection import get_driver, _with_constraints, get_owner_id
import logging
logger = logging.getLogger(__name__)

@_with_constraints
async def save_message_with_processing_status(
    channel_id,
    username,
    message,
    sender,
    media_path=None,
    media_type=None,
    original_language=None,
    translation_status='none',
    image_analysis_status='none',
    audio_transcription_status='none'
):
    """Save message with all processing status fields"""
    async with get_driver().session() as session:
        await session.execute_write(
            _save_message_tx,
            channel_id,
            username,
            message,
            sender,
            media_path,
            media_type,
            original_language,
            translation_status,
            image_analysis_status,
            audio_transcription_status
        )


async def _save_message_tx(
    tx,
    channel_id,
    username,
    message,
    sender,
    media_path,
    media_type,
    original_language,
    translation_status,
    image_analysis_status,
    audio_transcription_status
):
    """Transaction function for saving message"""
    cypher = """
    MERGE (ch:Channel {channel_id:$cid, owner_id:$owner})
    ON CREATE SET ch.username = $uname
    
    MERGE (m:Message {mid:$mid, owner_id:$owner})
    ON CREATE SET 
        m.date = datetime($date),
        m.original_text = $original_text,
        m.original_language = $original_language,
        m.media_type = $media_type,
        m.media_path = $media_path,
        m.translated_text = $translated_text,
        m.translation_status = $translation_status,
        m.image_analysis_status = $image_analysis_status,
        m.image_text = null,
        m.image_labels = null,
        m.audio_transcription_status = $audio_transcription_status,
        m.audio_transcript = null
    
    MERGE (ch)-[:HAS_MESSAGE]->(m)
    
    FOREACH (_ IN CASE WHEN $uid IS NOT NULL THEN [1] ELSE [] END |
        MERGE (u:User {user_id:$uid, owner_id:$owner})
        ON CREATE SET 
            u.first_name = $fname,
            u.last_name = $lname,
            u.username = $uusername
        MERGE (u)-[:SENT]->(m)
        MERGE (u)-[:PART_OF]->(ch)
    )
    
    FOREACH (_ IN CASE WHEN $reply_to IS NOT NULL THEN [1] ELSE [] END |
        MERGE (rm:Message {mid:$reply_to_mid, owner_id:$owner})
        MERGE (m)-[:REPLY_TO]->(rm)
    )
    """
    
    text = getattr(message, 'message', None) or getattr(message, 'caption', None) or ""
    translated_text = text if original_language == 'de' else None
    
    sender_id = getattr(sender, 'id', None) if sender else None
    first_name = getattr(sender, 'first_name', None) if sender else None
    last_name = getattr(sender, 'last_name', None) if sender else None
    sender_username = getattr(sender, 'username', None) if sender else None
    
    reply_to_mid = None
    if message.reply_to_msg_id:
        reply_to_mid = f"{channel_id}-{message.reply_to_msg_id}"
    
    owner = get_owner_id()
    
    await tx.run(
        cypher,
        owner=owner,
        cid=str(channel_id),
        uname=username,
        uid=sender_id,
        fname=first_name,
        lname=last_name,
        uusername=sender_username,
        mid=f"{channel_id}-{message.id}",
        date=message.date.isoformat(),
        original_text=text,
        original_language=original_language or 'unknown',
        translated_text=translated_text,
        translation_status=translation_status,
        media_type=media_type,
        media_path=media_path,
        image_analysis_status=image_analysis_status,
        audio_transcription_status=audio_transcription_status,
        reply_to=message.reply_to_msg_id,
        reply_to_mid=reply_to_mid,
    )



@_with_constraints
async def message_exists(channel_id, message_id):
    """Check if a message exists"""
    full_mid = f"{channel_id}-{message_id}"
    async with get_driver().session() as session:
        owner = get_owner_id()
        rec = await (
            await session.run(
                """
                MATCH (m:Message {mid:$mid, owner_id:$owner})
                RETURN count(m) > 0 AS exists
                """,
                mid=full_mid,
                owner=owner,
            )
        ).single()
        return rec and rec["exists"]


@_with_constraints
async def save_message_if_new(channel_id, username, message, sender, media_path=None):
    """Save message only if it doesn't exist (legacy function)"""
    if await message_exists(channel_id, message.id):
        print(f"[SKIP] Message {message.id} already exists in Neo4j")
        return
    
    # Use new function with default processing status
    await save_message_with_processing_status(
        channel_id=channel_id,
        username=username,
        message=message,
        sender=sender,
        media_path=media_path,
        media_type=None,
        original_language='de',
        translation_status='none',
        image_analysis_status='none',
        audio_transcription_status='none'
    )

import logging
logger = logging.getLogger(__name__)

async def update_message_audio_transcription(
    driver,
    message_id: str,
    audio_text: str = None,
    audio_text_translated: str = None,
    detected_language: str = None,
    media_type: str = None,
):
    """
    Update message node with audio transcription results.

    Args:
        driver: Neo4j driver instance
        message_id: Telegram message ID (mid)
        audio_text: Transcribed text from audio/video
        audio_text_translated: German translation of audio text
        detected_language: Detected language code (e.g., 'en', 'ru')
        media_type: 'audio' or 'video'

    Returns:
        bool: True if update successful, False otherwise
    """
    logger.info(f"💾 [UPDATE] Updating audio transcription for message_id={message_id}")
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (m:Message {mid: $mid})
                SET 
                    m.audio_text = coalesce($audio_text, m.audio_text),
                    m.audio_text_translated = coalesce($audio_text_translated, m.audio_text_translated),
                    m.audio_language = coalesce($detected_language, m.audio_language),
                    m.transcribed_media_type = coalesce($media_type, m.transcribed_media_type),
                    m.audio_transcribed = true,
                    m.audio_transcribed_at = datetime(),
                    m.audio_transcription_status = 'completed'
                RETURN m.mid AS mid
                """,
                mid=message_id,
                audio_text=audio_text,
                audio_text_translated=audio_text_translated,
                detected_language=detected_language,
                media_type=media_type,
            )

            record = await result.single()
            if record:
                logger.info(f"✅ [UPDATE] Updated audio transcription for {message_id}")
                if audio_text:
                    logger.info(f"   Transcribed: {len(audio_text)} chars")
                if detected_language:
                    logger.info(f"   Language: {detected_language}")
                if media_type:
                    logger.info(f"   Media type: {media_type}")
                return True
            else:
                logger.warning(f"⚠️ [UPDATE] Message {message_id} not found")
                return False

    except Exception as e:
        logger.error(f"❌ [UPDATE] Failed to update audio transcription for {message_id}: {e}")
        logger.exception("Full traceback:")
        return False

async def update_message_translation(
    driver,
    message_id: str,
    translated_text: str,
    image_text: bool = False,
    audio_text: bool = False
):
    """
    Update message with translated text
    
    Args:
        driver: Neo4j driver instance
        message_id: Message ID
        translated_text: Translated text
        image_text: If True, update image_text_translated; if False, update translated_text
        audio_text: If True, update audio_text_translated; if False, update translated_text
    Returns:
        bool: True if update successful
    """
    logger.info(f"🔍 [UPDATE] message_id={message_id}, image_text={image_text}, audio_text={audio_text}")

    try:
        if audio_text:
            field_name = "audio_text_translated"
        elif image_text:
            field_name = "image_text_translated"
        else:
            field_name = "translated_text"
        async with driver.session() as session:
            if image_text:
                # Update image text translation
                result = await session.run(
                    """
                    MATCH (m:Message {mid: $mid})
                    SET m.image_text_translated = $translated_text,
                        m.image_translation_status = 'completed',
                        m.image_translated_at = datetime()
                    RETURN m.mid as mid
                    """,
                    mid=message_id,
                    translated_text=translated_text
                )
            elif audio_text:
                # Update audio text translation
                result = await session.run(
                    """
                    MATCH (m:Message {mid: $mid})
                    SET m.audio_text_translated = $translated_text,
                        m.audio_translation_status = 'completed',
                        m.audio_translated_at = datetime()
                    RETURN m.mid as mid
                    """,
                    mid=message_id,
                    translated_text=translated_text
                )
            else:
                # Update regular message text translation
                result = await session.run(
                    """
                    MATCH (m:Message {mid: $mid})
                    SET m.translated_text = $translated_text,
                        m.translation_status = 'completed',
                        m.translated_at = datetime()
                    RETURN m.mid as mid
                    """,
                    mid=message_id,
                    translated_text=translated_text
                )
            
            record = await result.single()
            return bool(record)
            
    except Exception as e:
        logger.error(f"❌ Error updating message {message_id}: {e}")
        return False
    

async def mark_translation_failed(driver, message_id: str, error: str, owner_id: str):
    """Mark translation as failed"""
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Message {mid: $mid, owner_id: $owner})
            SET m.translation_status = 'failed',
                m.translation_error = $error
            RETURN m.mid as mid
            """,
            mid=message_id,
            error=error,
            owner=owner_id,
        )
        logger.info(f"❌ Marked message {message_id} as failed")

async def check_message_exists(driver, message_id: str):
    """Check if message exists"""
    async with driver.session() as session:
        owner_id = get_owner_id()
        result = await session.run(
            """
            MATCH (m:Message {mid: $mid, owner_id: $owner})
            RETURN m.mid as mid, 
                   m.original_text as original_text,
                   m.translation_status as status
            """,
            mid=message_id,
            owner=owner_id,
        )
        record = await result.single()
        
        if record:
            logger.info(f"✅ Found message: status={record.get('status')}")
            return True
        else:
            logger.warning(f"⚠️ Message NOT found")
            return False

# Add to aether_lib/neo4j_client/messages.py

async def update_message_image_analysis(driver, message_id: str, image_text: str = None, image_labels: list = None):
    """
    Update message with image analysis results
    
    Args:
        driver: Neo4j driver instance
        message_id: Full message ID (channel_id-message_id)
        image_text: Extracted text from OCR
        image_labels: List of detected objects with confidence scores
    
    Returns:
        bool: True if update successful, False otherwise
    """
    logger.info(f"💾 [UPDATE] Updating image analysis for message_id={message_id}")
    try:
        async with driver.session() as session:
            # Convert labels list to string for Neo4j storage
            labels_str = None
            if image_labels:
                labels_str = ", ".join([
                    f"{obj['label']} ({obj['confidence']:.2f})" 
                    for obj in image_labels
                ])
            
            result = await session.run(
                """
                MATCH (m:Message {mid: $mid})
                SET m.image_text = $image_text,
                    m.image_labels = $labels_str,
                    m.image_analysis_status = 'completed'
                RETURN m.mid AS mid
                """,
                mid=message_id,
                image_text=image_text,
                labels_str=labels_str
            )
            
            record = await result.single()
            if record:
                logger.info(f"✅ [UPDATE] Updated message {record['mid']}")
                return True
            else:
                logger.warning(f"⚠️ [UPDATE] Message {message_id} not found")
                return False
                
    except Exception as e:
        logger.error(f"❌ [UPDATE] Failed to update image analysis: {e}")
        logger.exception("Full traceback:")
        return False


async def get_messages_pending_image_analysis(owner_id: str, limit: int = 100):
    """
    Get messages that have images but haven't been analyzed yet
    
    Args:
        owner_id: Owner ID for multi-tenancy
        limit: Maximum number of messages to return
    
    Returns:
        list: Messages with media_type='photo' and image_analysis_status='none'
    """
    async with get_driver().session() as session:
        result = await session.run(
            """
            MATCH (m:Message {owner_id: $owner_id})
            WHERE m.media_type = 'photo'
              AND m.image_analysis_status = 'none'
              AND m.media_path IS NOT NULL
            RETURN m.mid AS message_id,
                   m.media_path AS image_path,
                   m.date AS date
            ORDER BY m.date DESC
            LIMIT $limit
            """,
            owner_id=owner_id,
            limit=limit
        )
        
        messages = []
        async for record in result:
            messages.append({
                "message_id": record["message_id"],
                "image_path": record["image_path"],
                "date": record["date"]
            })
        
        return messages
    
# Add to aether_lib/neo4j_client/messages.py

async def update_message_image_analysis(driver, message_id: str, image_text: str = None, detected_language: str = None):
    """
    Update message with OCR results (no object detection)
    
    Args:
        driver: Neo4j driver instance
        message_id: Full message ID (channel_id-message_id)
        image_text: Extracted text from OCR
        detected_language: Detected language of the extracted text
    
    Returns:
        bool: True if update successful, False otherwise
    """
    logger.info(f"💾 [UPDATE] Updating image analysis for message_id={message_id}")
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (m:Message {mid: $mid})
                SET m.image_text = $image_text,
                    m.image_labels = null,
                    m.image_analysis_status = 'completed',
                    m.image_detected_language = $detected_language
                RETURN m.mid AS mid
                """,
                mid=message_id,
                image_text=image_text,
                detected_language=detected_language
            )
            
            record = await result.single()
            if record:
                logger.info(f"✅ [UPDATE] Updated message {record['mid']}")
                return True
            else:
                logger.warning(f"⚠️ [UPDATE] Message {message_id} not found")
                return False
                
    except Exception as e:
        logger.error(f"❌ [UPDATE] Failed to update image analysis: {e}")
        logger.exception("Full traceback:")
        return False


async def get_messages_pending_image_analysis(owner_id: str, limit: int = 100):
    """
    Get messages that have images but haven't been analyzed yet
    
    Args:
        owner_id: Owner ID for multi-tenancy
        limit: Maximum number of messages to return
    
    Returns:
        list: Messages with media_type='photo' and image_analysis_status='none'
    """
    async with get_driver().session() as session:
        result = await session.run(
            """
            MATCH (m:Message {owner_id: $owner_id})
            WHERE m.media_type = 'photo'
              AND m.image_analysis_status = 'none'
              AND m.media_path IS NOT NULL
            RETURN m.mid AS message_id,
                   m.media_path AS image_path,
                   m.date AS date
            ORDER BY m.date DESC
            LIMIT $limit
            """,
            owner_id=owner_id,
            limit=limit
        )
        
        messages = []
        async for record in result:
            messages.append({
                "message_id": record["message_id"],
                "image_path": record["image_path"],
                "date": record["date"]
            })
        
        return messages