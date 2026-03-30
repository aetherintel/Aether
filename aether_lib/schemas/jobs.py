from pydantic import BaseModel, Field
from typing import List, Optional, TypedDict

class BaseScrapePayload(BaseModel):
    """Base for all scraper jobs"""
    owner_id: str
    case_id: int

class TelegramJobPayload(BaseModel):
    channels: List[str] = Field(..., description="Telegram channels to scrape")
    session_name: str
    recursive: bool = False
    neo4j_write: bool = True
    owner_id: str
    case_id: int
    enable_translation: bool = False
    enable_image_analysis: bool = False
    enable_audio_transcription: bool = False
    enable_emotion_analysis: bool = False
    enable_label_classifier: bool = False
    enable_geolocation_extraction: bool = False

class TranslationJobPayload(BaseModel):
    message_id: str
    original_text: str
    source_language: str
    owner_id: str
    case_id: Optional[int] = None
    parent_job_id: Optional[str] = None
    image_text: bool = False
    audio_text: bool = False



class ExtendedScrapeRequest(BaseModel):
    channel: str
    tg_session: str
    recursive: bool = True
    neo4j: bool = True
    case_id: Optional[int] = None
    enable_translation: bool = True
    enable_image_analysis: bool = True
    enable_audio_transcription: bool = True
    enable_emotion_analysis: bool = False
    enable_label_classifier: bool = False
    enable_geolocation_extraction: bool = False

class LoginRequest(BaseModel):
    username: str
    password: str
    client_id: str
    client_secret: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    firstname: str
    lastname: str
    password: str

class ChannelInput(BaseModel):
    channel: str
    tg_session: str

class ChannelListInput(BaseModel):
    channels: List[str]
    tg_session: str
    neo4j: bool = True
    case_id: Optional[int] = None  # Optional case ID for tracking
    enable_translation: bool = True
    enable_image_analysis: bool = True
    enable_audio_transcription: bool = True
    enable_emotion_analysis: bool = False
    enable_label_classifier: bool = False
    enable_geolocation_extraction: bool = False

class StatusRequest(BaseModel):
    case_id: Optional[int] = None


class UserCtx(TypedDict):
    id: str           # Keycloak "sub"
    roles: list[str]

"""
Shared Job Payload Schemas
These models are used across:
- Backend API (request validation)
- Queue Service (job enqueueing)
- Workers (job processing)

By centralizing these models, we ensure type safety and
make changes in one place only.
"""


# ============================================================================
# BASE PAYLOAD
# ============================================================================

class BaseJobPayload(BaseModel):
    """Base payload with common fields for all jobs"""
    owner_id: str = Field(..., description="Owner/user ID who triggered the job")
    case_id: Optional[int] = Field(None, description="Case ID this job belongs to")

class ScrapeRequest(BaseModel):
    """Frontend-Schema: owner_id wird automatisch aus Auth-Context injiziert"""
    channel: str = Field(..., description="Single Telegram channel username")
    tg_session: str = Field(..., description="Telegram session name")
    recursive: bool = Field(default=True, description="Recursive channel discovery")
    neo4j: bool = Field(default=True, description="Write to Neo4j")
    case_id: Optional[int] = Field(None, description="Case ID")
    
    # AI Feature Flags
    enable_translation: bool = Field(default=True)
    enable_image_analysis: bool = Field(default=False)
    enable_audio_transcription: bool = Field(default=False)
    enable_emotion_analysis: bool = Field(default=False)
    enable_label_classifier: bool = Field(default=False)
    enable_geolocation_extraction: bool = Field(default=False)
    ocr_languages: List[str] = Field(default=["latin"], description="OCR Languages (latin, cyrillic, arabic)")

# ============================================================================
# TELEGRAM SCRAPER
# ============================================================================

class TelegramScrapePayload(BaseJobPayload):
    """Payload for Telegram scraping jobs"""
    channels: List[str] = Field(..., description="List of Telegram channel usernames")
    session_name: str = Field(..., alias="tg_session", description="Telegram session name")
    mode: str = Field(default="scrape", description="Scraper mode (scrape, monitor, etc.)")
    recursive: bool = Field(default=False, description="Recursively discover related channels")
    neo4j_write: bool = Field(default=True, alias="neo4j", description="Write to Neo4j graph database")
    
    # AI Feature Flags
    enable_translation: bool = Field(default=False, description="Enable automatic translation")
    enable_image_analysis: bool = Field(default=False, description="Enable image OCR and analysis")
    enable_audio_transcription: bool = Field(default=False, description="Enable audio transcription")
    enable_emotion_analysis: bool = Field(default=False, description="Enable emotion detection")
    enable_label_classifier: bool = Field(default=False, description="Enable text classification")
    enable_geolocation_extraction: bool = Field(default=False, description="Enable location extraction")
    ocr_languages: List[str] = Field(default=["latin"], description="OCR Languages (latin, cyrillic, arabic)")

    class Config:
        populate_by_name = True  # Allow both field names and aliases


