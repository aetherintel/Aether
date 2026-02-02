import asyncio
import os
from telethon import events
from .telegram_client import get_client, login
from .telegram_client import get_client, login
from aether_lib.neo4j_client.channels import is_scraped, mark_scraped, get_latest_message_id
from .message_processor import process_message

# Configuration
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))
MESSAGE_BATCH_SIZE = int(os.getenv("MESSAGE_BATCH_SIZE", "500"))
MESSAGE_BATCH_DELAY = float(os.getenv("MESSAGE_BATCH_DELAY", "0.05"))
MAX_PARALLEL_SCRAPERS = int(os.getenv("MAX_PARALLEL_SCRAPERS", "4"))

config = {}

def reload_scraper_config():
    global config
    config = {
        'ENABLE_TRANSLATION': os.getenv('ENABLE_TRANSLATION', '1') == '1',
        'ENABLE_IMAGE_ANALYSIS': os.getenv('ENABLE_IMAGE_ANALYSIS', '1') == '1',
        'ENABLE_AUDIO_TRANSCRIPTION': os.getenv('ENABLE_AUDIO_TRANSCRIPTION', '1') == '1',
        'ENABLE_EMOTION_ANALYSIS': os.getenv('ENABLE_EMOTION_ANALYSIS', '1') == '1',
        'ENABLE_LABEL_CLASSIFIER': os.getenv('ENABLE_LABEL_CLASSIFIER', '1') == '1',
        'ENABLE_GEOLOCATION_EXTRACTION': os.getenv('ENABLE_GEOLOCATION_EXTRACTION', '1') == '1',
        'ENABLE_LIVE_MONITORING': os.getenv('ENABLE_LIVE_MONITORING', '0') == '1',
        'RATE_LIMIT_DELAY': RATE_LIMIT_DELAY
    }
    print(f"[CONFIG] Reloaded scraper config: {config}", flush=True)

reload_scraper_config()

processing_channels = set()
found_channels_queue = None
scraper_semaphore = None
all_seen_channels = set()

def init_scraper_state():
    global found_channels_queue, scraper_semaphore
    found_channels_queue = asyncio.Queue()
    scraper_semaphore = asyncio.Semaphore(MAX_PARALLEL_SCRAPERS)


async def get_entity_safe(identifier):
    try:
        if isinstance(identifier, str) and (identifier.lstrip('-').isdigit()):
            entity = await get_client().get_entity(int(identifier))
        else:
            entity = await get_client().get_entity(identifier)
        clean_name = getattr(entity, 'username', None) or str(entity.id)
        # print(f"[DEBUG] Resolved {identifier} -> {clean_name}", flush=True)
        return entity, clean_name
    except Exception as e:
        print(f"[ERROR] Could not resolve entity '{identifier}': {e}", flush=True)
        return None, None

async def scrape_channel_complete(channel_name, recursive=False, case_id=None, owner_id=None):
    async with scraper_semaphore:
        try:
            entity, clean_name = await get_entity_safe(channel_name)
            if not entity:
                print(f"[SCRAPE] ❌ Entity not found for {channel_name}", flush=True)
                return set()
            
            # Incremental Scraping Logic
            latest_id = await get_latest_message_id(clean_name)
            min_id = 0
            if latest_id:
                print(f"[SCRAPE] 🔄 Found existing messages for {clean_name}, latest ID: {latest_id}. Resuming scrape...", flush=True)
                min_id = latest_id
            else:
                print(f"[SCRAPE] 🆕 No existing messages for {clean_name}. Starting full scrape...", flush=True)

            print(f"[SCRAPE] Starting scrape of {clean_name} (min_id={min_id})", flush=True)
            found_channels, message_count = set(), 0
            
            # If min_id > 0, we can use reverse=True to get oldest-newest from that point, 
            # OR just default latest-first.
            # Telethon's iter_messages with min_id gets messages NEWER than min_id.
            
            async for msg in get_client().iter_messages(entity, min_id=min_id, reverse=True):
                if not msg.message and not msg.media: continue
                message_count += 1
                await process_message(msg, clean_name, found_channels, all_seen_channels, found_channels_queue, config, recursive, case_id, owner_id=owner_id)
                if message_count % MESSAGE_BATCH_SIZE == 0: await asyncio.sleep(MESSAGE_BATCH_DELAY)
            
            # Only mark as fully scraped if we did a full scrape (min_id=0) or successfully updated
            # Actually we probably want to track "last scraped" timestamp regardless
            if min_id == 0:
                await mark_scraped(clean_name)
                
            print(f"[SCRAPE] ✅ {clean_name}: Completed scrape with {message_count} messages", flush=True)
            return found_channels
        except Exception as e:
            print(f"[ERROR] Failed to scrape channel {channel_name}: {e}")
            return set()

