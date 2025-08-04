# controller/casefile_controller.py  

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import Column, Integer, String, create_engine, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import Float, Text, CheckConstraint
import json
import os

# # RAG-spezifische Imports
# from services.rag_service import RAGService
# from sqlalchemy import text, func
# import time

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
    # embeddings = relationship("MessageEmbedding", back_populates="case", cascade="all, delete-orphan")
    # analyses = relationship("MessageAnalysis", back_populates="case", cascade="all, delete-orphan")
    # rag_queries = relationship("RAGQuery", back_populates="case", cascade="all, delete-orphan")



# class MessageEmbedding(Base):
#     __tablename__ = "message_embeddings"
    
#     id = Column(Integer, primary_key=True, index=True)
#     neo4j_message_id = Column(String(255), unique=True, nullable=False, index=True)
#     case_id = Column(Integer, ForeignKey('casefiles.id', ondelete='CASCADE'), nullable=False)
#     channel_name = Column(String(255), nullable=False, index=True)
    
#     # Vector embedding
#     embedding = Column(Vector(384), nullable=False)
    
#     # Metadaten
#     message_timestamp = Column(DateTime(timezone=True), nullable=False)
#     message_length = Column(Integer)
#     language = Column(String(5), default='unknown')
    
#     # Tracking
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
#     # Relationship
#     case = relationship("CaseFileModel", back_populates="embeddings")

# class MessageAnalysis(Base):
#     __tablename__ = "message_analyses"
    
#     id = Column(Integer, primary_key=True, index=True)
#     neo4j_message_id = Column(String(255), unique=True, nullable=False, index=True)
#     case_id = Column(Integer, ForeignKey('casefiles.id', ondelete='CASCADE'), nullable=False)
    
#     # Sentiment Analysis
#     sentiment_score = Column(Float, CheckConstraint('sentiment_score >= -1 AND sentiment_score <= 1'))
#     sentiment_label = Column(String(20), CheckConstraint("sentiment_label IN ('positive', 'neutral', 'negative')"))
#     sentiment_confidence = Column(Float, CheckConstraint('sentiment_confidence >= 0 AND sentiment_confidence <= 1'))
    
#     # Topic Analysis
#     topics = Column(ARRAY(String), default=[])
#     topic_scores = Column(JSONB, default={})
    
#     # Named Entity Recognition
#     entities = Column(JSONB, default={})
    
#     # Risk Assessment
#     risk_score = Column(Float, CheckConstraint('risk_score >= 0 AND risk_score <= 1'))
#     risk_categories = Column(ARRAY(String), default=[])
#     risk_reasoning = Column(Text)
    
#     # Analysis Metadata
#     model_used = Column(String(100), nullable=False)
#     analysis_confidence = Column(Float, CheckConstraint('analysis_confidence >= 0 AND analysis_confidence <= 1'))
#     processing_time_ms = Column(Integer)
    
#     # Tracking
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
#     # Relationship
#     case = relationship("CaseFileModel", back_populates="analyses")

# class RAGQuery(Base):
#     __tablename__ = "rag_queries"
    
#     id = Column(Integer, primary_key=True, index=True)
#     case_id = Column(Integer, ForeignKey('casefiles.id', ondelete='CASCADE'), nullable=False)
#     user_id = Column(String(255), nullable=False)
    
#     query_text = Column(Text, nullable=False)
#     query_embedding = Column(Vector(384))
    
#     # Results Metadata
#     results_count = Column(Integer, default=0)
#     avg_similarity_score = Column(Float)
#     llm_response = Column(Text)
    
#     # Performance Metrics
#     embedding_time_ms = Column(Integer)
#     search_time_ms = Column(Integer)
#     llm_time_ms = Column(Integer)
#     total_time_ms = Column(Integer)
    
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
    
#     # Relationship
#     case = relationship("CaseFileModel", back_populates="rag_queries")

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

class MessageEmbeddingResponse(BaseModel):
    id: int
    neo4j_message_id: str
    channel_name: str
    message_timestamp: datetime
    language: str
    similarity_score: Optional[float] = None

class MessageAnalysisResponse(BaseModel):
    id: int
    neo4j_message_id: str
    sentiment_score: Optional[float]
    sentiment_label: Optional[str]
    topics: List[str]
    entities: dict
    risk_score: Optional[float]
    risk_categories: List[str]
    model_used: str
    analysis_confidence: Optional[float]

