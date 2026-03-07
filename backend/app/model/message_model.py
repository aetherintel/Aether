from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, root_validator


class Author(BaseModel):
    id: int
    name: str

class Channel(BaseModel):
    id: str
    username: str

class Message(BaseModel):
    message_id: str
    text: Optional[str] = None  # backward compatibility
    original_text: Optional[str] = None
    translated_text: Optional[str] = None
    original_language: Optional[str] = None
    translation_status: Optional[str] = None
    date: Optional[datetime] = None
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    reply_to_id: Optional[str] = None
    author: Author
    channel: Channel
    image_text: Optional[str] = None
    image_text_translated: Optional[str] = None
    audio_text: Optional[str] = None
    audio_text_translated: Optional[str] = None
    emotion: Optional[str] = None
    image_analysis_status: Optional[str] = None
    audio_transcription_status: Optional[str] = None
    classification_status: Optional[str] = None
    emotion_status: Optional[str] = None
    geolocation_status: Optional[str] = None


    @root_validator(pre=True)
    def check_message_id(values):
        if 'mid' in values and 'message_id' not in values:
            values['message_id'] = values['mid']
        return values

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
    username: Optional[str] = None
    title: Optional[str]
    message_count: int
    last_active: Optional[datetime] = Field(alias="last_message_date")
    recommended_by: int
    is_scraped: Optional[bool]
    scraped_at: Optional[datetime]

    class Config:
        allow_population_by_field_name = True