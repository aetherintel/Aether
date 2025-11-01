# backend/app/controller/scraper_controller.py
from http.client import HTTPException
from typing import Optional
from backend.app.services.keycloak_service import get_current_user
from fastapi import APIRouter, Depends
from aether_lib.schemas.jobs import TelegramScrapePayload
from services.queue_service import queue_service
from services.telegram_auth_service import load_session_string

router = APIRouter()

@router.post("/scrape")
def scrape(payload: TelegramScrapePayload, user=Depends(get_current_user)):
    """
    Direkter Aufruf - KEIN HTTP-Call zum Job-Launcher mehr!
    """
    # Load session
    session_string, _ = load_session_string(payload.session_name, user.id)
    if not session_string:
        raise HTTPException(404, "Session not found")
    
    # Enqueue directly
    job_id = queue_service.enqueue_telegram_scraper(payload, session_string)
    
    return {"job_id": job_id, "status": "queued"}

@router.get("/jobs")
def list_jobs(
    case_id: Optional[int] = None,
    queue_name: Optional[str] = None,
    user=Depends(get_current_user)
):
    """List jobs - direkt vom queue_service"""
    jobs = queue_service.list_jobs(
        owner_id=user.id,
        case_id=case_id,
        queue_name=queue_name
    )
    return {"jobs": jobs}