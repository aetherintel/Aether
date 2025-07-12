# controller/casefile_controller.py  (full rewritten file)

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import Column, Integer, String, create_engine, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import os
from controller.message_controller import (
    list_channels
)
from services.neo4j_backend_client import (
    get_case_channels_with_recommendations,
    get_total_message_count_for_channels,
    get_messages_with_media
)
# ⬇︎ NEW:  bring in the user-context helper
from services.auth_ctx import user_ctx, is_admin, UserCtx

router = APIRouter(prefix="/casefiles", tags=["casefiles"])

# --- DB setup -----------------------------------------------------------
SQLALCHEMY_DATABASE_URL = os.getenv("DB_URL")
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Model --------------------------------------------------------------
class CaseFileModel(Base):
    __tablename__ = "casefiles"
    id         = Column(Integer, primary_key=True, index=True)
    owner_id   = Column(String,  nullable=False, index=True)          # already present
    title      = Column(String,  index=True)
    description = Column(Text)  
    category   = Column(String)
    postCount  = Column(Integer)
    tgchannels = Column(ARRAY(String))
    topics     = Column(ARRAY(String))
    terms      = Column(ARRAY(String))
    thumbnails = Column(ARRAY(String))
    duration   = Column(Integer)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    archived   = Column(Boolean, default=False)

# --- Schemas ------------------------------------------------------------
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
    tg_session: Optional[str] = None  # NEW: From frontend
    scraper_mode: Optional[str] = "full"

class CaseFile(CaseFileCreate):
    id: int
    owner_id: str
    created_at: datetime
    archived: bool

    class Config:
        from_attributes = True

# --- Helpers ------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)

# -----------------------------------------------------------------------
# Routes – every one now receives `user` and decides `owner`
# -----------------------------------------------------------------------

# Update your CaseFileCreate Pydantic model:
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
    tg_session: Optional[str] = None  # NEW: From frontend
    scraper_mode: Optional[str] = "full"  # NEW: Always "full" from frontend

# Import the telegram controller function
from controller.telegram_controller import launch_full_scrape_job

@router.post("/", response_model=CaseFile)
def create_casefile(
    payload: CaseFileCreate,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    # Create the case file (exclude scraper-specific fields from database)
    case_data = payload.model_dump(exclude={"tg_session", "scraper_mode"})
    db_case = CaseFileModel(**case_data, owner_id=user["id"])
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    
    # Auto-start scrapers for channels if conditions are met
    if payload.tgchannels and len(payload.tgchannels) > 0 and payload.tg_session:
        try:
            # Use the existing full scrape function for each channel
            for channel in payload.tgchannels:
                container_info = launch_full_scrape_job(
                    channel=channel,
                    tg_session=payload.tg_session,
                    recursive=True,  # Always recursive for full scrape
                    neo4j=True,     # Always write to Neo4j
                    owner_id=user["id"],
                    case_id=db_case.id  # Link to this case
                )
                
                print(f"Auto-started full scraper for channel '{channel}' in case {db_case.id}: {container_info}")
            
            print(f"Auto-started {len(payload.tgchannels)} full scrapers for case {db_case.id}")
            
        except Exception as e:
            # Don't fail case creation if scraper fails to start
            print(f"Failed to auto-start scrapers for case {db_case.id}: {str(e)}")
            # Log the error but don't raise it - case creation should still succeed
    
    return db_case

# Alternative: If you want to return scraper status info (optional)
class CaseFileCreateResponse(BaseModel):
    case: CaseFile
    scrapers_started: int
    scraper_error: Optional[str] = None

@router.post("/", response_model=CaseFileCreateResponse)
def create_casefile_with_status(
    payload: CaseFileCreate,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    # Create the case file
    case_data = payload.model_dump(exclude={"tg_session", "scraper_mode"})
    db_case = CaseFileModel(**case_data, owner_id=user["id"])
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    
    scrapers_started = 0
    scraper_error = None
    
    # Auto-start scrapers for channels if conditions are met
    if payload.tgchannels and len(payload.tgchannels) > 0 and payload.tg_session:
        try:
            for channel in payload.tgchannels:
                container_info = launch_full_scrape_job(
                    channel=channel,
                    tg_session=payload.tg_session,
                    recursive=True,
                    neo4j=True,
                    owner_id=user["id"],
                    case_id=db_case.id
                )
                scrapers_started += 1
                print(f"Auto-started full scraper for channel '{channel}': {container_info}")
            
        except Exception as e:
            scraper_error = str(e)
            print(f"Failed to auto-start scrapers for case {db_case.id}: {str(e)}")
    
    return {
        "case": db_case,
        "scrapers_started": scrapers_started,
        "scraper_error": scraper_error
    }


@router.get("/", response_model=List[CaseFile])
def read_casefiles(
    archived: bool | None = False,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),                    # NEW
):
    q = db.query(CaseFileModel)
    if not is_admin(user):                                # NEW
        q = q.filter_by(owner_id=user["id"])

    if archived is not None:
        q = q.filter_by(archived=archived)

    return q.all()


@router.get("/{casefile_id}", response_model=CaseFile)
async def read_casefile(
    casefile_id: int,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),                    # NEW
):
    obj = db.query(CaseFileModel).get(casefile_id)
    print(f"read_casefile: user={user}, obj={obj.tgchannels if obj else 'None'}")

    # TODO: Updating postCount while reading the casefile is only temporary. Needs to be moved to a better place.

    owner = None if is_admin(user) else user["id"]
    channel_usernames = obj.tgchannels if obj.tgchannels else []
    expanded_channels = await get_case_channels_with_recommendations(channel_usernames, owner)
    flattened = [item for sublist in expanded_channels.values() for item in sublist]

    print(f"read_casefile: expanded_channels={flattened}")

    # Get channel usernames from tgchannels and convert to comma-separated string
    usernames_str = ','.join(flattened) if flattened else None
    
    # Get channel details using the existing list_channels function
    channels = await list_channels(usernames=usernames_str, user=user)
    
    # Extract channel IDs from the channels
    channel_ids = [ch['channel_id'] for ch in channels if ch.get('channel_id')]
    
    print(f"read_casefile: tgchannels={obj.tgchannels}, expanded_channels={flattened}, channel_ids={channel_ids}")

    total_message_count = await get_total_message_count_for_channels(
        channel_ids=channel_ids,
        owner_id=owner
    )
    print(f"read_casefile: total_message_count={total_message_count}")

    obj.postCount = total_message_count
    obj.tgchannels = channel_usernames

    try:
        messages = await get_messages_with_media(
            owner_id=owner,
            limit=20,
        )

        messages_with_media = []
        for message in messages:
            if message.get('media_path'):
                messages_with_media.append(message.get('media_path'))

        print(f"read_casefile: messages_with_media={messages_with_media}")

        obj.thumbnails = messages_with_media
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Nachrichten für Benutzer {owner}: {str(e)}")

    db.commit()

    # TODO: End of temporary postCount update...

    if not obj:
        raise HTTPException(404, "CaseFile not found")
    if not is_admin(user) and obj.owner_id != user["id"]: # NEW
        raise HTTPException(403, "Forbidden")
    return obj


