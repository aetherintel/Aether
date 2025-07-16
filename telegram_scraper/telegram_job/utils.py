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
            return str(downloaded_path)
        else:
            print(f"[DOWNLOAD] ❌ File not found after download: {downloaded_path}")
            return None
        
    except Exception as e:
        print(f"[ERROR] Failed to download media to {target_path}: {e}")
        import traceback
        traceback.print_exc()
        return None
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

if __name__ == "__main__":
    test_extract_links()