import asyncio
from pathlib import Path
import os
import time
import requests
from langdetect import detect, LangDetectException
from telethon import events
from .telegram_client import get_client, login
from aether_lib.neo4j_client.messages import save_message_with_processing_status
from aether_lib.neo4j_client.channels import is_scraped, mark_scraped
from aether_lib.queue_client.queue_client import queue_client
from aether_lib.schemas.jobs import (
    TranslationJobPayload,
    ImageJobPayload,
    AudioJobPayload,
    EmotionJobPayload,
    ClassificationJobPayload,
    GeolocationJobPayload,
)
from .utils import download_media_to_path, extract_invite_links, generate_media_path, get_media_type

# Configuration
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))
MESSAGE_BATCH_SIZE = int(os.getenv("MESSAGE_BATCH_SIZE", "500"))
MESSAGE_BATCH_DELAY = float(os.getenv("MESSAGE_BATCH_DELAY", "0.05"))
MAX_PARALLEL_SCRAPERS = int(os.getenv("MAX_PARALLEL_SCRAPERS", "4"))

OWNER_ID = os.getenv("OWNER_ID", "unknown")

ENABLE_TRANSLATION = os.getenv('ENABLE_TRANSLATION', '1') == '1'
ENABLE_IMAGE_ANALYSIS = os.getenv('ENABLE_IMAGE_ANALYSIS', '1') == '1'
ENABLE_AUDIO_TRANSCRIPTION = os.getenv('ENABLE_AUDIO_TRANSCRIPTION', '1') == '1'
ENABLE_EMOTION_ANALYSIS = os.getenv('ENABLE_EMOTION_ANALYSIS', '0') == '1'
ENABLE_LABEL_CLASSIFIER = os.getenv('ENABLE_LABEL_CLASSIFIER', '0') == '1'
ENABLE_GEOLOCATION_EXTRACTION = os.getenv('ENABLE_GEOLOCATION_EXTRACTION', '0') == '1'

# Translation Configuration
SUPPORTED_TRANSLATION_LANGUAGES = ['ru', 'ar', 'trk', 'en']

# Global state for parallel processing
processing_channels = set()
found_channels_queue = asyncio.Queue()
scraper_semaphore = asyncio.Semaphore(MAX_PARALLEL_SCRAPERS)
all_seen_channels = set()

# ============================================================================
#  TRANSLATION HELPERS
# ============================================================================

def detect_language(text: str) -> str:
    """Detect language of text, returns 'de' if detection fails"""
    if not text or len(text.strip()) < 10:
        return 'de'
    
    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        print(f"[LANG] Could not detect language, assuming German")
        return 'de'

def needs_translation(text: str) -> tuple[bool, str]:
    """
    Check if text needs translation
    Returns: (needs_translation, detected_language, to_english)
    """
    detected_lang = detect_language(text)
    
    # Already German
    if detected_lang == 'de':
        # translate to english for better NLP results
        return False, 'de'
    
    # Supported language - needs translation
    if detected_lang in SUPPORTED_TRANSLATION_LANGUAGES:
        print(f"[LANG] Text needs translation: {detected_lang} -> de")
        return True, detected_lang
    
    # Unsupported language - store as-is
    print(f"[LANG] Unsupported language {detected_lang}, storing original")
    return False, detected_lang

# ============================================================================
#  MESSAGE PROCESSING (Updated with Translation)
# ============================================================================

# Updated process_message function with audio transcription support

