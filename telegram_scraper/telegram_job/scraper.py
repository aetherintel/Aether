import asyncio
from pathlib import Path
import os
import time
from telethon import events
from telegram_client import client, login
from neo4j_client import save_message_if_new, is_scraped, mark_scraped
from utils import download_media_to_path, extract_invite_links, generate_media_path, get_media_type

# Configuration
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))
MESSAGE_BATCH_SIZE = int(os.getenv("MESSAGE_BATCH_SIZE", "500"))
MESSAGE_BATCH_DELAY = float(os.getenv("MESSAGE_BATCH_DELAY", "0.05"))
MAX_PARALLEL_SCRAPERS = int(os.getenv("MAX_PARALLEL_SCRAPERS", "4"))

# Global state for parallel processing
processing_channels = set()
found_channels_queue = asyncio.Queue()
scraper_semaphore = asyncio.Semaphore(MAX_PARALLEL_SCRAPERS)
# FIX: Track all channels we've seen to prevent duplicates
all_seen_channels = set()

async def get_entity_safe(identifier):
    """Safely get a Telegram entity"""
    try:
        if isinstance(identifier, str) and (identifier.lstrip('-').isdigit()):
            chat_id = int(identifier)
            entity = await client.get_entity(chat_id)
        else:
            entity = await client.get_entity(identifier)
        
        clean_name = getattr(entity, 'username', None) or str(entity.id)
        print(f"[ENTITY] Resolved {identifier} to: {clean_name}")
        return entity, clean_name
    except Exception as e:
        print(f"[ERROR] Could not resolve entity '{identifier}': {e}")
        return None, None

async def process_message(msg, username, found_channels, recursive=False):
    """Process a single message: save it, download media, find channels"""
    try:
        # Skip service messages
        if hasattr(msg, 'action') and msg.action is not None:
            return
            
        # Rate limiting
        await asyncio.sleep(RATE_LIMIT_DELAY)
        
        # Get sender
        sender = await msg.get_sender()
        
        # Handle media download
        media_path = None
        if msg.media:
            media_type = get_media_type(msg.media)
            if media_type in ["photo", "video", "document"]:
                media_path = generate_media_path(username, msg.id, media_type, msg)
                
                if media_path:
                    # Download immediately
                    try:
                        os.makedirs(os.path.dirname(media_path), exist_ok=True)
                        if not os.path.exists(media_path):
                            print(f"[DOWNLOAD] {username}: Downloading media for message {msg.id}")
                            await download_media_to_path(username, msg, client, media_path)
                        # Silent if exists
                    except Exception as e:
                        print(f"[ERROR] {username}: Failed to download media for message {msg.id}: {e}")
        
        # Save message to Neo4j
        await save_message_if_new(msg.chat_id, username, msg, sender, media_path)
        
        # Extract invite links for recursive processing
        if recursive and msg.message:
            links = extract_invite_links([msg.message])
            for link in links:
                # Normalize link
                normalized_link = link.lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '').strip()
                
                # Skip self-references
                if normalized_link == username.lower():
                    continue
                    
                # FIX: Check global seen channels to prevent duplicates
                if normalized_link not in all_seen_channels:
                    all_seen_channels.add(normalized_link)
                    found_channels.add(normalized_link)
                    print(f"[FOUND] {username}: New channel from message {msg.id}: {normalized_link}")
                    # FIX: Use current channel (username) as source, not original channel
                    await found_channels_queue.put((normalized_link, username))
                else:
                    print(f"[DUPLICATE] {username}: Channel {normalized_link} already seen, skipping")
        
    except Exception as e:
        print(f"[ERROR] {username}: Failed to process message {msg.id}: {e}")

async def scrape_channel_complete(channel_name, recursive=False):
    """Scrape a channel completely: all messages, media, and find new channels"""
    # Use semaphore to limit concurrent scrapers
    async with scraper_semaphore:
        try:
            entity, clean_name = await get_entity_safe(channel_name)
            if not entity:
                return set()
                
            # Check if already scraped
            if await is_scraped(clean_name):
                print(f"[SKIP] {clean_name} already scraped")
                return set()
            
            print(f"[SCRAPE] Starting complete scrape of {clean_name}")
            
            found_channels = set()
            message_count = 0
            
            # Process ALL messages in the channel
            async for msg in client.iter_messages(entity, reverse=True):
                # Skip empty messages
                if not msg.message and not msg.media:
                    continue
                    
                message_count += 1
                
                # Process message: save, download media, find channels
                # FIX: Channels are added to queue immediately in process_message!
                await process_message(msg, clean_name, found_channels, recursive)
                
                # Rate limiting
                if message_count % MESSAGE_BATCH_SIZE == 0:
                    await asyncio.sleep(MESSAGE_BATCH_DELAY)
                
                if message_count % 100 == 0:
                    print(f"[SCRAPE] {clean_name}: Processed {message_count} messages")
                    await asyncio.sleep(0.1)
            
            # Mark as scraped
            await mark_scraped(clean_name)
            print(f"[SCRAPE] ✅ {clean_name}: Completed scrape with {message_count} messages")
            
            if recursive and found_channels:
                print(f"[SCRAPE] {clean_name}: Found {len(found_channels)} new channels total")
                # Channels were already added to queue during processing!
            
            return found_channels
            
        except Exception as e:
            print(f"[ERROR] Failed to scrape channel {channel_name}: {e}")
            return set()

