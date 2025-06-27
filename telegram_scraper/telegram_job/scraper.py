import asyncio
from telethon import events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telegram_client import client, login
from neo4j_client import save_message_if_new, is_scraped, mark_scraped
from utils import extract_invite_links, download_media

# Tracks last message ID seen per channel
channel_state = {}

# Semaphore to limit concurrent scraping tasks
MAX_CONCURRENT_SCRAPERS = 5
scraper_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPERS)

# Global queue for discovered invite links
invite_queue = asyncio.Queue()

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

# NEW: Stream messages and extract links in parallel
async def _streaming_backfill(channel_entity, channel_id, username, recursive: bool, visited: set):
    """Process messages as a stream, extracting links immediately"""
    message_count = 0
    processed_links = set()
    
    async for m in client.iter_messages(channel_entity, reverse=True):
        if not hasattr(m, 'message') or not m.message:
            continue
            
        message_count += 1
        
        # Extract invite links IMMEDIATELY from each message
        if recursive and m.message:
            links = extract_invite_links([m.message])
            for link in links:
                if link not in processed_links:
                    processed_links.add(link)
                    # Add to global queue for immediate processing
                    await invite_queue.put((link, visited))
                    print(f"[STREAM] Found invite link in message {message_count}: {link}")
        
        # Start async tasks for time-consuming operations
        async def process_message(msg):
            sender = await msg.get_sender()
            media_path = await download_media(username, msg, client)
            await save_message_if_new(msg.chat_id, username, msg, sender, media_path)
        
        # Fire and forget - don't wait for media download
        asyncio.create_task(process_message(m))
        
        # Yield control periodically to allow other tasks to run
        if message_count % 10 == 0:
            await asyncio.sleep(0)  # Let other coroutines run
    
    print(f"[STREAM] Processed {message_count} messages from {username}")
    return message_count > 0

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

# NEW: Worker that processes invite links
async def invite_link_worker():
    """Continuously process invite links from the queue"""
    while True:
        try:
            link, visited = await invite_queue.get()
            
            joined_username = await try_join_invite_link(link)
            if joined_username and joined_username not in visited:
                # Add to main channel queue
                await channel_queue.put(joined_username)
                print(f"[INVITE-WORKER] Successfully joined and queued: {joined_username}")
            
            invite_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ERROR] Invite worker exception: {e}")

# Global channel queue
channel_queue = asyncio.Queue()

async def channel_worker(visited: set, recursive: bool, skip_history: bool, live_channels: list):
    """Worker that processes channels from the queue asynchronously"""
    while True:
        try:
            ch = await channel_queue.get()
            
            if ch in visited:
                channel_queue.task_done()
                continue
                
            async with scraper_semaphore:  # Limit concurrent scrapers
                visited.add(ch)
                
                try:
                    entity = await client.get_entity(ch)
                    username = entity.username or ch
                    channel_id = entity.id
                    
                    print(f"[WORKER] Processing {ch}")
                    
                    if await is_scraped(username):
                        print(f"[SKIP] Already scraped: {ch}")
                        live_channels.append(ch)
                    else:
                        if not skip_history:
                            # Use streaming backfill instead of waiting for all messages
                            had_messages = await _streaming_backfill(
                                entity, channel_id, username, recursive, visited
                            )
                            
                            if had_messages:
                                await mark_scraped(username)
                                live_channels.append(ch)
                        else:
                            await mark_scraped(username)
                            live_channels.append(ch)
                
                except Exception as e:
                    print(f"[ERROR] Worker failed for {ch}: {e}")
                
                finally:
                    channel_queue.task_done()
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ERROR] Worker exception: {e}")

async def run_scraper(channels, _session_name, recursive=False, skip_history=False):
    await login()
    print("[DEBUG] Logged in")
    
    visited = set()
    live_channels = []  # Channels ready for live listening
    
    # Add initial channels to queue
    for ch in channels:
        await channel_queue.put(ch)
    
    async with client:
        # Start workers
        workers = []
        
        # Channel processing workers
        for i in range(MAX_CONCURRENT_SCRAPERS):
            worker = asyncio.create_task(
                channel_worker(visited, recursive, skip_history, live_channels)
            )
            workers.append(worker)
        
        # Invite link processing workers (if recursive)
        if recursive:
            for i in range(3):  # 3 workers for invite links
                worker = asyncio.create_task(invite_link_worker())
                workers.append(worker)
        
        # Wait for initial channels to be processed
        # But don't wait forever - check periodically for new channels
        while not channel_queue.empty() or not invite_queue.empty():
            await asyncio.sleep(5)  # Check every 5 seconds
            print(f"[STATUS] Channels in queue: {channel_queue.qsize()}, Invites in queue: {invite_queue.qsize()}")
        
        # Give a bit more time for final processing
        await asyncio.sleep(10)
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*workers, return_exceptions=True)
        
        # Start live listening for all processed channels
        if live_channels:
            print(f"[LIVE] Starting real-time tracking for {len(live_channels)} channels")
            await _live_listener(live_channels)

async def run_live_listener_only(channels):
    print("[DEBUG] Running live listener only")
    await login()
    print("[DEBUG] Logged in")
    async with client:
        print("[LIVE-ONLY] Running live listener")
        await _live_listener(channels)