# backend/app/controller/scraper_controller.py
from http.client import HTTPException
from typing import Optional
from controller.auth_controller import user_ctx
from services.keycloak_service import get_current_user
from fastapi import APIRouter, Depends
from aether_lib.schemas.jobs import TelegramScrapePayload, ScrapeRequest, UserCtx
from services.queue_service import queue_service
from services.telegram_auth_service import load_string_session

router = APIRouter()

@router.post("/scrape")
def scrape(
    request: ScrapeRequest,
    user: UserCtx = Depends(user_ctx)
):
    """
    Start Telegram scraper job
    
    - Frontend sendet Request OHNE owner_id
    - owner_id wird automatisch aus JWT Token extrahiert
    - Security: User kann nur für sich selbst Jobs erstellen
    """
    # Load session
    session_string, _ = load_string_session(request.tg_session, user["id"])
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Convert Frontend-Request → Internal Payload
    payload = TelegramScrapePayload(
        channels=[request.channel],  # Convert singular → list
        session_name=request.tg_session,
        mode="full",
        recursive=request.recursive,
        neo4j_write=request.neo4j,
        owner_id=user["id"],  # ✅ Injected from auth context
        case_id=request.case_id,
        enable_translation=request.enable_translation,
        enable_image_analysis=request.enable_image_analysis,
        enable_audio_transcription=request.enable_audio_transcription,
        enable_emotion_analysis=request.enable_emotion_analysis,
        enable_label_classifier=request.enable_label_classifier,
        enable_geolocation_extraction=request.enable_geolocation_extraction,
    )
    
    # Enqueue
    job_id = queue_service.enqueue_telegram_scraper(payload, session_string)
    
    return {
        "job_id": job_id,
        "status": "queued",
        "channel": request.channel
    }
@router.get("/jobs")
def list_jobs(
    case_id: Optional[int] = None,
    queue_name: Optional[str] = None,
    user: UserCtx = Depends(user_ctx)
):
    """
    List user's jobs
    
    - Automatically filtered by authenticated user
    - Optional filters: case_id, queue_name
    """
    jobs = queue_service.list_jobs(
        owner_id=user["id"],  # ✅ Injected from auth context
        case_id=case_id,
        queue_name=queue_name
    )
    return {"jobs": jobs, "total": len(jobs)}


@router.delete("/jobs/{job_id}")
def cancel_job(
    job_id: str,
    user: UserCtx = Depends(user_ctx)
):
    """
    Cancel a job
    
    - Only owner can cancel their own jobs
    - Admin role could override (future enhancement)
    """
    success = queue_service.cancel_job(job_id, owner_id=user["id"])
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Job not found or access denied"
        )
    return {"message": "Job cancelled", "job_id": job_id}


@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    user: UserCtx = Depends(user_ctx)
):
    """
    Get detailed job status
    
    - Returns job info if user is the owner
    """
    job = queue_service.get_job(job_id, owner_id=user["id"])
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or access denied"
        )
    return job