async def process_message(msg, username, found_channels, recursive=False, case_id=None, owner_id=None):
    """Process a single message: save it, download media, queue translation/transcription, find channels"""
    try:
        # Skip service messages
        if hasattr(msg, 'action') and msg.action is not None:
            return
            
        # Rate limiting
        await asyncio.sleep(RATE_LIMIT_DELAY)
        
        # Get sender
        sender = await msg.get_sender()
        
        # Extract text
        text = msg.message or ""
        
        # Analyze text for translation
        needs_trans = False
        detected_lang = None
        translation_status = 'none'
        geolocation_status = 'none'
        image_analysis_status = 'none'
        audio_transcription_status = 'none'

        if text:
            if len(text) >= 10 and ENABLE_TRANSLATION:
                needs_trans, detected_lang = needs_translation(text)
                translation_status = 'pending' if needs_trans else 'none'
            # Geolocation extraction status
            if len(text) >= 10 and ENABLE_GEOLOCATION_EXTRACTION:
                geolocation_status = 'pending'
                # Queue geolocation extraction
                geolocation_payload = GeolocationJobPayload(
                    message_id=f"{msg.chat_id}-{msg.id}",
                    text=text,
                    owner_id=owner_id,
                    case_id=case_id
                )
                job_id = queue_client.enqueue_geolocation(geolocation_payload)
        
        # Handle media download and processing
        media_path = None
        media_type = None
        
        if msg.media:
            media_type = get_media_type(msg.media)
            
            # Check if media should be downloaded
            if media_type in ["photo", "video", "document", "audio"]:
                media_path = generate_media_path(username, msg.id, media_type, msg)
                
                if media_path:
                    try:
                        os.makedirs(os.path.dirname(media_path), exist_ok=True)
                        if not os.path.exists(media_path):
                            print(f"[DOWNLOAD] {username}: Downloading media for message {msg.id}")
                            await download_media_to_path(username, msg, get_client(), media_path)
                        
                        # Build full message ID for processing
                        full_message_id = f"{msg.chat_id}-{msg.id}"
                        
                        # Process based on media type
                        
                        # 1. IMAGE PROCESSING (existing)
                        if media_type == "photo" and os.path.exists(media_path) and ENABLE_IMAGE_ANALYSIS:
                            image_analysis_status = 'pending'

                            image_payload = ImageJobPayload(
                                message_id=full_message_id,
                                image_path=media_path,
                                owner_id=owner_id,
                                case_id=case_id,
                                extract_text=True,
                                detect_objects=False,
                                translate_extracted_text=True
                            )
                            job_id = queue_client.enqueue_image_analysis(image_payload)
                            print(f"[QUEUE] Image analysis queued for {full_message_id}, job: {job_id}")
                        
                        # 2. AUDIO PROCESSING (new)
                        elif media_type == "audio" and os.path.exists(media_path) and ENABLE_AUDIO_TRANSCRIPTION:
                            audio_transcription_status = 'pending'

                            audio_payload = AudioJobPayload(
                                message_id=full_message_id,
                                audio_path=media_path,
                                owner_id=owner_id,
                                case_id=case_id,
                                translate_transcription=True
                            )
                            job_id = queue_client.enqueue_audio_transcription(audio_payload)
                            print(f"[QUEUE] Audio transcription queued for {full_message_id}, job: {job_id}")
                        
                        # 3. VIDEO PROCESSING (check for audio track)
                        elif media_type == "video" and os.path.exists(media_path) and ENABLE_AUDIO_TRANSCRIPTION:
                            # Queue for audio extraction and transcription
                            # Videos often contain speech that needs transcription
                            audio_transcription_status = 'pending'

                            audio_payload = AudioJobPayload(
                                message_id=full_message_id,
                                audio_path=media_path,
                                owner_id=owner_id,
                                case_id=case_id,
                                translate_transcription=True
                            )
                            job_id = queue_client.enqueue_audio_transcription(audio_payload)
                            print(f"[QUEUE] Video audio extraction queued for {full_message_id}, job: {job_id}")
                        
                        # 4. DOCUMENT PROCESSING (check if it's audio/video file)
                        elif media_type == "document" and os.path.exists(media_path):
                            # Check if document is actually an audio/video file
                            if await is_audio_video_document(msg, media_path) and ENABLE_AUDIO_TRANSCRIPTION:
                                audio_transcription_status = 'pending'

                                # Detect if it's audio or video based on mime type or extension
                                doc_media_type = await get_document_media_type(msg, media_path)

                                audio_payload = AudioJobPayload(
                                    message_id=full_message_id,
                                    audio_path=media_path,
                                    owner_id=owner_id,
                                    case_id=case_id,
                                    translate_transcription=True
                                )
                                job_id = queue_client.enqueue_audio_transcription(audio_payload)
                                print(f"[QUEUE] Document {doc_media_type} transcription queued for {full_message_id}")
                            
                    except Exception as e:
                        print(f"[ERROR] {username}: Failed to download/process media for message {msg.id}: {e}")
            
            # 5. VOICE MESSAGES (Telegram voice notes)
            # Voice messages appear as audio with is_voice flag
            elif hasattr(msg.media, 'document') and msg.media.document:
                doc = msg.media.document
                # Check for voice attribute
                if hasattr(doc, 'attributes'):
                    for attr in doc.attributes:
                        if hasattr(attr, 'voice') and attr.voice:
                            # This is a voice message
                            media_path = generate_media_path(username, msg.id, "voice", msg)
                            if media_path:
                                try:
                                    os.makedirs(os.path.dirname(media_path), exist_ok=True)
                                    if not os.path.exists(media_path):
                                        print(f"[DOWNLOAD] {username}: Downloading voice message {msg.id}")
                                        await download_media_to_path(username, msg, get_client(), media_path)
                                    
                                    if os.path.exists(media_path) and ENABLE_AUDIO_TRANSCRIPTION:
                                        full_message_id = f"{msg.chat_id}-{msg.id}"
                                        audio_transcription_status = 'pending'

                                        audio_payload = AudioJobPayload(
                                            message_id=full_message_id,
                                            audio_path=media_path,
                                            owner_id=owner_id,
                                            case_id=case_id,
                                            translate_transcription=True
                                        )
                                        job_id = queue_client.enqueue_audio_transcription(audio_payload)
                                        print(f"[QUEUE] Voice transcription queued for {full_message_id}")
                                        media_type = "voice"  # Store as voice type
                                except Exception as e:
                                    print(f"[ERROR] Failed to process voice message: {e}")
        
        # Build full message ID
        full_message_id = f"{msg.chat_id}-{msg.id}"
        
        # Save message to Neo4j with processing status
        await save_message_with_processing_status(
            owner_id=owner_id,
            channel_id=msg.chat_id,
            username=username,
            message=msg,
            sender=sender,
            media_path=media_path,
            media_type=media_type,
            original_language=detected_lang,
            translation_status=translation_status,
            image_analysis_status=image_analysis_status,
            audio_transcription_status=audio_transcription_status,
            geolocation_status=geolocation_status
        )

        print(f"[SAVE] {username}: Saved message {msg.id} (lang: {detected_lang}, translation: {translation_status}, audio: {audio_transcription_status}, geolocation: {geolocation_status})")

        # Queue text translation if needed (existing logic)
        if needs_trans and ENABLE_TRANSLATION:
            translation_payload = TranslationJobPayload(
                message_id=full_message_id,
                original_text=text,
                source_language=detected_lang,
                owner_id=owner_id,
                case_id=case_id
            )
            job_id = queue_client.enqueue_translation(translation_payload)
        else:
            if text and len(text.strip()) > 10 and ENABLE_EMOTION_ANALYSIS:  # Only if meaningful text
                print(f"🎭 Text is German, triggering emotion analysis directly")
                emotion_payload = EmotionJobPayload(
                    message_id=f"{msg.chat_id}-{msg.id}",
                    text=text,
                    owner_id=owner_id,
                    case_id=case_id
                )
                queue_client.enqueue_emotion(emotion_payload)
            if text and len(text.strip()) > 10 and ENABLE_LABEL_CLASSIFIER:
                print(f"🏷️ Text is German, triggering label classification directly")
                classification_payload = ClassificationJobPayload(
                    message_id=f"{msg.chat_id}-{msg.id}",
                    text=text,
                    owner_id=owner_id,
                    case_id=case_id
                )
                queue_client.enqueue_classification(classification_payload)
        # Extract invite links for recursive processing (existing logic)
        if recursive and text:
            links = extract_invite_links([text])
            for link in links:
                normalized_link = link.lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '').strip()
                
                if normalized_link == username.lower():
                    continue
                    
                if normalized_link not in all_seen_channels:
                    all_seen_channels.add(normalized_link)
                    found_channels.add(normalized_link)
                    print(f"[FOUND] {username}: New channel from message {msg.id}: {normalized_link}")
                    await found_channels_queue.put((normalized_link, username))
                else:
                    print(f"[DUPLICATE] {username}: Channel {normalized_link} already seen, skipping")
        
    except Exception as e:
        print(f"[ERROR] {username}: Failed to process message {msg.id}: {e}")


