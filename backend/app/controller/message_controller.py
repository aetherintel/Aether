from datetime import datetime
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/messages", tags=["messages"])

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
