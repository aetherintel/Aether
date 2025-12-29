import asyncio
import os
from telethon import events
from .telegram_client import get_client, login
from aether_lib.neo4j_client.channels import is_scraped, mark_scraped
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
        'RATE_LIMIT_DELAY': RATE_LIMIT_DELAY
    }
    print(f"[CONFIG] Reloaded scraper config: {config}")

reload_scraper_config()

processing_channels = set()
found_channels_queue = asyncio.Queue()
scraper_semaphore = asyncio.Semaphore(MAX_PARALLEL_SCRAPERS)
all_seen_channels = set()

async def get_entity_safe(identifier):
    try:
        if isinstance(identifier, str) and (identifier.lstrip('-').isdigit()):
            entity = await get_client().get_entity(int(identifier))
        else:
            entity = await get_client().get_entity(identifier)
        clean_name = getattr(entity, 'username', None) or str(entity.id)
        return entity, clean_name
    except Exception as e:
        print(f"[ERROR] Could not resolve entity '{identifier}': {e}")
        return None, None

async def scrape_channel_complete(channel_name, recursive=False, case_id=None, owner_id=None):
    async with scraper_semaphore:
        try:
            entity, clean_name = await get_entity_safe(channel_name)
            if not entity or await is_scraped(clean_name): return set()
            print(f"[SCRAPE] Starting complete scrape of {clean_name}")
            found_channels, message_count = set(), 0
            async for msg in get_client().iter_messages(entity, reverse=True):
                if not msg.message and not msg.media: continue
                message_count += 1
                await process_message(msg, clean_name, found_channels, all_seen_channels, found_channels_queue, config, recursive, case_id, owner_id=owner_id)
                if message_count % MESSAGE_BATCH_SIZE == 0: await asyncio.sleep(MESSAGE_BATCH_DELAY)
            await mark_scraped(clean_name)
            print(f"[SCRAPE] ✅ {clean_name}: Completed scrape with {message_count} messages")
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
        return clean_name if entity else None
    except Exception as e:
        print(f"[JOIN] ❌ Failed to join {channel_name}: {e}")
    return None

async def channel_processor(recursive=False, case_id=None, owner_id=None):
    while True:
        try:
            channel_name, source_channel = await found_channels_queue.get()
            if channel_name in processing_channels:
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
    await login()
    for ch in channels:
        norm = ch.lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '').strip()
        all_seen_channels.add(norm)
        await found_channels_queue.put((norm, None))
    async with get_client():
        workers = [asyncio.create_task(channel_processor(recursive, case_id, owner_id=owner_id)) for _ in range(MAX_PARALLEL_SCRAPERS)]
        while not found_channels_queue.empty() or processing_channels: await asyncio.sleep(5)
        for worker in workers: worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

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
    if skip_history: await run_live_monitor(channels, case_id, owner_id=owner_id)
    else:
        await run_parallel_scraper(channels, recursive, case_id, owner_id=owner_id)
        await run_live_monitor(channels, case_id, owner_id=owner_id)

async def run_live_listener_only(channels, case_id=None, owner_id=None):
    await run_live_monitor(channels, case_id, owner_id=owner_id)