import os
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

load_dotenv()

API_ID       = int(os.getenv("TG_API_ID"))
API_HASH     = os.getenv("TG_API_HASH")
PHONE        = os.getenv("TG_PHONE")
SESSION_NAME = os.getenv("SESSION_NAME", "default")

# session file lives in /app/session/<SESSION_NAME>.session
SESSION_PATH = Path("/app/session") / SESSION_NAME

client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)

async def login():
    await client.connect()
    if await client.is_user_authorized():
        return

    # Interactive fallback (only first run)
    await client.send_code_request(PHONE)
    code = input("Telegram authentication code: ")
    try:
        await client.sign_in(PHONE, code)
    except SessionPasswordNeededError:
        pwd = input("Two-step verification password: ")
        await client.sign_in(password=pwd)