async def try_join_channel(channel_name):
    try:
        if '+' in channel_name:
            from telethon.tl.functions.messages import ImportChatInviteRequest
            result = await get_client()(ImportChatInviteRequest(channel_name.split('+')[-1]))
            joined = result.chats[0]
            return getattr(joined, 'username', None) or str(joined.id)
        entity, clean_name = await get_entity_safe(channel_name)
        res = clean_name if entity else None
        print(f"[JOIN] Joining {channel_name} -> {res} (Identity verified: {entity is not None})", flush=True)
        return res
    except Exception as e:
        print(f"[JOIN] ❌ Failed to join {channel_name}: {e}", flush=True)
    return None

async def channel_processor(recursive=False, case_id=None, owner_id=None):
    print(f"[WORKER] Channel processor started", flush=True)
    while True:
        try:
            channel_name, source_channel = await found_channels_queue.get()
            print(f"[WORKER] Picked up channel: {channel_name}", flush=True)
            if channel_name in processing_channels:
                print(f"[WORKER] Skip {channel_name} (already processing)", flush=True)
                found_channels_queue.task_done()
                continue
            processing_channels.add(channel_name)
            try:
                actual_name = await try_join_channel(channel_name)
                if actual_name:
                    if source_channel:
                        try:
                            from aether_lib.neo4j_client.channels import write_recommendations
                            await write_recommendations(source_channel, [{"id": actual_name, "username": actual_name, "title": None}])
                        except Exception as e:
                            print(f"[ERROR] Recommendation failed: {source_channel} -> {actual_name}: {e}")
                    await scrape_channel_complete(actual_name, recursive, case_id, owner_id=owner_id)
            finally:
                processing_channels.discard(channel_name)
                found_channels_queue.task_done()
        except asyncio.CancelledError: break
        except Exception as e:
            print(f"[ERROR] Channel processor error: {e}")
            await asyncio.sleep(5)

async def run_parallel_scraper(channels, recursive=False, case_id=None, owner_id=None):
    print(f"[SCRAPER] Starting parallel scraper for {len(channels)} channels", flush=True)
    await login()
    for ch in channels:
        norm = ch.lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '').strip()
        all_seen_channels.add(norm)
        await found_channels_queue.put((norm, None))
    
    print(f"[SCRAPER] Queue populated. Entering client context...", flush=True)
    async with get_client():
        print(f"[SCRAPER] Client context entered. Spawning {MAX_PARALLEL_SCRAPERS} workers.", flush=True)
        workers = [asyncio.create_task(channel_processor(recursive, case_id, owner_id=owner_id)) for _ in range(MAX_PARALLEL_SCRAPERS)]
        
        while not found_channels_queue.empty() or processing_channels: 
             await asyncio.sleep(5)
        
        print("[SCRAPER] Queue empty. Cancelling workers...", flush=True)
        for worker in workers: worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    print("[SCRAPER] Parallel scraper finished.", flush=True)

async def run_live_monitor(channels, case_id=None, owner_id=None):
    await login()
    resolved = []
    for ch in channels:
        ent, name = await get_entity_safe(ch)
        if ent: resolved.append((ent, name))
    if not resolved: return
    
    @get_client().on(events.NewMessage(chats=[e for e, _ in resolved]))
    async def handle_new_message(event):
        channel_name = next((name for e, name in resolved if e.id == event.chat_id), None)
        if channel_name:
            await process_message(event.message, channel_name, set(), all_seen_channels, found_channels_queue, config, False, case_id, owner_id=owner_id)
    
    async with get_client():
        while True: await asyncio.sleep(60)

async def run_scraper(channels, _session_name, recursive=False, skip_history=False, case_id=None, owner_id=None):
    if skip_history: 
        print("[RUN] Skip history=True, starting live monitor directly", flush=True)
        await run_live_monitor(channels, case_id, owner_id=owner_id)
    else:
        print("[RUN] Running parallel scraper...", flush=True)
        await run_parallel_scraper(channels, recursive, case_id, owner_id=owner_id)
        # Only start live monitor if explicitly enabled
        if config.get('ENABLE_LIVE_MONITORING', False):
            print("[RUN] Live monitoring ENABLED. Starting live monitor...", flush=True)
            await run_live_monitor(channels, case_id, owner_id=owner_id)
        else:
            print("[RUN] Live monitoring DISABLED. Job complete.", flush=True)

async def run_live_listener_only(channels, case_id=None, owner_id=None):
    await run_live_monitor(channels, case_id, owner_id=owner_id)