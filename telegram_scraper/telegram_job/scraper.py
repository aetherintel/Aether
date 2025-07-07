import asyncio
from pathlib import Path
import aiohttp
import os
import time
from telethon import events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import FloodWaitError, FloodError
from telegram_client import client, login
from neo4j_client import save_message_if_new, is_scraped, mark_scraped
from utils import download_media_to_path, extract_invite_links, generate_media_path, get_media_type

# Job launcher configuration
JOB_LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL", "http://job-launcher:9001")
JOB_SECRET_TOKEN = os.getenv("JOB_SECRET_TOKEN", "changeme")
CURRENT_SESSION_NAME = os.getenv("SESSION_NAME", "default")
CURRENT_OWNER_ID = os.getenv("OWNER_ID", "unknown")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/public/media"))

# Rate limiting configuration
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
BACKOFF_MULTIPLIER = float(os.getenv("BACKOFF_MULTIPLIER", "2.0"))
MESSAGE_BATCH_SIZE = int(os.getenv("MESSAGE_BATCH_SIZE", "20"))
MESSAGE_BATCH_DELAY = float(os.getenv("MESSAGE_BATCH_DELAY", "0.05"))

# Media download queue
media_download_queue = asyncio.Queue()

async def get_entity_safe(identifier):
    """Safely get a Telegram entity from either username or chat ID"""
    try:
        if isinstance(identifier, str) and (identifier.lstrip('-').isdigit()):
            chat_id = int(identifier)
            print(f"[ENTITY] Resolving chat ID: {chat_id}")
            entity = await rate_limited_request(
                client.get_entity(chat_id),
                f"get_entity({chat_id})"
            )
        else:
            print(f"[ENTITY] Resolving username: {identifier}")
            entity = await rate_limited_request(
                client.get_entity(identifier),
                f"get_entity({identifier})"
            )
        
        clean_name = getattr(entity, 'username', None) or str(entity.id)
        print(f"[ENTITY] Resolved to: {clean_name} (type: {type(entity).__name__})")
        
        return entity, clean_name
    except Exception as e:
        print(f"[ERROR] Could not resolve entity '{identifier}': {e}")
        return None, None

async def rate_limited_request(coro, operation_name="request"):
    """Wrapper for API calls with rate limiting and backoff"""
    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(RATE_LIMIT_DELAY)
            result = await coro
            return result
            
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"[RATE-LIMIT] {operation_name} hit flood wait, sleeping for {wait_time} seconds")
            await asyncio.sleep(wait_time + 1)
            
        except FloodError as e:
            wait_time = 60
            print(f"[RATE-LIMIT] {operation_name} hit flood error, sleeping for {wait_time} seconds")
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            if "429" in str(e) or "too many requests" in str(e).lower():
                wait_time = (attempt + 1) * 30
                print(f"[RATE-LIMIT] {operation_name} hit 429, attempt {attempt + 1}, sleeping for {wait_time} seconds")
                await asyncio.sleep(wait_time)
            else:
                raise e
    
    raise Exception(f"Max retries ({MAX_RETRIES}) exceeded for {operation_name}")

last_request_time = 0

async def ensure_rate_limit():
    """Ensure we don't exceed rate limits"""
    global last_request_time
    current_time = time.time()
    time_since_last = current_time - last_request_time
    
    if time_since_last < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - time_since_last
        await asyncio.sleep(sleep_time)
    
    last_request_time = time.time()

channel_state = {}
MAX_CONCURRENT_SCRAPERS = 5
scraper_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPERS)
invite_queue = asyncio.Queue()
channel_queue = asyncio.Queue()

def normalize_channel_name(name_or_link):
    """Normalize channel names/links for comparison"""
    if not name_or_link:
        return None
    
    name = str(name_or_link).lower()
    name = name.replace('https://t.me/', '')
    name = name.replace('http://t.me/', '')
    name = name.replace('t.me/', '')
    name = name.replace('@', '')
    name = name.strip('⁠ \t\n\r')
    
    return name if name else None

def is_self_reference(link, current_channel):
    """Check if the invite link points to the current channel"""
    normalized_link = normalize_channel_name(link)
    normalized_current = normalize_channel_name(current_channel)
    
    if not normalized_link or not normalized_current:
        return False
    
    return normalized_link == normalized_current

async def process_single_message(msg, username, recursive, visited, processed_links):
    """Process a single message - SAVE ONCE with predicted media path"""
    try:
        await ensure_rate_limit()
        sender = await msg.get_sender()
        
        # Determine media path (predicted or None)
        media_path = None
        if msg.media:
            media_type = get_media_type(msg.media)
            
            # Only generate path for downloadable media types (silently skip webpages)
            if media_type in ["photo", "video", "document", "audio"]:
                media_path = generate_media_path(username, msg.id, media_type, msg)
                
                # Only queue for download if we have a valid path
                if media_path:
                    await media_download_queue.put((username, msg, client, media_path))
            # Don't log anything for webpages - just silently skip like the old version
        
        # SINGLE SAVE: Save message with predicted media path (or None)
        await save_message_if_new(msg.chat_id, username, msg, sender, media_path)
        
        # Extract invite links for recursive processing
        if recursive and msg.message:
            links = extract_invite_links([msg.message])
            for link in links:
                if is_self_reference(link, username):
                    continue
                    
                if link not in processed_links:
                    processed_links.add(link)
                    await invite_queue.put((link, visited))
                    print(f"[STREAM] Found NEW invite link: {link}")
        
    except Exception as e:
        print(f"[ERROR] Failed to process message {msg.id}: {e}")
        import traceback
        traceback.print_exc()