# Helper functions for audio/video detection

async def is_audio_video_document(msg, file_path: str) -> bool:
    """Check if a document is actually an audio or video file"""
    # Check by MIME type
    if hasattr(msg.media, 'document') and msg.media.document:
        doc = msg.media.document
        mime_type = getattr(doc, 'mime_type', '').lower()
        
        # Audio MIME types
        if mime_type.startswith('audio/'):
            return True
        # Video MIME types  
        if mime_type.startswith('video/'):
            return True
    
    # Check by file extension as fallback
    if file_path:
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        
        audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.opus', '.wma', '.aac', '.oga'}
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'}
        
        if ext in audio_extensions or ext in video_extensions:
            return True
    
    return False


async def get_document_media_type(msg, file_path: str) -> str:
    """Determine if document is audio or video"""
    # Check MIME type first
    if hasattr(msg.media, 'document') and msg.media.document:
        doc = msg.media.document
        mime_type = getattr(doc, 'mime_type', '').lower()
        
        if mime_type.startswith('audio/'):
            return "audio"
        elif mime_type.startswith('video/'):
            return "video"
    
    # Check file extension
    if file_path:
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        
        audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.opus', '.wma', '.aac', '.oga'}
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'}
        
        if ext in audio_extensions:
            return "audio"
        elif ext in video_extensions:
            return "video"
    
    # Default to audio if unsure
    return "audio"

