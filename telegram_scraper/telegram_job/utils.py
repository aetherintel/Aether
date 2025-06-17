import re
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, User, PeerChannel
import os
import asyncio
from pathlib import Path

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/public/media")) 
MAX_RETRIES = 5
INVITE_LINK_RE = re.compile(r"(https?://)?t\.me/(joinchat/[\w-]+|\+[\w-]+)")

def extract_invite_links(messages: list[str]) -> list[str]:
    links = set()
    for msg in messages:
        links.update(INVITE_LINK_RE.findall(msg))
    return ["https://t.me/" + match[1] for match in links if match]

async def download_media(channel: str, message, client) -> str | None:
    if not message.media or not client:
        return None

    channel_dir = MEDIA_ROOT / channel
    media_folder = channel_dir / "media"
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
            await asyncio.sleep(2 ** attempt)
    return None