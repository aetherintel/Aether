from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from model.casefile_model import CaseFileModel
from schemas.casefile_schema import CaseFileCreate
from controller.message_controller import fetch_channels
from controller.telegram_controller import launch_full_scrape_job
from services.neo4j_backend_client import (
    get_case_channels_with_recommendations,
    get_total_message_count_for_channels,
    get_messages_with_media
)

async def get_casefile_detail(db: Session, casefile_id: int, owner_id: Optional[str], is_admin: bool):
    obj = db.query(CaseFileModel).get(casefile_id)
    if not obj:
        raise HTTPException(404, "CaseFile not found")
    if not is_admin and obj.owner_id != owner_id:
        raise HTTPException(403, "Forbidden")

    owner = None if is_admin else owner_id
    channel_usernames = obj.tgchannels if obj.tgchannels else []
    
    # Expand channels with recommendations
    expanded_channels = await get_case_channels_with_recommendations(channel_usernames, owner)
    flattened = list(expanded_channels.keys()) + [
        rec for recs in expanded_channels.values() for rec in recs
    ]

    # Get channel details
    channels = await fetch_channels(owner, flattened)
    channel_ids = [ch['channel_id'] for ch in channels if ch.get('channel_id')]
    
    # Update post count (temporary logic from controller)
    total_message_count = await get_total_message_count_for_channels(
        channel_ids=channel_ids,
        owner_id=owner
    )
    obj.postCount = total_message_count

    # Get thumbnails (latest messages with media)
    try:
        messages = await get_messages_with_media(
            owner_id=owner,
            channel_ids=channel_ids,
            limit=100,
        )
        thumbnails = [msg.get('media_path') for msg in messages if msg.get('media_path')]
        obj.thumbnails = thumbnails
    except Exception as e:
        print(f"Error fetching thumbnails: {e}")
        # Don't fail the whole request if thumbnails fail

    db.commit()
    return obj

def create_casefile_logic(db: Session, payload: CaseFileCreate, owner_id: str):
    case_data = payload.model_dump(exclude={
        "tg_session", 
        "scraper_mode",
        "enable_translation",
        "enable_image_analysis",
        "enable_audio_transcription",
        "enable_emotion_analysis",
        "enable_label_classifier",
        "enable_geolocation_extraction"
    })
    db_case = CaseFileModel(**case_data, owner_id=owner_id)
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    
    scrapers_started = 0
    scraper_error = None
    
    if payload.tgchannels and payload.tg_session:
        try:
            for channel in payload.tgchannels:
                launch_full_scrape_job(
                    channel=channel,
                    tg_session=payload.tg_session,
                    recursive=True,
                    neo4j=True,
                    owner_id=owner_id,
                    case_id=db_case.id,
                    enable_translation=payload.enable_translation,
                    enable_image_analysis=payload.enable_image_analysis,
                    enable_audio_transcription=payload.enable_audio_transcription,
                    enable_emotion_analysis=payload.enable_emotion_analysis,
                    enable_label_classifier=payload.enable_label_classifier,
                    enable_geolocation_extraction=payload.enable_geolocation_extraction
                )
                scrapers_started += 1
        except Exception as e:
            scraper_error = str(e)
            print(f"Failed to auto-start scrapers for case {db_case.id}: {e}")
            
    return db_case, scrapers_started, scraper_error