# ============================================================================
#  EXISTING SCRAPER LOGIC (Keep as is, just updated process_message call)
# ============================================================================

async def get_entity_safe(identifier):
    """Safely get a Telegram entity"""
    try:
        if isinstance(identifier, str) and (identifier.lstrip('-').isdigit()):
            chat_id = int(identifier)
            entity = await get_client().get_entity(chat_id)
        else:
            entity = await get_client().get_entity(identifier)
        
        clean_name = getattr(entity, 'username', None) or str(entity.id)
        print(f"[ENTITY] Resolved {identifier} to: {clean_name}")
        return entity, clean_name
    except Exception as e:
        print(f"[ERROR] Could not resolve entity '{identifier}': {e}")
        return None, None

async def scrape_channel_complete(channel_name, recursive=False, case_id=None, owner_id=None):
    """Scrape a channel completely: all messages, media, and find new channels"""
    async with scraper_semaphore:
        try:
            entity, clean_name = await get_entity_safe(channel_name)
            if not entity:
                return set()
                
            if await is_scraped(clean_name):
                print(f"[SKIP] {clean_name} already scraped")
                return set()
            
            print(f"[SCRAPE] Starting complete scrape of {clean_name}")
            
            found_channels = set()
            message_count = 0
            
            # Process ALL messages in the channel
            async for msg in get_client().iter_messages(entity, reverse=True):
                if not msg.message and not msg.media:
                    continue
                    
                message_count += 1
                
                # Process message with translation pipeline
                await process_message(msg, clean_name, found_channels, recursive, case_id, owner_id=owner_id)
                
                if message_count % MESSAGE_BATCH_SIZE == 0:
                    await asyncio.sleep(MESSAGE_BATCH_DELAY)
                
                if message_count % 100 == 0:
                    print(f"[SCRAPE] {clean_name}: Processed {message_count} messages")
                    await asyncio.sleep(0.1)
            
            await mark_scraped(clean_name)
            print(f"[SCRAPE] ✅ {clean_name}: Completed scrape with {message_count} messages")
            
            if recursive and found_channels:
                print(f"[SCRAPE] {clean_name}: Found {len(found_channels)} new channels total")
            
            return found_channels
            
        except Exception as e:
            print(f"[ERROR] Failed to scrape channel {channel_name}: {e}")
            return set()

async def try_join_channel(channel_name):
    """Try to join a channel by invite link"""
    try:
        print(f"[JOIN] Trying to join: {channel_name}")
        
        if '+' in channel_name:
            slug = channel_name.split('+')[-1]
            from telethon.tl.functions.messages import ImportChatInviteRequest
            result = await get_client()(ImportChatInviteRequest(slug))
            joined = result.chats[0]
            username = getattr(joined, 'username', None) or str(joined.id)
            print(f"[JOIN] ✅ Joined via invite: {username}")
            return username
        else:
            entity, clean_name = await get_entity_safe(channel_name)
            if entity:
                print(f"[JOIN] ✅ Access to channel: {clean_name}")
                return clean_name
            
    except Exception as e:
        print(f"[JOIN] ❌ Failed to join {channel_name}: {e}")
        
    return None

