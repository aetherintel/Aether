import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")

_client = None

def get_client():
    """Get the initialized Telegram client"""
    if _client is None:
        raise RuntimeError("Client not initialized. Call login() first.")
    return _client

async def login(session_string=None):
    global _client
    
    if _client is not None and _client.is_connected():
        print("[LOGIN] Client already connected. Reusing existing client.", flush=True)
        return

    if not session_string:
        session_string = os.getenv("SESSION_STRING")
    
    if not session_string:
        raise ValueError("session_string is required")
    
    _client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    
    await _client.connect()
    print("Connected to Telegram successfully.")
    
    if not await _client.is_user_authorized():
        raise ValueError("Session string is invalid or expired")