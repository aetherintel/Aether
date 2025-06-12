import os, json
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

load_dotenv()

API_ID       = int(os.getenv("TG_API_ID"))
API_HASH     = os.getenv("TG_API_HASH")
PHONE        = os.getenv("TG_PHONE")
SESSION_STRING = os.getenv("SESSION_STRING")


client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def login():
    await client.connect()
    if await client.is_user_authorized():
        return
