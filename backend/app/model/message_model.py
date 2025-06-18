from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Author(BaseModel):
    id: int
    name: str

class Channel(BaseModel):
    id: str
    username: str

class Message(BaseModel):
    message_id: str
    text: str
    date: datetime
    media_type: Optional[str]
    media_path: Optional[str]
    reply_to_id: Optional[str]
    author: Author
    channel: Channel

class ChannelDetail(BaseModel):
    channel_id: str
    username: str
    title: Optional[str]
    message_count: int
    first_message: Optional[datetime]
    last_message: Optional[datetime]
    recommends_count: int
    recommended_by_count: int
    is_scraped: Optional[bool]
    scraped_at: Optional[datetime]

class ChannelListItem(BaseModel):
    channel_id: str
    username: str
    title: Optional[str]
    message_count: int
    last_active: Optional[datetime] = Field(alias="last_message_date")
    recommended_by: int
    is_scraped: Optional[bool]
    scraped_at: Optional[datetime]

    class Config:
        allow_population_by_field_name = True