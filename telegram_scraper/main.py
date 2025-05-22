# main.py
import asyncio
from telegram_job import telegram_client
from telegram_job.neo4j_client import close as close_neo4j

CHANNELS = ["insider_nachrichten"]   # …your list…

async def main():
    try:
        # 1️⃣  Telegram login & scrape
        await telegram_client.login()
        async with telegram_client.client:
            for channel in CHANNELS:
                print(f"Scraping channel: {channel}")
                await telegram_client.scrape_channel(channel)
    finally:
        # 2️⃣  always close the Neo4j driver *in the same loop*
        await close_neo4j()

if __name__ == "__main__":
    asyncio.run(main())   # ← exactly one event-loop for everything