class RAGSearchRequest(BaseModel):
    query: str
    limit: int = 10
    similarity_threshold: float = 0.7
    include_analysis: bool = True

class RAGSearchResult(BaseModel):
    neo4j_message_id: str
    channel_name: str
    similarity_score: float
    message_timestamp: datetime
    analysis: Optional[MessageAnalysisResponse] = None

class RAGSearchResponse(BaseModel):
    query: str
    results: List[RAGSearchResult]
    total_results: int
    avg_similarity: float
    processing_time_ms: int

class CaseAnalysisStats(BaseModel):
    total_messages: int
    analyzed_messages: int
    avg_sentiment: Optional[float]
    high_risk_messages: int
    top_topics: dict
    sentiment_distribution: dict
    risk_distribution: dict

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
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx),                    # NEW
):
    q = db.query(CaseFileModel)

    if not is_admin(user):                                # NEW
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
            channel_ids=channel_ids,
            limit=100,
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

    

# @router.get("/{casefile_id}/rag-search", response_model=RAGSearchResponse)
# async def rag_search(
#     casefile_id: int,
#     request: RAGSearchRequest = Depends(),
#     db: Session = Depends(get_db),
#     user: UserCtx = Depends(user_ctx),
# ):
#     """Semantische Suche mit RAG für einen Case"""
#     # Berechtigung prüfen
#     obj = db.query(CaseFileModel).get(casefile_id)
#     if not obj:
#         raise HTTPException(404, "CaseFile not found")
#     if not is_admin(user) and obj.owner_id != user["id"]:
#         raise HTTPException(403, "Forbidden")
    
#     start_time = time.time()
    
#     try:
#         rag_service = RAGService(db)
#         results = await rag_service.semantic_search(
#             case_id=casefile_id,
#             query=request.query,
#             limit=request.limit,
#             similarity_threshold=request.similarity_threshold,
#             include_analysis=request.include_analysis
#         )
        
#         processing_time_ms = int((time.time() - start_time) * 1000)
        
#         # Query für Analytics speichern
#         avg_similarity = sum(r.similarity_score for r in results) / len(results) if results else 0
        
#         rag_query = RAGQuery(
#             case_id=casefile_id,
#             user_id=user["id"],
#             query_text=request.query,
#             results_count=len(results),
#             avg_similarity_score=avg_similarity,
#             total_time_ms=processing_time_ms
#         )
#         db.add(rag_query)
#         db.commit()
        
#         return RAGSearchResponse(
#             query=request.query,
#             results=results,
#             total_results=len(results),
#             avg_similarity=avg_similarity,
#             processing_time_ms=processing_time_ms
#         )
        
#     except Exception as e:
#         raise HTTPException(500, f"RAG search failed: {str(e)}")

# @router.get("/{casefile_id}/analysis-stats", response_model=CaseAnalysisStats)
# async def get_case_analysis_stats(
#     casefile_id: int,
#     db: Session = Depends(get_db),
#     user: UserCtx = Depends(user_ctx),
# ):
#     """Statistiken über alle Analysen eines Cases"""
#     # Berechtigung prüfen
#     obj = db.query(CaseFileModel).get(casefile_id)
#     if not obj:
#         raise HTTPException(404, "CaseFile not found")
#     if not is_admin(user) and obj.owner_id != user["id"]:
#         raise HTTPException(403, "Forbidden")
    
#     try:
#         # Verwende die PostgreSQL-Funktion
#         result = db.execute(
#             text("SELECT * FROM get_case_analysis_stats(:case_id)"),
#             {"case_id": casefile_id}
#         ).fetchone()
        
#         if not result:
#             return CaseAnalysisStats(
#                 total_messages=0,
#                 analyzed_messages=0,
#                 avg_sentiment=None,
#                 high_risk_messages=0,
#                 top_topics={},
#                 sentiment_distribution={},
#                 risk_distribution={}
#             )
        
#         # Sentiment-Verteilung berechnen
#         sentiment_dist = db.execute(
#             text("""
#                 SELECT sentiment_label, COUNT(*) as count
#                 FROM message_analyses 
#                 WHERE case_id = :case_id AND sentiment_label IS NOT NULL
#                 GROUP BY sentiment_label
#             """),
#             {"case_id": casefile_id}
#         ).fetchall()
        
