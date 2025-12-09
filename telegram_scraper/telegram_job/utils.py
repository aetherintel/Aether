import re
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, User, PeerChannel
import os
import asyncio
from pathlib import Path

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/public/media")) 
MAX_RETRIES = 5

# FIXED: More comprehensive regex that catches all Telegram links
INVITE_LINK_RE = re.compile(r"https?://t\.me/([a-zA-Z0-9_]+|\+[a-zA-Z0-9_-]+|joinchat/[a-zA-Z0-9_-]+)")

def extract_invite_links(messages: list[str]) -> list[str]:
    """Extract all Telegram links from messages"""
    links = set()
    for msg in messages:
        if not msg:
            continue
        # Find all matches in the message
        matches = INVITE_LINK_RE.findall(msg)
        for match in matches:
            # Reconstruct the full URL
            full_url = f"https://t.me/{match}"
            links.add(full_url)
            print(f"[EXTRACT] Found Telegram link: {full_url}")
    
    return list(links)

def extract_all_telegram_references(messages: list[str]) -> list[str]:
    """Extract all possible Telegram references including @mentions"""
    links = set()
    
    # Pattern for full URLs
    url_pattern = re.compile(r"https?://t\.me/([a-zA-Z0-9_]+|\+[a-zA-Z0-9_-]+|joinchat/[a-zA-Z0-9_-]+)")
    
    # Pattern for @mentions (but be careful not to include @username in normal conversation)
    mention_pattern = re.compile(r"@([a-zA-Z0-9_]{5,})")  # At least 5 chars to avoid false positives
    
    # Pattern for bare t.me references
    bare_pattern = re.compile(r"t\.me/([a-zA-Z0-9_]+)")
    
    for msg in messages:
        if not msg:
            continue
            
        # Find URL links
        url_matches = url_pattern.findall(msg)
        for match in url_matches:
            full_url = f"https://t.me/{match}"
            links.add(full_url)
            print(f"[EXTRACT] Found URL link: {full_url}")
        
        # Find bare t.me references
        bare_matches = bare_pattern.findall(msg)
        for match in bare_matches:
            if not any(match in url_match for url_match in url_matches):  # Avoid duplicates
                full_url = f"https://t.me/{match}"
                links.add(full_url)
                print(f"[EXTRACT] Found bare reference: {full_url}")
        
        # Find @mentions that look like channels (optional, might be noisy)
        mention_matches = mention_pattern.findall(msg)
        for match in mention_matches:
            # Only include if it looks like a channel name (you might want to filter this more)
            if len(match) >= 5 and not match.lower() in ['everyone', 'channel', 'admin', 'admins']:
                full_url = f"https://t.me/{match}"
                links.add(full_url)
                print(f"[EXTRACT] Found mention: {full_url}")
    
    return list(links)

def generate_media_path(username: str, msg_id: int, media_type: str, message=None) -> str:
    """Generate predictable media path before download - FIXED VERSION"""
    # Use MEDIA_ROOT consistently
    channel_dir = MEDIA_ROOT / username
    
    # Try to get the original filename if available
    original_name = None
    if message and hasattr(message, 'file') and message.file:
        original_name = getattr(message.file, 'name', None)
    
    # Generate filename with message ID and type
    if original_name:
        base_name = Path(original_name).stem
        ext = Path(original_name).suffix
        filename = f"msg_{msg_id}_{base_name}{ext}"
    elif media_type == "photo":
        filename = f"msg_{msg_id}_photo.jpg"
    elif media_type == "video":
        filename = f"msg_{msg_id}_video.mp4"
    elif media_type == "document":
        filename = f"msg_{msg_id}_document"
    elif media_type == "audio":
        filename = f"msg_{msg_id}_audio.mp3"
    elif media_type == "webpage":
        return None
    else:
        filename = f"msg_{msg_id}_media"
    
    return str(channel_dir / filename)

