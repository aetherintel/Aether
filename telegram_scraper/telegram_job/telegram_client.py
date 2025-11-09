import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")

client = None  # Global client wird später initialisiert

async def login(session_string=None):
    """Initialize and connect Telegram client with session string"""
    global client
    
    if not session_string:
        session_string = os.getenv("SESSION_STRING")
    
    if not session_string:
        raise ValueError("session_string is required")
    
    # Create client with provided session string
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    
    try:
        await client.connect()
        print("Connected to Telegram successfully.")
        
        if not await client.is_user_authorized():
            raise ValueError("Session string is invalid or expired")
            
    except Exception as e:
        print(f"Failed to connect: {e}")
        raise e