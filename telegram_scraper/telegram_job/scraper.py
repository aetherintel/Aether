import asyncio
import re
from telethon import events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telegram_job.telegram_client import client, login
from telegram_job.neo4j_client import save_message, is_scraped, mark_scraped

INVITE_LINK_RE = re.compile(r"(https?://)?t\.me/(joinchat/[\w-]+|\+[\w-]+)")

def extract_invite_links(messages: list[str]) -> list[str]:
    links = set()
    for msg in messages:
        links.update(INVITE_LINK_RE.findall(msg))
    return ["https://t.me/" + match[1] for match in links if match]

async def try_join_invite_link(invite_link: str) -> str | None:
    try:
        slug = invite_link.split('/')[-1]
        result = await client(ImportChatInviteRequest(slug))
        joined = result.chats[0]
        return joined.username
    except Exception as e:
        print(f"[WARN] Could not join {invite_link}: {e}")
        return None

async def _historic_backfill(channel_entity, channel_id, username) -> list[str]:
    messages = []
    async for m in client.iter_messages(channel_entity, reverse=True):
        if not hasattr(m, 'message') or not m.message:
            continue

        sender = await m.get_sender()
        if sender:
            await save_message(channel_id, username, m, sender)
            messages.append(m.message)
    return messages

async def _live_listener(channels):
    print(f"[DEBUG] Setting up listener for: {channels}")
    
    resolved = []
    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            resolved.append(entity)
            print(f"[DEBUG] Listening to {getattr(entity, 'title', ch)}")
        except Exception as e:
            print(f"[WARN] Could not resolve {ch}: {e}")

    @client.on(events.NewMessage(chats=resolved))
    async def handler(evt):
        print(f"[EVENT] New message in chat {evt.chat_id}")
        try:
            sender = await evt.message.get_sender()
            entity = await evt.get_chat()
            username = getattr(entity, "username", None)
            await save_message(evt.chat_id, username, evt.message, sender)
        except Exception as e:
            print(f"[ERROR] Live handler failed: {e}")

    await client.run_until_disconnected()


async def run_scraper(channels, _session_name, recursive=False, skip_history=False):
    await login()
    print("[DEBUG] Logged in")
    visited = set()
    queue = list(channels)

    async with client:
        while queue:
            ch = queue.pop(0)
            if ch in visited:
                continue
            visited.add(ch)

            entity = await client.get_entity(ch)
            username = entity.username or ch
            channel_id = entity.id

            print(f"[DEBUG] Entity type: {entity.__class__.__name__}")
            print(f"[SCRAPE] {ch}")

            if await is_scraped(username):
                print(f"[SKIP] Already scraped: {ch}")
                continue

            messages = []
            if not skip_history:
                messages = await _historic_backfill(entity, channel_id, username)

            if messages:
                await mark_scraped(username)

            if recursive and messages:
                links = extract_invite_links(messages)
                for link in links:
                    joined_username = await try_join_invite_link(link)
                    if joined_username and joined_username not in visited:
                        queue.append(joined_username)
                        print(f"[RECURSIVE] Joined {joined_username} from {link}")

        # Always start live listener at the end
        print("[LIVE] Starting real-time message tracking...")
        await _live_listener(channels)

async def run_live_listener_only(channels):
    print("[DEBUG] Running live listener only")
    await login()
    print("[DEBUG] Logged in")
    async with client:
        print("[LIVE-ONLY] Running live listener")
        await _live_listener(channels)
