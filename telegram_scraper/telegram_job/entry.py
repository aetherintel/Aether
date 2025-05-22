import os, json, sys, asyncio
from telegram_job.similar import similar_channels_flexible as similar_channels
from telegram_job.scraper import run_scraper
from telegram_job.neo4j_client import write_recommendations
from telegram_job.telegram_client import login

MODE         = os.getenv("MODE", "similar")      # "similar" | "scrape"
CHANNELS     = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c]
SESSION_NAME = os.getenv("SESSION_NAME", "default")

async def main():
    # 1️⃣  Telegram login
    await login()
    if MODE == "similar":
        if not CHANNELS:
            print("[]")
            return
        res = await similar_channels(CHANNELS[0])
        print(json.dumps(res, ensure_ascii=False))
        if os.getenv("NEO4J_WRITE") == "1":
            await write_recommendations(CHANNELS[0], res)
    elif MODE == "scrape":
        if not CHANNELS:
            sys.exit("scrape mode requires CHANNELS")
        await run_scraper(CHANNELS, SESSION_NAME)
    else:
        sys.exit("unknown MODE")

if __name__ == "__main__":
    asyncio.run(main())