@router.delete("/{casefile_id}")
def delete_casefile(
    casefile_id: int,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),                    # NEW
):
    obj = db.query(CaseFileModel).get(casefile_id)
    if not obj:
        raise HTTPException(404, "CaseFile not found")
    if not is_admin(user) and obj.owner_id != user["id"]: # NEW
        raise HTTPException(403, "Forbidden")
    db.delete(obj)
    db.commit()
    return {"ok": True}

@router.patch("/{casefile_id}/archive")
def archive_casefile(
    casefile_id: int,
    archived: bool,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    obj = db.query(CaseFileModel).get(casefile_id)
    if not obj:
        raise HTTPException(404, "CaseFile not found")
    if not is_admin(user) and obj.owner_id != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    obj.archived = archived
    db.commit()
    db.refresh(obj)
    
    return {"ok": True, "archived": obj.archived}

@router.post("/{casefile_id}/add-channels")
def add_channels_to_case(
    casefile_id: int,
    channel_usernames: List[str],
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    """Add newly discovered channels to case"""
    try:
        obj = db.query(CaseFileModel).get(casefile_id)
        if not obj:
            raise HTTPException(404, "CaseFile not found")
        
        if not is_admin(user) and obj.owner_id != user["id"]:
            raise HTTPException(403, "Forbidden")
        
        # Get existing channels
        existing_channels = set(obj.tgchannels or [])
        
        # Add new channels
        new_channels = set(channel_usernames)
        updated_channels = list(existing_channels | new_channels)
        
        # Update case
        obj.tgchannels = updated_channels
        db.commit()
        
        print(f"[CASE] Added {len(new_channels)} channels to case {casefile_id}")
        print(f"[CASE] Total channels: {len(updated_channels)}")
        
        return {
            "case_id": casefile_id,
            "added_channels": list(new_channels - existing_channels),
            "total_channels": updated_channels
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error adding channels to case: {str(e)}")

@router.post("/{casefile_id}/remove-channels")
def remove_channels_from_case(
    casefile_id: int,
    channel_usernames: List[str],
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    """Remove specified channels from case"""
    try:
        obj = db.query(CaseFileModel).get(casefile_id)
        if not obj:
            raise HTTPException(404, "CaseFile not found")
        
        if not is_admin(user) and obj.owner_id != user["id"]:
            raise HTTPException(403, "Forbidden")
        
        # Get existing channels
        existing_channels = set(obj.tgchannels or [])
        
        # Remove specified channels
        to_remove = set(channel_usernames)
        updated_channels = list(existing_channels - to_remove)
        
        # Update case
        obj.tgchannels = updated_channels
        db.commit()
        
        print(f"[CASE] Removed {len(to_remove & existing_channels)} channels from case {casefile_id}")
        print(f"[CASE] Total channels: {len(updated_channels)}")
        
        return {
            "case_id": casefile_id,
            "removed_channels": list(to_remove & existing_channels),
            "total_channels": updated_channels
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error removing channels from case: {str(e)}")

    