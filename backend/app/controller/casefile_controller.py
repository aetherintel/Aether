# controller/casefile_controller.py

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import os

from database import engine, Base, get_db
from model.casefile_model import CaseFileModel, ReportModel
from schemas.casefile_schema import (
    CaseFileCreate, 
    CaseFile, 
    ReportConfigUpdate, 
    CaseFileCreateResponse
)

from controller.message_controller import (
    fetch_channels,
    list_channels
)
from services.neo4j_backend_client import (
    get_case_channels_with_recommendations,
    get_total_message_count_for_channels,
    get_messages_with_media
)
from services.auth_ctx import user_ctx, is_admin, UserCtx

router = APIRouter(prefix="/casefiles", tags=["casefiles"])

# Auto-migration for new columns
def check_and_migrate_db():
    try:
        with engine.connect() as conn:
            # Check if columns exist
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='casefiles'"))
            columns = [row[0] for row in result]
            
            if 'report_frequency' not in columns:
                print("Migrating DB: Adding report_frequency column")
                conn.execute(text("ALTER TABLE casefiles ADD COLUMN report_frequency VARCHAR DEFAULT 'daily'"))
                
            if 'report_sections' not in columns:
                print("Migrating DB: Adding report_sections column")
                conn.execute(text("ALTER TABLE casefiles ADD COLUMN report_sections VARCHAR[] DEFAULT ARRAY['stats', 'charts', 'messages']"))
            
            conn.commit()
    except Exception as e:
        print(f"DB Migration Warning: {e}")

Base.metadata.create_all(bind=engine)
check_and_migrate_db()

from services.casefile_service import get_casefile_detail, create_casefile_logic

@router.post("/", response_model=CaseFile)
def create_casefile(
    payload: CaseFileCreate,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    db_case, _, _ = create_casefile_logic(db, payload, user["id"])
    return db_case

@router.post("/with-status", response_model=CaseFileCreateResponse)
def create_casefile_with_status_route(
    payload: CaseFileCreate,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    db_case, scrapers_started, scraper_error = create_casefile_logic(db, payload, user["id"])
    return {
        "case": db_case,
        "scrapers_started": scrapers_started,
        "scraper_error": scraper_error
    }

@router.get("/", response_model=List[CaseFile])
def read_casefiles(
    archived: bool | None = False,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    q = db.query(CaseFileModel)
    if not is_admin(user):
        q = q.filter_by(owner_id=user["id"])
    if archived is not None:
        q = q.filter_by(archived=archived)
    if limit is not None:
        q = q.limit(limit)
    return q.all()

@router.get("/{casefile_id}", response_model=CaseFile)
async def read_casefile(
    casefile_id: int,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    return await get_casefile_detail(
        db=db, 
        casefile_id=casefile_id, 
        owner_id=user["id"], 
        is_admin=is_admin(user)
    )


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

@router.patch("/{casefile_id}/report-config")
def update_report_config(
    casefile_id: int,
    config: ReportConfigUpdate,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),
):
    """Update report configuration for a case"""
    obj = db.query(CaseFileModel).get(casefile_id)
    if not obj:
        raise HTTPException(404, "CaseFile not found")
    if not is_admin(user) and obj.owner_id != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    obj.report_frequency = config.report_frequency
    obj.report_sections = config.report_sections
    db.commit()
    db.refresh(obj)
    
    return {
        "id": obj.id,
        "report_frequency": obj.report_frequency,
        "report_sections": obj.report_sections
    }

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

    