# Also update the old download_media function to be consistent:
async def download_media(channel: str, message, client) -> str | None:
    if not message.media or not client:
        return None
    # Use MEDIA_ROOT consistently
    channel_dir = MEDIA_ROOT / channel
    media_folder = channel_dir / "media"  # Keep the /media subfolder if needed
    media_folder.mkdir(parents=True, exist_ok=True)

    # Default fallback
    media_file_name = getattr(message.file, "name", None) or f"{message.id}"

    # Add proper extension
    if isinstance(message.media, MessageMediaPhoto):
        media_file_name += ".jpg"
    elif isinstance(message.media, MessageMediaDocument):
        ext = getattr(message.file, "ext", None)
        media_file_name += f".{ext or 'bin'}"

    media_path = media_folder / media_file_name
    if media_path.exists():
        print(f"[MEDIA] Skipping existing file: {media_path}")
        return str(media_path)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            path = await message.download_media(file=str(media_path))
            if path:
                print(f"[MEDIA] Downloaded to: {path}")
                return path
        except Exception as e:
            print(f"[MEDIA] Failed to download media (attempt {attempt}): {e}")
            await asyncio.sleep(2 * attempt)
    return None

async def download_media_to_path(username: str, msg, client_ref, target_path: str) -> str:
    """Download media to specific path, return actual path - WITH DEBUGGING"""
    try:
        print(f"[DOWNLOAD] Starting download to: {target_path}")
        
        # Check if message has media
        if not msg.media:
            print(f"[DOWNLOAD] No media in message {msg.id}")
            return None
        
        # Ensure directory exists
        directory = os.path.dirname(target_path)
        print(f"[DOWNLOAD] Ensuring directory exists: {directory}")
        os.makedirs(directory, exist_ok=True)
        
        # Check if file already exists
        if os.path.exists(target_path):
            print(f"[DOWNLOAD] File already exists: {target_path}")
            return target_path
        
        print(f"[DOWNLOAD] Calling client.download_media with target: {target_path}")
        
        # Download to target path
        downloaded_path = await client_ref.download_media(msg.media, file=target_path)
        
        print(f"[DOWNLOAD] Download completed. Returned path: {downloaded_path}")
        
        # Verify the file exists
        if downloaded_path and os.path.exists(str(downloaded_path)):
            file_size = os.path.getsize(str(downloaded_path))
            print(f"[DOWNLOAD] ✅ File verified: {downloaded_path} ({file_size} bytes)")
            
            # COMPRESSION LOGIC
            try:
                final_path = str(downloaded_path)
                
                # Image Compression
                if final_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    print(f"[COMPRESS] Compressing image: {final_path}")
                    final_path = compress_image(final_path)
                    
                # Video Compression
                elif final_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                    print(f"[COMPRESS] Compressing video: {final_path}")
                    final_path = compress_video(final_path)
                    
                return final_path
                
            except Exception as e:
                print(f"[WARN] Compression failed, using original file: {e}")
                return str(downloaded_path)
                
        else:
            print(f"[DOWNLOAD] ❌ File not found after download: {downloaded_path}")
            return None
        
    except Exception as e:
        print(f"[ERROR] Failed to download media to {target_path}: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================================
# COMPRESSION HELPERS
# ============================================================================

def compress_image(file_path: str, max_width: int = 1920, quality: int = 80) -> str:
    """
    Compress image using Pillow.
    - Resize if width > max_width
    - Convert to RGB (remove alpha) and save as JPEG if PNG/WEBP
    - Optimize quality
    """
    try:
        from PIL import Image
        import os
        
        img = Image.open(file_path)
        original_size = os.path.getsize(file_path)
        
        # Resize if too large
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            print(f"[COMPRESS] Resized image to {max_width}x{new_height}")
            
        # Convert to RGB if necessary (e.g. PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # Save as JPEG (replace original or create new if format changed)
        # We'll overwrite the original file to keep the path consistent if possible
        # But if it was a PNG, we might want to change extension to .jpg
        
        path_obj = Path(file_path)
        if path_obj.suffix.lower() != '.jpg':
            new_path = path_obj.with_suffix('.jpg')
            img.save(new_path, "JPEG", quality=quality, optimize=True)
            # Remove original if different
            os.remove(file_path)
            file_path = str(new_path)
        else:
            img.save(file_path, "JPEG", quality=quality, optimize=True)
            
        new_size = os.path.getsize(file_path)
        savings = original_size - new_size
        print(f"[COMPRESS] Image compressed: {original_size} -> {new_size} bytes (Saved {savings/1024:.2f} KB)")
        
        return file_path
        
    except Exception as e:
        print(f"[ERROR] Image compression failed: {e}")
        return file_path

def compress_video(file_path: str, crf: int = 28) -> str:
    """
    Compress video using ffmpeg (via subprocess).
    - Convert to h.264 mp4
    - CRF 28 (good compression/quality balance)
    - AAC audio
    """
    import subprocess
    import os
    import shutil
    
    try:
        temp_path = f"{file_path}.temp.mp4"
        
        # ffmpeg command
        # -i input
        # -vcodec libx264 (H.264 video)
        # -crf 28 (Constant Rate Factor, higher = more compression)
        # -acodec aac (AAC audio)
        # -movflags +faststart (Web optimization)
        # -y (overwrite output)
        
        cmd = [
            "ffmpeg",
            "-i", file_path,
            "-vcodec", "libx264",
            "-crf", str(crf),
            "-acodec", "aac",
            "-movflags", "+faststart",
            "-y",
            temp_path
        ]
        
        print(f"[COMPRESS] Running ffmpeg: {' '.join(cmd)}")
        
        # Run ffmpeg
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            print(f"[ERROR] ffmpeg failed: {result.stderr.decode()}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return file_path
            
        # Check if compression actually helped
        original_size = os.path.getsize(file_path)
        new_size = os.path.getsize(temp_path)
        
        if new_size < original_size:
            # Replace original with compressed
            shutil.move(temp_path, file_path)
            savings = original_size - new_size
            print(f"[COMPRESS] Video compressed: {original_size} -> {new_size} bytes (Saved {savings/(1024*1024):.2f} MB)")
        else:
            print(f"[COMPRESS] Compressed video was larger ({new_size} > {original_size}), keeping original")
            os.remove(temp_path)
            
        return file_path
        
    except Exception as e:
        print(f"[ERROR] Video compression failed: {e}")
        return file_path
def get_media_type(media) -> str:
    """Determine media type for file naming - FIXED VERSION"""
    try:
        # Use type name string comparison to avoid import issues
        media_type_name = type(media).__name__
        
        if media_type_name == "MessageMediaPhoto":
            return "photo"
        elif media_type_name == "MessageMediaDocument":
            # Safely access document properties
            if hasattr(media, 'document') and media.document:
                doc = media.document
                # Safely get mime_type as string
                mime_type = getattr(doc, 'mime_type', '')
                if isinstance(mime_type, str):
                    mime_lower = mime_type.lower()
                    if mime_lower.startswith('video/'):
                        return "video"
                    elif mime_lower.startswith('audio/'):
                        return "audio"
                    elif mime_lower.startswith('image/'):
                        return "image"
            return "document"
        elif media_type_name == "MessageMediaWebPage":
            # Web pages don't have downloadable media
            return "webpage"
        elif hasattr(media, 'video'):
            return "video"
        elif hasattr(media, 'audio'):
            return "audio"
        else:
            print(f"[DEBUG] Unknown media type: {media_type_name}")
            return "unknown"
    except Exception as e:
        print(f"[WARN] Error determining media type: {e}")
        return "unknown"

# Test function to verify the regex works
def test_extract_links():
    test_messages = [
        "Check out https://t.me/Clownswelt for more info",
        "Join our private group: https://t.me/+PcEcUv4wOTRiMDYx",
        "Old style link: https://t.me/joinchat/ABC123DEF456",
        "Bare reference: t.me/somechannel",
        "Follow @Clownswelt for updates",
        "Don't forget @admin and @everyone",  # Should filter out common false positives
        "Contact @verylongchannelname for details"
    ]
    
    print("=== Testing Link Extraction ===")
    links = extract_all_telegram_references(test_messages)
    print(f"Found {len(links)} unique links:")
    for link in links:
        print(f"  - {link}")

# Updated utils.py functions for audio/voice support

def get_media_type(media) -> str:
    """Determine media type for file naming - WITH VOICE SUPPORT"""
    try:
        # Use type name string comparison to avoid import issues
        media_type_name = type(media).__name__
        
        if media_type_name == "MessageMediaPhoto":
            return "photo"
        elif media_type_name == "MessageMediaDocument":
            # Check for voice messages first
            if hasattr(media, 'document') and media.document:
                doc = media.document
                
                # Check attributes for voice flag
                if hasattr(doc, 'attributes'):
                    for attr in doc.attributes:
                        # Voice messages have a 'voice' attribute
                        if hasattr(attr, 'voice') and attr.voice:
                            return "voice"
                        # Video notes (round video messages) 
                        if hasattr(attr, 'round_message') and attr.round_message:
                            return "video_note"
                
                # Then check MIME type
                mime_type = getattr(doc, 'mime_type', '')
                if isinstance(mime_type, str):
                    mime_lower = mime_type.lower()
                    if mime_lower.startswith('video/'):
                        return "video"
                    elif mime_lower.startswith('audio/'):
                        return "audio"
                    elif mime_lower.startswith('image/'):
                        return "image"
            return "document"
        elif media_type_name == "MessageMediaWebPage":
            # Web pages don't have downloadable media
            return "webpage"
        elif hasattr(media, 'video'):
            return "video"
        elif hasattr(media, 'audio'):
            return "audio"
        else:
            print(f"[DEBUG] Unknown media type: {media_type_name}")
            return "unknown"
    except Exception as e:
        print(f"[WARN] Error determining media type: {e}")
        return "unknown"


def generate_media_path(username: str, msg_id: int, media_type: str, message=None) -> str:
    """Generate predictable media path before download - WITH VOICE SUPPORT"""
    # Use MEDIA_ROOT consistently
    channel_dir = MEDIA_ROOT / username
    
    # Try to get the original filename if available
    original_name = None
    if message and hasattr(message, 'file') and message.file:
        original_name = getattr(message.file, 'name', None)
    
    # Generate filename with message ID and type
    if original_name:
        base_name = Path(original_name).stem
        ext = Path(original_name).suffix
        filename = f"msg_{msg_id}_{base_name}{ext}"
    elif media_type == "photo":
        filename = f"msg_{msg_id}_photo.jpg"
    elif media_type == "video":
        filename = f"msg_{msg_id}_video.mp4"
    elif media_type == "voice":
        # Voice messages are typically OGG format with Opus codec
        filename = f"msg_{msg_id}_voice.ogg"
    elif media_type == "video_note":
        # Round video messages
        filename = f"msg_{msg_id}_videonote.mp4"
    elif media_type == "audio":
        filename = f"msg_{msg_id}_audio.mp3"
    elif media_type == "document":
        filename = f"msg_{msg_id}_document"
    elif media_type == "webpage":
        return None
    else:
        filename = f"msg_{msg_id}_media"
    
    return str(channel_dir / filename)


def is_media_audio_capable(media_type: str) -> bool:
    """Check if media type can contain audio for transcription"""
    return media_type in ["audio", "voice", "video", "video_note"]


def should_queue_transcription(msg, media_type: str) -> bool:
    """
    Determine if message should be queued for audio transcription
    
    Args:
        msg: Telegram message object
        media_type: Detected media type
    
    Returns:
        True if message should be transcribed
    """
    # Always transcribe voice messages and audio files
    if media_type in ["voice", "audio"]:
        return True
    
    # For videos, check if it's not just an animation/GIF
    if media_type in ["video", "video_note"]:
        # Skip if it's marked as animation (GIFs)
        if hasattr(msg, 'media') and hasattr(msg.media, 'document'):
            doc = msg.media.document
            if hasattr(doc, 'attributes'):
                for attr in doc.attributes:
                    # Skip animated content without sound
                    if hasattr(attr, 'animated') and attr.animated:
                        # Check if it has audio track
                        if not (hasattr(attr, 'has_audio') and attr.has_audio):
                            return False
        return True
    
    return False


def get_audio_file_info(file_path: str) -> dict:
    """
    Get audio file information for logging
    
    Args:
        file_path: Path to audio/video file
    
    Returns:
        Dictionary with file info
    """
    import os
    from pathlib import Path
    
    if not os.path.exists(file_path):
        return {"exists": False}
    
    path = Path(file_path)
    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    
    return {
        "exists": True,
        "name": path.name,
        "extension": path.suffix,
        "size_bytes": size_bytes,
        "size_mb": round(size_mb, 2),
        "path": str(path)
    }

if __name__ == "__main__":
    test_extract_links()