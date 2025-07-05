import asyncio
import aiohttp
import os
import time
from telethon import events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import FloodWaitError, FloodError
from telegram_client import client, login
from neo4j_client import save_message_if_new, is_scraped, mark_scraped
from utils import extract_invite_links, download_media

# Alternative: import the more comprehensive function
# from utils import extract_all_telegram_references as extract_invite_links

# Job launcher configuration
JOB_LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL", "http://job-launcher:9001")
JOB_SECRET_TOKEN = os.getenv("JOB_SECRET_TOKEN", "changeme")
CURRENT_SESSION_NAME = os.getenv("SESSION_NAME", "default")
CURRENT_OWNER_ID = os.getenv("OWNER_ID", "unknown")

# Rate limiting configuration
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
BACKOFF_MULTIPLIER = float(os.getenv("BACKOFF_MULTIPLIER", "2.0"))
MESSAGE_BATCH_SIZE = int(os.getenv("MESSAGE_BATCH_SIZE", "20"))  # Increased batch size
MESSAGE_BATCH_DELAY = float(os.getenv("MESSAGE_BATCH_DELAY", "0.05"))  # Reduced delay

# NEW: Separate queue for media downloads (low priority)
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

# NEW: Track processed channels to avoid self-references
def normalize_channel_name(name_or_link):
    """Normalize channel names/links for comparison"""
    if not name_or_link:
        return None
    
    # Remove common URL parts and formatting
    name = str(name_or_link).lower()
    name = name.replace('https://t.me/', '')
    name = name.replace('http://t.me/', '')
    name = name.replace('t.me/', '')
    name = name.replace('@', '')
    name = name.strip('⁠ \t\n\r')  # Remove invisible chars
    
    return name if name else None

def is_self_reference(link, current_channel):
    """Check if the invite link points to the current channel"""
    normalized_link = normalize_channel_name(link)
    normalized_current = normalize_channel_name(current_channel)
    
    if not normalized_link or not normalized_current:
        return False
    
    return normalized_link == normalized_current

async def try_join_invite_link(invite_link: str) -> str | None:
    try:
        print(f"[JOIN] Processing invite link: {invite_link}")
        slug = invite_link.split('/')[-1]
        
        if slug.startswith('+'):
            slug = slug[1:]
            
        print(f"[JOIN] Using slug: {slug}")
        
        from telethon.tl.functions.messages import CheckChatInviteRequest
        try:
            invite_info = await rate_limited_request(
                client(CheckChatInviteRequest(slug)),
                f"CheckChatInvite({slug})"
            )
            print(f"[JOIN] Got invite info: {type(invite_info).__name__}")
            
            if hasattr(invite_info, 'chat'):
                joined = invite_info.chat
                print(f"[JOIN] Already a member, got chat info")
            else:
                print(f"[JOIN] Not a member, attempting to join...")
                result = await rate_limited_request(
                    client(ImportChatInviteRequest(slug)),
                    f"ImportChatInvite({slug})"
                )
                joined = result.chats[0]
                print(f"[JOIN] Successfully joined new chat")
                
        except Exception as check_error:
            print(f"[JOIN] CheckChatInvite failed: {check_error}")
            try:
                result = await rate_limited_request(
                    client(ImportChatInviteRequest(slug)),
                    f"ImportChatInvite({slug}) fallback"
                )
                joined = result.chats[0]
                print(f"[JOIN] Successfully joined via fallback")
            except Exception as join_error:
                print(f"[JOIN] Both methods failed: {join_error}")
                return None
        
        username = getattr(joined, 'username', None)
        if username:
            print(f"[JOIN] Public channel: @{username}")
            return username
        else:
            chat_id = str(joined.id)
            title = getattr(joined, 'title', 'Unknown')
            print(f"[JOIN] Private group: '{title}' (ID: {chat_id})")
            return chat_id
            
    except Exception as e:
        print(f"[WARN] Could not process invite link {invite_link}: {e}")
        return None