async def try_join_channel(channel_name):
    """Try to join a channel by invite link"""
    try:
        print(f"[JOIN] Trying to join: {channel_name}")
        
        # If it's an invite link, extract the slug
        if '+' in channel_name:
            slug = channel_name.split('+')[-1]
            from telethon.tl.functions.messages import ImportChatInviteRequest
            result = await client(ImportChatInviteRequest(slug))
            joined = result.chats[0]
            username = getattr(joined, 'username', None) or str(joined.id)
            print(f"[JOIN] ✅ Joined via invite: {username}")
            return username
        else:
            # Try to get entity directly
            entity, clean_name = await get_entity_safe(channel_name)
            if entity:
                print(f"[JOIN] ✅ Access to channel: {clean_name}")
                return clean_name
            
    except Exception as e:
        print(f"[JOIN] ❌ Failed to join {channel_name}: {e}")
        
    return None

async def channel_processor(recursive=False):
    """Process channels from the queue in parallel"""
    while True:
        try:
            # Get next channel from queue
            queue_item = await found_channels_queue.get()
            
            # Handle both old format (string) and new format (tuple)
            if isinstance(queue_item, tuple):
                channel_name, source_channel = queue_item
            else:
                channel_name = queue_item
                source_channel = None
            
            print(f"[DEBUG] Processing: {channel_name}, source: {source_channel}")
            
            # FIX: Skip if already processing (double-check)
            if channel_name in processing_channels:
                print(f"[SKIP] {channel_name} already being processed")
                found_channels_queue.task_done()
                continue
            
            processing_channels.add(channel_name)
            
            try:
                # Try to join/access channel
                actual_name = await try_join_channel(channel_name)
                if actual_name:
                    # FIX: Write recommendation relationship if we have source channel
                    if source_channel:
                        try:
                            from neo4j_client import write_recommendations
                            print(f"[RECOMMEND] Creating relationship: {source_channel} -> {actual_name}")
                            
                            # Create recommendation record
                            rec_data = [{
                                "id": actual_name,  # Use actual name as ID
                                "username": actual_name,
                                "title": None  # Will be set during scraping
                            }]
                            
                            await write_recommendations(source_channel, rec_data)
                            print(f"[RECOMMEND] ✅ Created relationship: {source_channel} -> {actual_name}")
                            
                        except Exception as e:
                            print(f"[ERROR] Failed to create recommendation: {source_channel} -> {actual_name}: {e}")
                    else:
                        print(f"[DEBUG] No source channel for {actual_name}, skipping recommendation")
                    
                    # Scrape the channel
                    await scrape_channel_complete(actual_name, recursive)
                
            finally:
                processing_channels.discard(channel_name)
                found_channels_queue.task_done()
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ERROR] Channel processor error: {e}")
            await asyncio.sleep(5)

async def run_parallel_scraper(channels, recursive=False):
    """Parallel scraper with workers"""
    await login()
    
    print(f"[START] Parallel scraper: channels={channels}, recursive={recursive}")
    print(f"[START] Max parallel scrapers: {MAX_PARALLEL_SCRAPERS}")
    
    # FIX: Add initial channels to seen set and queue
    for ch in channels:
        normalized_ch = ch.lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '').strip()
        all_seen_channels.add(normalized_ch)
        await found_channels_queue.put((normalized_ch, None))  # No source for initial channels
    
    async with client:
        # Start channel processor workers
        workers = []
        for i in range(MAX_PARALLEL_SCRAPERS):
            worker = asyncio.create_task(channel_processor(recursive))
            workers.append(worker)
        
        # Monitor progress
        processed_count = 0
        while True:
            # Check if queue is empty and no channels are being processed
            if found_channels_queue.empty() and not processing_channels:
                print(f"[COMPLETE] ✅ All channels processed!")
                break
            
            # Status update
            current_processing = len(processing_channels)
            queue_size = found_channels_queue.qsize()
            total_seen = len(all_seen_channels)
            
            if current_processing > 0 or queue_size > 0:
                print(f"[STATUS] Processing: {current_processing}, Queue: {queue_size}, Total seen: {total_seen}")
            
            await asyncio.sleep(5)
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)
        
        print(f"[COMPLETE] ✅ Parallel scraping finished")

async def run_live_monitor(channels):
    """Simple live monitor for channels"""
    await login()
    
    print(f"[LIVE] Starting live monitor for {len(channels)} channels")
    
    resolved_entities = []
    for ch in channels:
        entity, clean_name = await get_entity_safe(ch)
        if entity:
            resolved_entities.append((entity, clean_name))
    
    if not resolved_entities:
        print("[LIVE] No valid channels to monitor")
        return
    
    # Set up live listener
    entities = [entity for entity, _ in resolved_entities]
    
    @client.on(events.NewMessage(chats=entities))
    async def handle_new_message(event):
        try:
            # Find the channel name
            channel_name = None
            for entity, name in resolved_entities:
                if entity.id == event.chat_id:
                    channel_name = name
                    break
            
            if not channel_name:
                return
                
            print(f"[LIVE] 📩 New message in {channel_name}")
            
            # Process the message
            await process_message(event, channel_name, set(), False)
            
        except Exception as e:
            print(f"[LIVE] Error processing message: {e}")
    
    print("[LIVE] ✅ Live monitor active")
    
    # Keep running
    async with client:
        while True:
            await asyncio.sleep(60)  # Check every minute
            print("[LIVE] Monitor running...")

# Main entry points
async def run_scraper(channels, _session_name, recursive=False, skip_history=False):
    """Main scraper entry point"""
    if skip_history:
        # Only live monitoring
        await run_live_monitor(channels)
    else:
        # Complete scraping in parallel
        await run_parallel_scraper(channels, recursive)
        
        # After scraping, start live monitoring
        print("[TRANSITION] Scraping complete, starting live monitor...")
        await run_live_monitor(channels)

async def run_live_listener_only(channels):
    """Only live listener"""
    await run_live_monitor(channels)