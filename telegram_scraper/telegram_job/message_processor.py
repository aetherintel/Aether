import asyncio
import os
from .utils import download_media_to_path, extract_invite_links, generate_media_path, get_media_type
from .telegram_client import get_client
from langdetect import detect, LangDetectException
from aether_lib.neo4j_client.messages import save_message_with_processing_status
from aether_lib.queue_client.queue_client import queue_client
from aether_lib.utils.event_publisher import publish_event
from aether_lib.schemas.jobs import (
    TranslationJobPayload,
    ImageJobPayload,
    AudioJobPayload,
    EmotionJobPayload,
    ClassificationJobPayload,
    GeolocationJobPayload,
)

# Configuration defaults
SUPPORTED_TRANSLATION_LANGUAGES = ['ru', 'ar', 'trk', 'en']

def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 10: return 'de'
    try: return detect(text)
    except LangDetectException: return 'de'

def needs_translation(text: str) -> tuple[bool, str]:
    detected_lang = detect_language(text)
    if detected_lang == 'de' or detected_lang not in SUPPORTED_TRANSLATION_LANGUAGES:
        return False, detected_lang
    return True, detected_lang

async def is_audio_video_document(msg, file_path: str) -> bool:
    if hasattr(msg.media, 'document') and msg.media.document:
        mime_type = getattr(msg.media.document, 'mime_type', '').lower()
        if mime_type.startswith(('audio/', 'video/')): return True
    if file_path:
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        if ext in {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.opus', '.wma', '.aac', '.oga',
                   '.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'}:
            return True
    return False