async def media_download_worker():
    """Background worker that downloads media to predicted paths"""
    print("[MEDIA-WORKER] Started media download worker")
    while True:
        try:
            username, msg, client_ref, predicted_path = await media_download_queue.get()
            try:
                os.makedirs(os.path.dirname(predicted_path), exist_ok=True)
                actual_path = await download_media_to_path(username, msg, client_ref, predicted_path)
                
                if actual_path and actual_path != predicted_path:
                    print(f"[MEDIA-WORKER] Path mismatch! Predicted: {predicted_path}, Actual: {actual_path}")
                    # Could add database update here if needed
                else:
                    print(f"[MEDIA-WORKER] Downloaded to: {predicted_path}")
                    
            except Exception as e:
                print(f"[MEDIA-WORKER] Failed to download media for message {msg.id}: {e}")
            finally:
                media_download_queue.task_done()
                await asyncio.sleep(2)
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ERROR] Media worker exception: {e}")
            await asyncio.sleep(5)

async def try_join_invite_link(invite_link: str) -> str | None:
    try:
        print(f"[JOIN] Processing invite link: {invite_link}")
        slug = invite_link.split('/')[-1]
        
        if slug.startswith('+'):
            slug = slug[1:]
            
        from telethon.tl.functions.messages import CheckChatInviteRequest
        try:
            invite_info = await rate_limited_request(
                client(CheckChatInviteRequest(slug)),
                f"CheckChatInvite({slug})"
            )
            
            if hasattr(invite_info, 'chat'):
                joined = invite_info.chat
            else:
                result = await rate_limited_request(
                    client(ImportChatInviteRequest(slug)),
                    f"ImportChatInvite({slug})"
                )
                joined = result.chats[0]
                
        except Exception as check_error:
            result = await rate_limited_request(
                client(ImportChatInviteRequest(slug)),
                f"ImportChatInvite({slug}) fallback"
            )
            joined = result.chats[0]
        
        username = getattr(joined, 'username', None)
        if username:
            return username
        else:
            return str(joined.id)
            
    except Exception as e:
        print(f"[WARN] Could not process invite link {invite_link}: {e}")
        return None

