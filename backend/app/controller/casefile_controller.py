from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import ARRAY
import os

router = APIRouter(prefix="/casefiles", tags=["casefiles"])

# --- Database setup ---
SQLALCHEMY_DATABASE_URL = os.getenv('DB_URL')
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Model ---
class CaseFileModel(Base):
    __tablename__ = "casefiles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(String)
    postCount = Column(Integer)
    topics = Column(ARRAY(String))
    terms = Column(ARRAY(String))
    duration = Column(Integer)

# --- Pydantic schemas ---
class CaseFileCreate(BaseModel):
    title: str
    category: str
    postCount: int
    topics: List[str]
    terms: List[str]
    duration: int

class CaseFile(CaseFileCreate):
    id: int
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)

@router.post("/", response_model=CaseFile)
def create_casefile(casefile: CaseFileCreate, db: Session = Depends(get_db)):
    db_casefile = CaseFileModel(**casefile.dict())
    db.add(db_casefile)
    db.commit()
    db.refresh(db_casefile)
    return db_casefile

@router.get("/", response_model=List[CaseFile])
def read_casefiles(db: Session = Depends(get_db)):
    return db.query(CaseFileModel).all()

@router.get("/{casefile_id}", response_model=CaseFile)
def read_casefile(casefile_id: int, db: Session = Depends(get_db)):
    db_casefile = db.query(CaseFileModel).filter(CaseFileModel.id == casefile_id).first()
    if not db_casefile:
        raise HTTPException(status_code=404, detail="CaseFile not found")
    return db_casefile

@router.delete("/{casefile_id}")
def delete_casefile(casefile_id: int, db: Session = Depends(get_db)):
    db_casefile = db.query(CaseFileModel).filter(CaseFileModel.id == casefile_id).first()
    if not db_casefile:
        raise HTTPException(status_code=404, detail="CaseFile not found")
    db.delete(db_casefile)
    db.commit()
    return {"ok": True}