async def get_document_media_type(msg, file_path: str) -> str:
    if hasattr(msg.media, 'document') and msg.media.document:
        mime_type = getattr(msg.media.document, 'mime_type', '').lower()
        if mime_type.startswith('video/'): return "video"
    if file_path:
        from pathlib import Path
        if Path(file_path).suffix.lower() in {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'}:
            return "video"
    return "audio"

async def process_message(msg, username, found_channels, all_seen_channels, found_channels_queue, config, recursive=False, case_id=None, owner_id=None):
    try:
        if hasattr(msg, 'action') and msg.action is not None: return
        await asyncio.sleep(config.get('RATE_LIMIT_DELAY', 1.0))
        
        sender = await msg.get_sender()
        if sender:
            sender_id = sender.id
            if getattr(sender, 'username', None): sender_username = sender.username
            elif hasattr(sender, 'first_name'):
                parts = [sender.first_name]
                if getattr(sender, 'last_name', None): parts.append(sender.last_name)
                sender_username = ' '.join(parts)
            else: sender_username = f"user_{sender_id}"
        else:
            sender_username = "unknown"
            sender_id = msg.from_id.user_id if msg.from_id else None
        
        text = msg.message or ""
        needs_trans, detected_lang = False, None
        translation_status = geolocation_status = image_analysis_status = audio_transcription_status = 'none'

        if text:
            if len(text) >= 10 and config.get('ENABLE_TRANSLATION'):
                needs_trans, detected_lang = needs_translation(text)
                translation_status = 'pending' if needs_trans else 'none'
            if len(text) >= 10 and config.get('ENABLE_GEOLOCATION_EXTRACTION'):
                geolocation_status = 'pending'
                queue_client.enqueue_geolocation(GeolocationJobPayload(message_id=f"{msg.chat_id}-{msg.id}", text=text, owner_id=owner_id, case_id=case_id))
        
        media_path = media_type = None
        if msg.media:
            media_type = get_media_type(msg.media)
            if media_type in ["photo", "video", "document", "audio"]:
                media_path = generate_media_path(username, msg.id, media_type, msg)
                if media_path:
                    try:
                        os.makedirs(os.path.dirname(media_path), exist_ok=True)
                        if not os.path.exists(media_path):
                            await download_media_to_path(username, msg, get_client(), media_path)
                        
                        full_id = f"{msg.chat_id}-{msg.id}"
                        if media_type == "photo" and os.path.exists(media_path) and config.get('ENABLE_IMAGE_ANALYSIS'):
                            image_analysis_status = 'pending'
                            queue_client.enqueue_image_analysis(ImageJobPayload(message_id=full_id, image_path=media_path, owner_id=owner_id, case_id=case_id, extract_text=True, detect_objects=False, translate_extracted_text=True, ocr_languages=config.get('OCR_LANGUAGES', ['latin'])))
                        elif media_type in ["audio", "video"] and os.path.exists(media_path) and config.get('ENABLE_AUDIO_TRANSCRIPTION'):
                            audio_transcription_status = 'pending'
                            queue_client.enqueue_audio_transcription(AudioJobPayload(message_id=full_id, audio_path=media_path, owner_id=owner_id, case_id=case_id, translate_transcription=True))
                        elif media_type == "document" and os.path.exists(media_path) and await is_audio_video_document(msg, media_path) and config.get('ENABLE_AUDIO_TRANSCRIPTION'):
                            audio_transcription_status = 'pending'
                            queue_client.enqueue_audio_transcription(AudioJobPayload(message_id=full_id, audio_path=media_path, owner_id=owner_id, case_id=case_id, translate_transcription=True))
                    except Exception as e:
                        print(f"[ERROR] {username}: Media processing failed for {msg.id}: {e}")
            elif hasattr(msg.media, 'document') and any(hasattr(a, 'voice') and a.voice for a in getattr(msg.media.document, 'attributes', [])):
                media_path = generate_media_path(username, msg.id, "voice", msg)
                if media_path:
                    try:
                        os.makedirs(os.path.dirname(media_path), exist_ok=True)
                        if not os.path.exists(media_path):
                            await download_media_to_path(username, msg, get_client(), media_path)
                        if os.path.exists(media_path) and config.get('ENABLE_AUDIO_TRANSCRIPTION'):
                            audio_transcription_status = 'pending'
                            queue_client.enqueue_audio_transcription(AudioJobPayload(message_id=f"{msg.chat_id}-{msg.id}", audio_path=media_path, owner_id=owner_id, case_id=case_id, translate_transcription=True))
                            media_type = "voice"
                    except Exception as e:
                        print(f"[ERROR] Voice processing failed: {e}")

        await save_message_with_processing_status(
            owner_id=owner_id, channel_id=msg.chat_id, username=username, message=msg, sender=sender,
            media_path=media_path, media_type=media_type, original_language=detected_lang,
            translation_status=translation_status, image_analysis_status=image_analysis_status,
            audio_transcription_status=audio_transcription_status, geolocation_status=geolocation_status
        )

        publish_event("new_message", {"owner_id": owner_id, "channel_id": str(msg.chat_id), "channel_username": username})

        full_id = f"{msg.chat_id}-{msg.id}"
        if needs_trans and config.get('ENABLE_TRANSLATION'):
            queue_client.enqueue_translation(TranslationJobPayload(
                message_id=full_id, original_text=text, source_language=detected_lang, owner_id=owner_id, case_id=case_id,
                enable_emotion_analysis=config.get('ENABLE_EMOTION_ANALYSIS', False),
                enable_label_classifier=config.get('ENABLE_LABEL_CLASSIFIER', False),
                enable_geolocation_extraction=config.get('ENABLE_GEOLOCATION_EXTRACTION', False),
            ))
        else:
            if text and len(text.strip()) > 10:
                if config.get('ENABLE_EMOTION_ANALYSIS'):
                    queue_client.enqueue_emotion(EmotionJobPayload(message_id=full_id, text=text, owner_id=owner_id, case_id=case_id))
                if config.get('ENABLE_LABEL_CLASSIFIER'):
                    queue_client.enqueue_classification(ClassificationJobPayload(message_id=full_id, text=text, owner_id=owner_id, case_id=case_id))

        if recursive and text:
            for link in extract_invite_links([text]):
                norm = link.lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '').strip()
                if norm != username.lower() and norm not in all_seen_channels:
                    all_seen_channels.add(norm)
                    found_channels.add(norm)
                    await found_channels_queue.put((norm, username))
    except Exception as e:
        print(f"[ERROR] {username}: Failed to process message {msg.id}: {e}")
