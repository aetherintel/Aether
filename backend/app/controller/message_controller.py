from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from telegram_job.neo4j_client import (
    get_channel_list,
    get_messages_for_channel,
    get_channel_by_id
)

router = APIRouter(prefix="/messages", tags=["messages"])

class Author(BaseModel):
    id: str
    name: str

class Channel(BaseModel):
    id: str
    username: str

class Message(BaseModel):
    message_id: str
    text: str
    date: datetime
    media_type: Optional[str]
    reply_to_id: Optional[str]
    author: Author
    channel: Channel

class ChannelDetail(BaseModel):
    channel_id: str
    username: str
    title: str
    message_count: int
    first_message: Optional[datetime]
    last_message: Optional[datetime]
    recommends_count: int
    recommended_by_count: int
    is_scraped: bool
    scraped_at: Optional[datetime]

class ChannelListItem(BaseModel):
    channel_id: str
    username: str
    title: str
    message_count: int
    last_active: Optional[datetime]
    recommended_by: int
    is_scraped: bool
    scraped_at: Optional[datetime]

@router.get("/channels", response_model=List[ChannelListItem])
async def list_channels():
    try:
        channels = await get_channel_list()
        return channels
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Channel-Liste: {str(e)}")

@router.get("/channels/{channel_id}", response_model=ChannelDetail)
async def get_channel_details(channel_id: str):
    try:
        channel = await get_channel_by_id(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} nicht gefunden")
        return channel
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Channel-Details: {str(e)}")

@router.get("/channels/{channel_id}/messages", response_model=List[Message])
async def get_channel_messages(
    channel_id: str,
    limit: int = Query(default=100, ge=1, le=1000)
):
    try:
        messages = await get_messages_for_channel(channel_id, limit)
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Nachrichten: {str(e)}")