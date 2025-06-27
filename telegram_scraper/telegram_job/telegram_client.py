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
    if not SESSION_STRING:
        raise ValueError("SESSION_STRING environment variable is required but not set.")
    try:
        await client.connect()
        print("Connected to Telegram successfully.")
    except Exception as e:
        print(f"Failed to connect: {e}")
        raise e
    if await client.is_user_authorized():
        return