async def spawn_container_for_channel(channel_name: str):
    """Spawn a new container for the discovered channel via job-launcher API"""
    print(f"[SPAWN] Attempting to spawn container for: {channel_name}")
    
    if not JOB_LAUNCHER_URL or not JOB_SECRET_TOKEN:
        print(f"[WARN] Job launcher not configured")
        return None
        
    try:
        headers = {
            "Authorization": f"Bearer {JOB_SECRET_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channels": [channel_name],
            "tg_session": CURRENT_SESSION_NAME,
            "mode": "scrape",
            "recursive": False,
            "neo4j": True,
            "owner_id": CURRENT_OWNER_ID
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{JOB_LAUNCHER_URL}/scrape",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"[SPAWN] ✅ Successfully spawned container: {result.get('container_id')}")
                    return result.get('container_id')
                else:
                    print(f"[ERROR] Failed to spawn container: {response.status}")
                    return None
                    
    except Exception as e:
        print(f"[ERROR] Exception spawning container: {e}")
        return None

async def scrape_channel(channel_name: str, channel_info: dict):
    """Simple channel scraping for polling"""
    try:
        entity, clean_name = await get_entity_safe(channel_name)
        if not entity:
            return
            
        last_id = channel_info.get("last_id", 0)
        new_max_id = last_id
        processed_links = set()

        async for msg in client.iter_messages(entity, min_id=last_id, reverse=True):
            if not msg.message:
                continue
                
            # Use the same single message processing
            await process_single_message(msg, clean_name, False, set(), processed_links)
            new_max_id = max(new_max_id, msg.id)

        if new_max_id > last_id:
            channel_info["last_id"] = new_max_id
            print(f"[SCRAPE] Updated last_id for {clean_name}: {new_max_id}")

    except Exception as e:
        print(f"[ERROR] Scraping channel {channel_name} failed: {e}")

async def _streaming_backfill(channel_entity, channel_id, username, recursive: bool, visited: set):
    """Process messages as a stream with single save per message"""
    message_count = 0
    processed_links = set()
    
    print(f"[STREAM] Starting backfill for {username}")
    
    async for msg in client.iter_messages(channel_entity, reverse=True):
        if not hasattr(msg, 'message') or not msg.message:
            continue
            
        message_count += 1
        
        # Process message once - saves with predicted media path
        await process_single_message(msg, username, recursive, visited, processed_links)
        
        # Batching control
        if message_count % MESSAGE_BATCH_SIZE == 0:
            await asyncio.sleep(MESSAGE_BATCH_DELAY)
        
        if message_count % 100 == 0:
            print(f"[STREAM] Processed {message_count} messages, found {len(processed_links)} links")
            await asyncio.sleep(0.1)
    
    print(f"[STREAM] ✅ Processed {message_count} messages from {username}")
    return message_count > 0

async def _live_listener(channels):
    """Live message listener"""
    print(f"[LIVE] Setting up listener for {len(channels)} channels")
    resolved = []
    
    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            resolved.append(entity)
        except Exception as e:
            print(f"[WARN] Could not resolve {ch}: {e}")

    if not resolved:
        print("[LIVE] No valid channels to listen to")
        return

    @client.on(events.NewMessage(chats=resolved))
    async def handler(evt):
        try:
            sender = await evt.get_sender()
            entity = await evt.get_chat()
            username = getattr(entity, "username", None) or str(evt.chat_id)
            
            # Use single message processing for live messages too
            await process_single_message(evt, username, False, set(), set())
            
        except Exception as e:
            print(f"[ERROR] Failed to process live message: {e}")

    print("[LIVE] Event handler attached, starting polling...")
    await start_short_polling(channels)

async def short_poll_channel(channel_name, poll_interval=60):
    if channel_name not in channel_state:
        channel_state[channel_name] = {"last_id": 0}

    while True:
        await scrape_channel(channel_name, channel_state[channel_name])
        await asyncio.sleep(poll_interval)

async def start_short_polling(channels, poll_interval=60):
    tasks = [asyncio.create_task(short_poll_channel(ch, poll_interval)) for ch in channels]
    await asyncio.gather(*tasks)

async def invite_link_worker():
    """Process invite links and spawn containers"""
    print("[INVITE-WORKER] Started invite link worker")
    while True:
        try:
            link, visited = await invite_queue.get()
            print(f"[INVITE-WORKER] Processing: {link}")
            
            if not client.is_connected():
                await client.connect()
                await asyncio.sleep(2)
            
            joined_username = await try_join_invite_link(link)
            if joined_username and joined_username not in visited:
                container_id = await spawn_container_for_channel(joined_username)
                if container_id:
                    visited.add(joined_username)
                    print(f"[CONTAINER] ✅ Spawned container for {joined_username}")
                else:
                    await channel_queue.put(joined_username)
            
            invite_queue.task_done()
            await asyncio.sleep(2)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ERROR] Invite worker exception: {e}")
            await asyncio.sleep(5)

async def channel_worker(visited: set, recursive: bool, skip_history: bool, live_channels: list):
    """Worker that processes channels from the queue"""
    while True:
        try:
            ch = await channel_queue.get()
            
            if ch in visited:
                channel_queue.task_done()
                continue
                
            async with scraper_semaphore:
                visited.add(ch)
                
                try:
                    entity, clean_name = await get_entity_safe(ch)
                    if not entity:
                        continue
                    
                    print(f"[WORKER] Processing {clean_name}")
                    
                    if await is_scraped(clean_name):
                        print(f"[SKIP] Already scraped: {clean_name}")
                        live_channels.append(ch)
                    else:
                        if not skip_history:
                            had_messages = await _streaming_backfill(
                                entity, entity.id, clean_name, recursive, visited
                            )
                            
                            if had_messages:
                                await mark_scraped(clean_name)
                                live_channels.append(ch)
                        else:
                            await mark_scraped(clean_name)
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
    print(f"[DEBUG] Starting scraper: recursive={recursive}, skip_history={skip_history}")
    
    visited = set()
    live_channels = []
    
    # Queue initial channels
    for ch in channels:
        await channel_queue.put(ch)
    
    async with client:
        workers = []
        
        # Channel processing workers
        for i in range(MAX_CONCURRENT_SCRAPERS):
            worker = asyncio.create_task(
                channel_worker(visited, recursive, skip_history, live_channels)
            )
            workers.append(worker)
        
        # Invite link workers (if recursive)
        if recursive:
            for i in range(3):
                worker = asyncio.create_task(invite_link_worker())
                workers.append(worker)
        
        # Media download workers
        for i in range(2):
            worker = asyncio.create_task(media_download_worker())
            workers.append(worker)
        
        # Monitor progress
        while not channel_queue.empty() or not invite_queue.empty():
            await asyncio.sleep(2)
            print(f"[STATUS] Channels: {channel_queue.qsize()}, Invites: {invite_queue.qsize()}, Media: {media_download_queue.qsize()}")
                
        print("[STATUS] ✅ Processing complete")
        await asyncio.sleep(10)
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        
        # Start live listening
        if live_channels:
            print(f"[LIVE] Starting live tracking for {len(live_channels)} channels")
            await _live_listener(live_channels)

async def run_live_listener_only(channels):
    await login()
    async with client:
        await _live_listener(channels)