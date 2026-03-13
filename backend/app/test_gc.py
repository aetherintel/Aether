from fastapi import FastAPI
import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get("TG_API_ID", 0))
API_HASH = os.environ.get("TG_API_HASH", "")

app = FastAPI()
sessions = {}

class MyClient(TelegramClient):
    def __del__(self):
        print(">>> CLIENT GARBAGE COLLECTED! <<<")
        super().__del__()

@app.post("/start")
async def start():
    print(f"Using API_ID={API_ID}")
    client = MyClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    try:
        sent_code = await client.send_code_request("+49123456789")
    except Exception as e:
        pass
        
    sessions["client"] = client
    return {"status": "ok"}

@app.get("/status")
async def status():
    return {"connected": sessions["client"].is_connected() if "client" in sessions else False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