async def channel_processor(recursive=False, case_id=None, owner_id=None):
    """Process channels from the queue in parallel"""
    while True:
        try:
            queue_item = await found_channels_queue.get()
            
            if isinstance(queue_item, tuple):
                channel_name, source_channel = queue_item
            else:
                channel_name = queue_item
                source_channel = None
            
            print(f"[DEBUG] Processing: {channel_name}, source: {source_channel}")
            
            if channel_name in processing_channels:
                print(f"[SKIP] {channel_name} already being processed")
                found_channels_queue.task_done()
                continue
            
            processing_channels.add(channel_name)
            
            try:
                actual_name = await try_join_channel(channel_name)
                if actual_name:
                    if source_channel:
                        try:
                            from aether_lib.neo4j_client.channels import write_recommendations
                            print(f"[RECOMMEND] Creating relationship: {source_channel} -> {actual_name}")
                            
                            rec_data = [{
                                "id": actual_name,
                                "username": actual_name,
                                "title": None
                            }]
                            
                            await write_recommendations(source_channel, rec_data)
                            print(f"[RECOMMEND] ✅ Created relationship: {source_channel} -> {actual_name}")
                            
                        except Exception as e:
                            print(f"[ERROR] Failed to create recommendation: {source_channel} -> {actual_name}: {e}")
                    else:
                        print(f"[DEBUG] No source channel for {actual_name}, skipping recommendation")
                    
                    # Scrape the channel with case_id
                    await scrape_channel_complete(actual_name, recursive, case_id, owner_id=owner_id)
                
            finally:
                processing_channels.discard(channel_name)
                found_channels_queue.task_done()
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ERROR] Channel processor error: {e}")
            await asyncio.sleep(5)

async def run_parallel_scraper(channels, recursive=False, case_id=None, owner_id=None):
    """Parallel scraper with workers"""
    await login()
    
    print(f"[START] Parallel scraper: channels={channels}, recursive={recursive}, case_id={case_id}")
    print(f"[START] Max parallel scrapers: {MAX_PARALLEL_SCRAPERS}")
    print(f"[START] Translation enabled for: {SUPPORTED_TRANSLATION_LANGUAGES}")
    
    for ch in channels:
        normalized_ch = ch.lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '').strip()
        all_seen_channels.add(normalized_ch)
        await found_channels_queue.put((normalized_ch, None))
    
    async with get_client():
        # Start channel processor workers
        workers = []
        for i in range(MAX_PARALLEL_SCRAPERS):
            worker = asyncio.create_task(channel_processor(recursive, case_id, owner_id=owner_id))
            workers.append(worker)
        
        # Monitor progress
        while True:
            if found_channels_queue.empty() and not processing_channels:
                print(f"[COMPLETE] ✅ All channels processed!")
                break
            
            current_processing = len(processing_channels)
            queue_size = found_channels_queue.qsize()
            total_seen = len(all_seen_channels)
            
            if current_processing > 0 or queue_size > 0:
                print(f"[STATUS] Processing: {current_processing}, Queue: {queue_size}, Total seen: {total_seen}")
            
            await asyncio.sleep(5)
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)
        
        print(f"[COMPLETE] ✅ Parallel scraping finished")

async def run_live_monitor(channels, case_id=None, owner_id=None):
    """Simple live monitor for channels with translation"""
    await login()
    
    print(f"[LIVE] Starting live monitor for {len(channels)} channels")
    
    resolved_entities = []
    for ch in channels:
        entity, clean_name = await get_entity_safe(ch)
        if entity:
            resolved_entities.append((entity, clean_name))
    
    if not resolved_entities:
        print("[LIVE] No valid channels to monitor")
        return
    
    entities = [entity for entity, _ in resolved_entities]
    
    @get_client().on(events.NewMessage(chats=entities))
    async def handle_new_message(event):
        try:
            channel_name = None
            for entity, name in resolved_entities:
                if entity.id == event.chat_id:
                    channel_name = name
                    break
            
            if not channel_name:
                return
                
            print(f"[LIVE] 📩 New message in {channel_name}")
            
            # Process the message with translation pipeline
            await process_message(event.message, channel_name, set(), False, case_id, owner_id=owner_id)
            
        except Exception as e:
            print(f"[LIVE] Error processing message: {e}")
    
    print("[LIVE] ✅ Live monitor active (with translation)")
    
    async with get_client():
        while True:
            await asyncio.sleep(60)
            print("[LIVE] Monitor running...")

# Main entry points
async def run_scraper(channels, _session_name, recursive=False, skip_history=False, case_id=None, owner_id=None):
    """Main scraper entry point with translation support"""
    if skip_history:
        await run_live_monitor(channels, case_id, owner_id=owner_id)
    else:
        await run_parallel_scraper(channels, recursive, case_id, owner_id=owner_id)
        print("[TRANSITION] Scraping complete, starting live monitor...")
        await run_live_monitor(channels, case_id, owner_id=owner_id)

async def run_live_listener_only(channels, case_id=None, owner_id=None):
    """Only live listener with translation"""
    await run_live_monitor(channels, case_id, owner_id=owner_id)