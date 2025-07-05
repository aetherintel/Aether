# controller/casefile_controller.py  (full rewritten file)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

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
    category   = Column(String)
    postCount  = Column(Integer)
    tgchannels = Column(ARRAY(String))
    topics     = Column(ARRAY(String))
    terms      = Column(ARRAY(String))
    duration   = Column(Integer)

# --- Schemas ------------------------------------------------------------
class CaseFileCreate(BaseModel):
    title: str
    category: str
    postCount: int
    tgchannels: List[str]
    topics: List[str]
    terms: List[str]
    duration: int

class CaseFile(CaseFileCreate):
    id: int
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

@router.post("/", response_model=CaseFile)
def create_casefile(
    payload: CaseFileCreate,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),                    # NEW
):
    db_case = CaseFileModel(**payload.model_dump(), owner_id=user["id"])  # NEW
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case


@router.get("/", response_model=List[CaseFile])
def read_casefiles(
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),                    # NEW
):
    q = db.query(CaseFileModel)
    if not is_admin(user):                                # NEW
        q = q.filter_by(owner_id=user["id"])
    return q.all()


@router.get("/{casefile_id}", response_model=CaseFile)
def read_casefile(
    casefile_id: int,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),                    # NEW
):
    obj = db.query(CaseFileModel).get(casefile_id)
    print(f"read_casefile: user={user}, obj={obj.tgchannels if obj else 'None'}")
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

