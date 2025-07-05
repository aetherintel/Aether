print("[DEBUG] entry.py loaded.")

import os, json, sys, asyncio
from similar import similar_channels_flexible as similar_channels
from scraper import run_scraper, run_live_listener_only
from neo4j_client import write_recommendations, is_scraped
from telegram_client import login

# MODE
MODE = os.getenv("MODE", "similar").strip()        # "similar" | "scrape" | "full" | "live"

# CHANNELS
CHANNELS_RAW = os.getenv("CHANNELS", "")
CHANNELS = [c.strip() for c in CHANNELS_RAW.split(",") if c]

# SESSION_NAME
SESSION_NAME = os.getenv("SESSION_NAME", "default")

# SESSION_STRING
SESSION_STRING = os.getenv("SESSION_STRING")
if not SESSION_STRING:
    raise ValueError("SESSION_STRING environment variable is required but not set.")

# RECURSIVE
RECURSIVE = os.getenv("RECURSIVE", "0") == "1"

# NEO4J_WRITE
NEO4J_WRITE = os.getenv("NEO4J_WRITE", "0") == "1"

# SKIP_HISTORY
SKIP_HISTORY = os.getenv("SKIP_HISTORY", "0") == "1"

async def main():
    if not MODE:
        sys.exit("MODE environment variable is required")
    await login()

    if not CHANNELS:
        print("[]")
        return

    if MODE == "similar":
        root = CHANNELS[0]
        if await is_scraped(root):
            return

        recs = await similar_channels(root)
        print(json.dumps(recs, ensure_ascii=False))

        if NEO4J_WRITE:
            await write_recommendations(root, recs)

        usernames = [c["username"] for c in recs if c.get("username")]
        if usernames:
            await run_scraper(usernames, SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)

    elif MODE == "scrape":
        for ch in CHANNELS:
            if await is_scraped(ch):
                continue
            await run_scraper([ch], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)

    elif MODE == "full":
        for root in CHANNELS:
            if await is_scraped(root):
                print(f"[SKIP] Channel {root} already scraped, skipping...")
                continue
            
            # Step 1: Scrape the root channel (with recursive container spawning)
            await run_scraper([root], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)

            # Step 2: Find similar channels and scrape them (without recursion to avoid exponential growth)
            recs = await similar_channels(root)
            if NEO4J_WRITE:
                await write_recommendations(root, recs)

            usernames = [c["username"] for c in recs if c.get("username")]
            if usernames:
                await run_scraper(usernames, SESSION_NAME, recursive=False, skip_history=SKIP_HISTORY)
    
    elif MODE == "live":
        print("[LIVE] Listening for new messages only...")
        try:
            await run_live_listener_only(CHANNELS)
        except Exception as e:
            print("[ERROR] Exception in live listener:", e)
            import traceback
            traceback.print_exc()
        print("[DEBUG] Live listener finished.")
    else:
        print(f"[ERROR] Unknown MODE: {MODE!r}")
        sys.exit("unknown MODE")

if __name__ == "__main__":
    try:
        print("[START] Starting Telegram scraper job...")
        asyncio.run(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)