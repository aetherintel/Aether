import asyncio
from telethon import events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telegram_client import client, login
from neo4j_client import save_message_if_new, is_scraped, mark_scraped
from utils import extract_invite_links, download_media

# Tracks last message ID seen per channel
channel_state = {}

async def try_join_invite_link(invite_link: str) -> str | None:
    try:
        slug = invite_link.split('/')[-1]
        result = await client(ImportChatInviteRequest(slug))
        joined = result.chats[0]
        return joined.username
    except Exception as e:
        print(f"[WARN] Could not join {invite_link}: {e}")
        return None

async def scrape_channel(channel_name: str, channel_info: dict):
    try:
        entity = await client.get_entity(channel_name)
        last_id = channel_info.get("last_id", 0)
        new_max_id = last_id

        async for msg in client.iter_messages(entity, min_id=last_id, reverse=True):
            if not msg.message:
                continue
            sender = await msg.get_sender()
            media_path = await download_media(channel_name, msg, client)
            await save_message_if_new(msg.chat_id, channel_name, msg, sender, media_path)
            new_max_id = max(new_max_id, msg.id)

        if new_max_id > last_id:
            channel_info["last_id"] = new_max_id
            print(f"[SCRAPE] Updated last_id for {channel_name}: {new_max_id}")
        else:
            print(f"[SCRAPE] No new messages for {channel_name}")

    except Exception as e:
        print(f"[ERROR] Scraping channel {channel_name} failed: {e}")

async def short_poll_channel(channel_name, poll_interval=60):
    if channel_name not in channel_state:
        channel_state[channel_name] = {"last_id": 0}

    while True:
        print(f"[POLL] Checking for updates in {channel_name}")
        await scrape_channel(channel_name, channel_state[channel_name])
        await asyncio.sleep(poll_interval)

async def start_short_polling(channels, poll_interval=60):
    tasks = [asyncio.create_task(short_poll_channel(ch, poll_interval)) for ch in channels]
    await asyncio.gather(*tasks)

async def _historic_backfill(channel_entity, channel_id, username) -> list[str]:
    messages = []
    async for m in client.iter_messages(channel_entity, reverse=True):
        if not hasattr(m, 'message') or not m.message:
            continue
        sender = await m.get_sender()
        media_path = await download_media(username, m, client)
        await save_message_if_new(channel_id, username, m, sender, media_path)
        messages.append(m.message)
    return messages

async def _live_listener(channels):
    print(f"[LIVE] Raw channels passed: {channels}")
    resolved = []
    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            resolved.append(entity)
            print(f"[LIVE] Resolved entity: {getattr(entity, 'title', ch)}")
        except Exception as e:
            print(f"[WARN] Could not resolve {ch}: {e}")

    if not resolved:
        print("[LIVE] No valid channels to listen to. Exiting early.")
        return

    @client.on(events.NewMessage(chats=resolved))
    async def handler(evt):
        try:
            print(f"[EVENT] New message in chat {evt.chat_id}")
            sender = await evt.get_sender()
            entity = await evt.get_chat()
            username = getattr(entity, "username", None) or str(evt.chat_id)
            media_path = await download_media(username, evt, client)
            await save_message_if_new(evt.chat_id, username, evt, sender, media_path)
            print(f"[DB] Message saved for chat {evt.chat_id}, user {username}")
        except Exception as e:
            print(f"[ERROR] Failed to process live message: {e}")
            import traceback
            traceback.print_exc()

    print("[DEBUG] NewMessage handler attached.")
    await start_short_polling(channels)
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
                print("[LIVE] Starting real-time message tracking...")
                await _live_listener([ch])
            else:
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
                print("[LIVE] Starting real-time message tracking...")
                await _live_listener([ch])

async def run_live_listener_only(channels):
    print("[DEBUG] Running live listener only")
    await login()
    print("[DEBUG] Logged in")
    async with client:
        print("[LIVE-ONLY] Running live listener")
        await _live_listener(channels)