async def spawn_container_for_channel(channel_name: str):
    """Spawn a new container for the discovered channel via job-launcher API"""
    print(f"[SPAWN] Attempting to spawn container for: {channel_name}")
    
    if not JOB_LAUNCHER_URL or not JOB_SECRET_TOKEN:
        print(f"[WARN] Job launcher not configured, cannot spawn container for {channel_name}")
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
            "recursive": False,  # Don't make spawned containers recursive
            "neo4j": True,
            "owner_id": CURRENT_OWNER_ID
        }
        
        print(f"[SPAWN] Payload: {payload}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{JOB_LAUNCHER_URL}/scrape",
                headers=headers,
                json=payload
            ) as response:
                response_text = await response.text()
                print(f"[SPAWN] Response status: {response.status}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        print(f"[SPAWN] ✅ Successfully spawned container for {channel_name}: {result.get('container_id')}")
                        return result.get('container_id')
                    except Exception as json_error:
                        print(f"[ERROR] Failed to parse JSON response: {json_error}")
                        return None
                else:
                    print(f"[ERROR] Failed to spawn container for {channel_name}: {response.status} - {response_text}")
                    return None
                    
    except Exception as e:
        print(f"[ERROR] Exception spawning container for {channel_name}: {e}")
        return None

# NEW: Separate media download worker (low priority, runs in background)
async def media_download_worker():
    """Background worker for downloading media files"""
    print("[MEDIA-WORKER] Started media download worker")
    while True:
        try:
            username, msg, client_ref = await media_download_queue.get()
            try:
                media_path = await download_media(username, msg, client_ref)
                print(f"[MEDIA-WORKER] Downloaded media for message {msg.id}")
            except Exception as e:
                print(f"[MEDIA-WORKER] Failed to download media for message {msg.id}: {e}")
            finally:
                media_download_queue.task_done()
                # Add delay to keep media downloads low priority
                await asyncio.sleep(2)
                
        except asyncio.CancelledError:
            print("[MEDIA-WORKER] Media worker cancelled")
            break
        except Exception as e:
            print(f"[ERROR] Media worker exception: {e}")
            await asyncio.sleep(5)

async def scrape_channel(channel_name: str, channel_info: dict):
    try:
        entity, clean_name = await get_entity_safe(channel_name)
        if not entity:
            print(f"[ERROR] Could not resolve entity for scraping: {channel_name}")
            return
            
        last_id = channel_info.get("last_id", 0)
        new_max_id = last_id

        async for msg in client.iter_messages(entity, min_id=last_id, reverse=True):
            if not msg.message:
                continue
            sender = await msg.get_sender()
            
            # PRIORITY 1: Save message text immediately (no media)
            await save_message_if_new(msg.chat_id, clean_name, msg, sender, None)
            
            # PRIORITY 2: Queue media download for later (non-blocking)
            if msg.media:
                await media_download_queue.put((clean_name, msg, client))
            
            new_max_id = max(new_max_id, msg.id)

        if new_max_id > last_id:
            channel_info["last_id"] = new_max_id
            print(f"[SCRAPE] Updated last_id for {clean_name}: {new_max_id}")
        else:
            print(f"[SCRAPE] No new messages for {clean_name}")

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

# OPTIMIZED: Fast streaming backfill focused on text extraction and link discovery
async def _streaming_backfill(channel_entity, channel_id, username, recursive: bool, visited: set):
    """Process messages as a stream, prioritizing text and link extraction"""
    message_count = 0
    processed_links = set()
    
    print(f"[STREAM] Starting backfill for {username}")
    
    async for m in client.iter_messages(channel_entity, reverse=True):
        if not hasattr(m, 'message') or not m.message:
            continue
            
        message_count += 1
        
        # PRIORITY 1: Extract invite links IMMEDIATELY from each message
        if recursive and m.message:
            print(f"[DEBUG] Checking message {message_count} for links: {m.message[:100]}...")
            links = extract_invite_links([m.message])
            print(f"[DEBUG] Extracted {len(links)} links: {links}")
            
            for link in links:
                print(f"[DEBUG] Processing link: {link}")
                # NEW: Skip self-references
                if is_self_reference(link, username):
                    print(f"[SKIP] Self-reference detected: {link} (current: {username})")
                    continue
                    
                if link not in processed_links:
                    processed_links.add(link)
                    # HIGH PRIORITY: Add to global queue for immediate processing
                    await invite_queue.put((link, visited))
                    print(f"[STREAM] 🚀 Found NEW invite link in message {message_count}: {link}")
                else:
                    print(f"[SKIP] Already processed link: {link}")
        
        # PRIORITY 2: Save message text immediately (fast operation)
        async def process_message_fast(msg):
            try:
                await ensure_rate_limit()
                sender = await msg.get_sender()
                # Save message WITHOUT media first (fast)
                await save_message_if_new(msg.chat_id, username, msg, sender, None)
                
                # PRIORITY 3: Queue media download for later (non-blocking)
                if msg.media:
                    await media_download_queue.put((username, msg, client))
                    
            except Exception as e:
                print(f"[ERROR] Failed to process message {msg.id}: {e}")
        
        # Fire and forget - don't wait for anything
        asyncio.create_task(process_message_fast(m))
        
        # REDUCED batching - process more messages before yielding
        if message_count % MESSAGE_BATCH_SIZE == 0:
            await asyncio.sleep(MESSAGE_BATCH_DELAY)
        
        # Progress updates
        if message_count % 100 == 0:  # Less frequent updates
            print(f"[STREAM] Processed {message_count} messages from {username}, found {len(processed_links)} unique links")
            await asyncio.sleep(0.1)  # Minimal break
    
    print(f"[STREAM] ✅ Processed {message_count} messages from {username}, discovered {len(processed_links)} unique channels")
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
            
            # PRIORITY: Save text immediately, queue media for later
            await save_message_if_new(evt.chat_id, username, evt, sender, None)
            if evt.media:
                await media_download_queue.put((username, evt, client))
                
            print(f"[DB] Message saved for chat {evt.chat_id}, user {username}")
        except Exception as e:
            print(f"[ERROR] Failed to process live message: {e}")

    print("[DEBUG] NewMessage handler attached.")
    await start_short_polling(channels)
    await client.run_until_disconnected()

# HIGH PRIORITY: Worker that processes invite links and spawns containers
async def invite_link_worker():
    """Continuously process invite links from the queue with HIGH PRIORITY"""
    print("[INVITE-WORKER] 🚀 Started HIGH PRIORITY invite link worker")
    while True:
        try:
            print("[INVITE-WORKER] Waiting for invite links...")
            link, visited = await invite_queue.get()
            print(f"[INVITE-WORKER] 🔥 PRIORITY: Processing invite link: {link}")
            
            if not client.is_connected():
                print("[INVITE-WORKER] Client disconnected, attempting to reconnect...")
                try:
                    await client.connect()
                    await asyncio.sleep(2)
                except Exception as conn_error:
                    print(f"[INVITE-WORKER] Reconnection failed: {conn_error}")
                    await invite_queue.put((link, visited))
                    await asyncio.sleep(30)
                    continue
            
            joined_username = await try_join_invite_link(link)
            if joined_username and joined_username not in visited:
                print(f"[INVITE-WORKER] 🚀 HIGH PRIORITY: Spawning container for: {joined_username}")
                container_id = await spawn_container_for_channel(joined_username)
                if container_id:
                    visited.add(joined_username)
                    print(f"[CONTAINER] ✅ Successfully spawned container {container_id} for {joined_username}")
                    print(f"[CONTAINER] 🎯 NEW CHANNEL WILL BE SCRAPED IN SEPARATE CONTAINER!")
                else:
                    print(f"[FAILED] ❌ Could not spawn container for {joined_username}")
                    print(f"[FALLBACK] Adding {joined_username} to local queue as fallback")
                    # FALLBACK: Only add to local queue if container spawning failed
                    await channel_queue.put(joined_username)
            elif joined_username:
                print(f"[SKIP] Already processed {joined_username}")
            else:
                print(f"[FAILED] Could not join channel from link: {link}")
            
            invite_queue.task_done()
            print(f"[INVITE-WORKER] ✅ Finished processing {link}")
            
            # Minimal delay for high priority processing
            await asyncio.sleep(2)
            
        except asyncio.CancelledError:
            print("[INVITE-WORKER] Worker cancelled")
            break
        except Exception as e:
            print(f"[ERROR] Invite worker exception: {e}")
            await asyncio.sleep(5)

channel_queue = asyncio.Queue()

async def channel_worker(visited: set, recursive: bool, skip_history: bool, live_channels: list):
    """Worker that processes channels from the queue asynchronously"""
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
                        print(f"[ERROR] Could not resolve entity for: {ch}")
                        continue
                    
                    print(f"[WORKER] Processing {ch} (resolved to: {clean_name})")
                    
                    if await is_scraped(clean_name):
                        print(f"[SKIP] Already scraped: {clean_name}")
                        live_channels.append(ch)
                    else:
                        if not skip_history:
                            # Use optimized streaming backfill
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
    print(f"[DEBUG] Logged in with recursive={recursive}, skip_history={skip_history}")
    
    visited = set()
    live_channels = []
    
    # Add initial channels to queue
    for ch in channels:
        await channel_queue.put(ch)
        print(f"[DEBUG] Added channel to queue: {ch}")
    
    async with client:
        workers = []
        
        # Channel processing workers
        for i in range(MAX_CONCURRENT_SCRAPERS):
            worker = asyncio.create_task(
                channel_worker(visited, recursive, skip_history, live_channels)
            )
            workers.append(worker)
        
        # HIGH PRIORITY: Invite link processing workers
        if recursive:
            print(f"[DEBUG] Starting {5} HIGH PRIORITY invite link workers")  # More workers
            for i in range(5):  # More workers for faster processing
                worker = asyncio.create_task(invite_link_worker())
                workers.append(worker)
        
        # LOW PRIORITY: Media download workers (background)
        print(f"[DEBUG] Starting {2} LOW PRIORITY media download workers")
        for i in range(2):  # Fewer media workers
            worker = asyncio.create_task(media_download_worker())
            workers.append(worker)
        
        # Monitor queues with more frequent updates
        while not channel_queue.empty() or not invite_queue.empty():
            await asyncio.sleep(2)  # Check every 2 seconds
            invite_count = invite_queue.qsize()
            channel_count = channel_queue.qsize()
            media_count = media_download_queue.qsize()
            print(f"[STATUS] 📊 Channels: {channel_count}, 🚀 Invites: {invite_count}, 📷 Media: {media_count}")
            
            # DEBUG: Show what channels are in the queue
            if channel_count > 0:
                print(f"[DEBUG] Channels in queue waiting to be processed locally")
            if invite_count > 0:
                print(f"[DEBUG] Invite links waiting to spawn new containers")
                
        print("[STATUS] ✅ All initial channels processed and all invite links spawned as containers")
        
        # Give more time for final processing
        await asyncio.sleep(15)
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)
        
        # Start live listening
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