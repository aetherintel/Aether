from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

class CaseFileCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    postCount: Optional[int] = None
    tgchannels: List[str] = []
    topics: List[str] = []
    terms: List[str] = []
    thumbnails: List[str] = []
    duration: Optional[int] = None
    tg_session: Optional[str] = None
    scraper_mode: Optional[str] = "full"
    
    # Report Config in Create (optional)
    report_frequency: Optional[str] = "daily"
    report_sections: List[str] = ["stats", "charts", "messages"]

    # AI Worker Configuration
    enable_translation: bool = True
    enable_image_analysis: bool = True
    enable_audio_transcription: bool = True
    enable_emotion_analysis: bool = False
    enable_label_classifier: bool = False
    enable_geolocation_extraction: bool = False

class CaseFile(CaseFileCreate):
    id: int
    owner_id: str
    created_at: datetime
    archived: bool
    # Ensure these are included in response
    report_frequency: Optional[str] = "daily"
    report_sections: Optional[List[str]] = ["stats", "charts", "messages"]

    class Config:
        from_attributes = True

class ReportConfigUpdate(BaseModel):
    report_frequency: str
    report_sections: List[str]

class CaseFileCreateResponse(BaseModel):
    case: CaseFile
    scrapers_started: int
    scraper_error: Optional[str] = None
