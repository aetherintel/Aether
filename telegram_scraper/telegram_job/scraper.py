import asyncio
from telethon import events
from telegram_job.telegram_client import client, login
from telegram_job.neo4j_client import save_message

async def _historic_backfill(channels):
    for ch in channels:
        async for m in client.iter_messages(ch, reverse=True):
            sender = await m.get_sender()
            await save_message(ch, m, sender)

async def _live_listener(channels):
    @client.on(events.NewMessage(chats=channels))
    async def handler(evt):
        sender = await evt.message.get_sender()
        await save_message(evt.chat_id, evt.message, sender)
    await client.run_until_disconnected()

async def run_scraper(channels, _session_name):
    await login()
    async with client:
        await _historic_backfill(channels)
        await _live_listener(channels)   # blocks forever
