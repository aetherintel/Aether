import os, json, sys, asyncio
from telegram_job.similar import similar_channels_flexible as similar_channels
from telegram_job.scraper import run_scraper, run_live_listener_only
from telegram_job.neo4j_client import write_recommendations, is_scraped
from telegram_job.telegram_client import login

MODE = os.getenv("MODE", "similar").strip()        # "similar" | "scrape" | "full" | "live"
CHANNELS     = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c]
SESSION_NAME = os.getenv("SESSION_NAME", "default")
RECURSIVE    = os.getenv("RECURSIVE", "0") == "1"  # Enable recursion
NEO4J_WRITE  = os.getenv("NEO4J_WRITE", "0") == "1"
SKIP_HISTORY = os.getenv("SKIP_HISTORY", "0") == "1"

async def main():
    if not MODE:
        sys.exit("MODE environment variable is required")
    await login()

    if not CHANNELS:
        print("[]")
        return

    print(f"[DEBUG] MODE={MODE!r}")
    print(f"[DEBUG] CHANNELS={CHANNELS!r}")

    if MODE == "similar":
        root = CHANNELS[0]
        if await is_scraped(root):
            print(f"[SKIP] {root} already has messages. Skipping.")
            return

        print(f"[SIMILAR] Finding channels related to: {root}")
        recs = await similar_channels(root)
        print(json.dumps(recs, ensure_ascii=False))

        if NEO4J_WRITE:
            await write_recommendations(root, recs)

        usernames = [c["username"] for c in recs if c.get("username")]
        if usernames:
            print(f"[SCRAPE] Scraping similar channels: {usernames}")
            await run_scraper(usernames, SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)

    elif MODE == "scrape":
        for ch in CHANNELS:
            if await is_scraped(ch):
                print(f"[SKIP] {ch} already has messages.")
                continue
            await run_scraper([ch], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)

    elif MODE == "full":
        for root in CHANNELS:
            if await is_scraped(root):
                print(f"[SKIP] {root} already has messages.")
                continue

            print(f"[SCRAPE] Scraping initial: {root}")
            await run_scraper([root], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)

            print(f"[SIMILAR] Finding similar to: {root}")
            recs = await similar_channels(root)
            if NEO4J_WRITE:
                await write_recommendations(root, recs)

            usernames = [c["username"] for c in recs if c.get("username")]
            if usernames:
                await run_scraper(usernames, SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)

    elif MODE == "live":
        print("[LIVE] Listening for new messages only...")
        await run_live_listener_only(CHANNELS)

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