# ============================================================================
# TRANSLATION
# ============================================================================

class TranslationJobPayload(BaseJobPayload):
    """Payload for translation jobs"""
    message_id: str = Field(..., description="Message ID to translate")
    original_text: str = Field(..., description="Original text to translate")
    source_language: str = Field(..., description="Source language code (e.g., 'en', 'de')")
    
    # Chain tracking
    parent_job_id: Optional[str] = Field(None, description="Parent job ID if chained")
    chained_from: Optional[str] = Field(None, description="What triggered this job (e.g., 'image-ocr')")
    
    # Context flags
    image_text: bool = Field(default=False, description="Text extracted from image")
    audio_text: bool = Field(default=False, description="Text transcribed from audio")

    # Downstream worker enable flags (controls chaining after translation)
    enable_emotion_analysis: bool = Field(default=False, description="Chain emotion analysis after translation")
    enable_label_classifier: bool = Field(default=False, description="Chain classification after translation")
    enable_geolocation_extraction: bool = Field(default=False, description="Chain geolocation after translation")


# ============================================================================
# IMAGE ANALYSIS
# ============================================================================

class ImageJobPayload(BaseJobPayload):
    """Payload for image analysis jobs"""
    message_id: str = Field(..., description="Message ID containing the image")
    image_path: str = Field(..., description="Path to image file")
    
    # Analysis options
    extract_text: bool = Field(default=True, description="Perform OCR to extract text")
    detect_objects: bool = Field(default=True, description="Detect objects in image")
    translate_extracted_text: bool = Field(default=False, description="Auto-translate extracted text")
    ocr_languages: List[str] = Field(default=["latin"], description="List of OCR language groups to use")


# ============================================================================
# AUDIO TRANSCRIPTION
# ============================================================================

class AudioJobPayload(BaseJobPayload):
    """Payload for audio transcription jobs"""
    message_id: str = Field(..., description="Message ID containing the audio")
    audio_path: str = Field(..., description="Path to audio file")
    
    # Transcription options
    translate_transcription: bool = Field(default=False, description="Auto-translate transcription")
    
    # Chain tracking
    parent_job_id: Optional[str] = Field(None, description="Parent job ID if chained")


# ============================================================================
# EMOTION ANALYSIS
# ============================================================================

class EmotionJobPayload(BaseJobPayload):
    """Payload for emotion analysis jobs"""
    message_id: str = Field(..., description="Message ID to analyze")
    text: str = Field(..., description="Text to analyze (should be in German)")
    
    # Analysis parameters
    threshold: float = Field(default=0.1, ge=0.0, le=1.0, description="Confidence threshold")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of top emotions to return")
    
    # Chain tracking
    parent_job_id: Optional[str] = Field(None, description="Parent job ID if chained")
    chained_from: Optional[str] = Field(None, description="What triggered this job")


# ============================================================================
# CLASSIFICATION
# ============================================================================

class ClassificationJobPayload(BaseJobPayload):
    """Payload for text classification jobs"""
    message_id: str = Field(..., description="Message ID to classify")
    text: str = Field(..., description="Text to classify")
    
    # Chain tracking
    parent_job_id: Optional[str] = Field(None, description="Parent job ID if chained")
    chained_from: Optional[str] = Field(None, description="What triggered this job")


# ============================================================================
# GEOLOCATION EXTRACTION
# ============================================================================

class GeolocationJobPayload(BaseJobPayload):
    """Payload for geolocation extraction jobs"""
    message_id: str = Field(..., description="Message ID to extract locations from")
    text: str = Field(..., description="Text to extract locations from")
    
    # Chain tracking
    parent_job_id: Optional[str] = Field(None, description="Parent job ID if chained")


# ============================================================================
# GENERIC JOB WRAPPER (for future extensibility)
# ============================================================================

class GenericJobRequest(BaseModel):
    """
    Generic job request wrapper
    Useful for a single unified endpoint in the future
    """
    job_type: str = Field(..., description="Type of job: telegram, translation, image, etc.")
    payload: dict = Field(..., description="Job-specific payload")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "telegram",
                "payload": {
                    "channels": ["example_channel"],
                    "session_name": "my_session",
                    "owner_id": "user123",
                    "case_id": 1
                }
            }
        }