#         sentiment_distribution = {row.sentiment_label: row.count for row in sentiment_dist}
        
#         # Risk-Verteilung berechnen
#         risk_dist = db.execute(
#             text("""
#                 SELECT 
#                     CASE 
#                         WHEN risk_score < 0.3 THEN 'low'
#                         WHEN risk_score < 0.7 THEN 'medium'
#                         ELSE 'high'
#                     END as risk_level,
#                     COUNT(*) as count
#                 FROM message_analyses 
#                 WHERE case_id = :case_id AND risk_score IS NOT NULL
#                 GROUP BY risk_level
#             """),
#             {"case_id": casefile_id}
#         ).fetchall()
        
#         risk_distribution = {row.risk_level: row.count for row in risk_dist}
        
#         return CaseAnalysisStats(
#             total_messages=result.total_messages,
#             analyzed_messages=result.analyzed_messages,
#             avg_sentiment=result.avg_sentiment,
#             high_risk_messages=result.high_risk_messages,
#             top_topics=result.top_topics,
#             sentiment_distribution=sentiment_distribution,
#             risk_distribution=risk_distribution
#         )
        
#     except Exception as e:
#         raise HTTPException(500, f"Failed to get analysis stats: {str(e)}")

# @router.post("/{casefile_id}/trigger-analysis")
# async def trigger_case_analysis(
#     casefile_id: int,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_db),
#     user: UserCtx = Depends(user_ctx),
# ):
#     """Startet RAG-Analyse für alle Messages eines Cases"""
#     # Berechtigung prüfen
#     obj = db.query(CaseFileModel).get(casefile_id)
#     if not obj:
#         raise HTTPException(404, "CaseFile not found")
#     if not is_admin(user) and obj.owner_id != user["id"]:
#         raise HTTPException(403, "Forbidden")
    
#     try:
#         # Background-Task für Batch-Analyse
#         from services.rag_analysis_job import analyze_case_messages
#         background_tasks.add_task(analyze_case_messages, casefile_id, user["id"])
        
#         return {
#             "message": "Analysis job started in background",
#             "case_id": casefile_id,
#             "status": "processing"
#         }
        
#     except Exception as e:
#         raise HTTPException(500, f"Failed to start analysis job: {str(e)}")

# @router.get("/{casefile_id}/high-risk-messages")
# async def get_high_risk_messages(
#     casefile_id: int,
#     risk_threshold: float = 0.7,
#     limit: int = 50,
#     db: Session = Depends(get_db),
#     user: UserCtx = Depends(user_ctx),
# ):
#     """Holt Messages mit hohem Risk-Score"""
#     # Berechtigung prüfen
#     obj = db.query(CaseFileModel).get(casefile_id)
#     if not obj:
#         raise HTTPException(404, "CaseFile not found")
#     if not is_admin(user) and obj.owner_id != user["id"]:
#         raise HTTPException(403, "Forbidden")
    
#     try:
#         high_risk_analyses = db.query(MessageAnalysis).filter(
#             MessageAnalysis.case_id == casefile_id,
#             MessageAnalysis.risk_score >= risk_threshold
#         ).order_by(MessageAnalysis.risk_score.desc()).limit(limit).all()
        
#         # Neo4j Message Details laden (hier würden Sie Ihren Neo4j Service aufrufen)
#         from services.neo4j_backend_client import get_messages_by_ids
        
#         neo4j_ids = [analysis.neo4j_message_id for analysis in high_risk_analyses]
#         message_details = await get_messages_by_ids(neo4j_ids, user["id"])
        
#         # Kombiniere Analysis + Message Details
#         results = []
#         for analysis in high_risk_analyses:
#             message = next((m for m in message_details if m['id'] == analysis.neo4j_message_id), None)
#             if message:
#                 results.append({
#                     "analysis": MessageAnalysisResponse.from_orm(analysis),
#                     "message": message,
#                     "risk_score": analysis.risk_score,
#                     "risk_categories": analysis.risk_categories,
#                     "risk_reasoning": analysis.risk_reasoning
#                 })
        
#         return {
#             "high_risk_messages": results,
#             "total_count": len(results),
#             "risk_threshold": risk_threshold
#         }
        
#     except Exception as e:
#         raise HTTPException(500, f"Failed to get high-risk messages: {str(e)}")