"""
Queue Controller - Job Management Endpoints
Provides REST API for job management (replacing job-launcher endpoints)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from aether_lib.schemas.jobs import (
    TranslationJobPayload,
    ImageJobPayload,
    AudioJobPayload,
    EmotionJobPayload,
    ClassificationJobPayload,
    GeolocationJobPayload,
)
from services.queue_service import queue_service
from services.auth_ctx import user_ctx, UserCtx, is_admin

router = APIRouter(prefix="/queue", tags=["queue"])


# ============================================================================
# JOB LISTING & MONITORING
# ============================================================================

@router.get("/jobs")
def list_jobs(
    case_id: Optional[int] = Query(None, description="Filter by case ID"),
    queue_name: Optional[str] = Query(None, description="Filter by queue name"),
    user: UserCtx = Depends(user_ctx),
):
    """
    List all jobs across queues
    Supports filtering by case_id and queue_name
    """
    # Admins can see all jobs, users only see their own
    owner_id = None if is_admin(user) else user["id"]
    
    try:
        result = queue_service.list_jobs(
            owner_id=owner_id,
            case_id=case_id,
            queue_name=queue_name
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing jobs: {str(e)}")


@router.delete("/jobs/{job_id}")
def cancel_job(
    job_id: str,
    user: UserCtx = Depends(user_ctx),
):
    """
    Cancel a running or queued job
    Only the job owner or admin can cancel
    """
    # TODO: Add ownership check before cancelling
    success = queue_service.cancel_job(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return {"success": True, "job_id": job_id}


# ============================================================================
# TRANSLATION JOBS
# ============================================================================

@router.post("/translation")
def enqueue_translation(
    payload: TranslationJobPayload,
    user: UserCtx = Depends(user_ctx),
):
    """
    Queue a translation job
    Automatically called by scrapers when translation is enabled
    """
    # Ensure owner_id matches authenticated user (unless admin)
    if not is_admin(user) and payload.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot queue jobs for other users")
    
    try:
        job_id = queue_service.enqueue_translation(payload)
        return {
            "job_id": job_id,
            "queue": "translation",
            "status": "queued",
            "message_id": payload.message_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enqueueing translation: {str(e)}")


# ============================================================================
# IMAGE ANALYSIS JOBS
# ============================================================================

@router.post("/image")
def enqueue_image_analysis(
    payload: ImageJobPayload,
    user: UserCtx = Depends(user_ctx),
):
    """
    Queue an image analysis job
    Performs OCR and object detection
    """
    if not is_admin(user) and payload.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot queue jobs for other users")
    
    try:
        job_id = queue_service.enqueue_image_analysis(payload)
        return {
            "job_id": job_id,
            "queue": "image",
            "status": "queued",
            "message_id": payload.message_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enqueueing image analysis: {str(e)}")


# ============================================================================
# AUDIO TRANSCRIPTION JOBS
# ============================================================================

@router.post("/audio")
def enqueue_audio_transcription(
    payload: AudioJobPayload,
    user: UserCtx = Depends(user_ctx),
):
    """
    Queue an audio transcription job
    Uses Whisper for speech-to-text
    """
    if not is_admin(user) and payload.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot queue jobs for other users")
    
    try:
        job_id = queue_service.enqueue_audio_transcription(payload)
        return {
            "job_id": job_id,
            "queue": "audio",
            "status": "queued",
            "message_id": payload.message_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enqueueing audio transcription: {str(e)}")


# ============================================================================
# EMOTION ANALYSIS JOBS
# ============================================================================

@router.post("/emotion")
def enqueue_emotion_analysis(
    payload: EmotionJobPayload,
    user: UserCtx = Depends(user_ctx),
):
    """
    Queue an emotion analysis job
    Detects emotions in German text
    """
    if not is_admin(user) and payload.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot queue jobs for other users")
    
    try:
        job_id = queue_service.enqueue_emotion_analysis(payload)
        return {
            "job_id": job_id,
            "queue": "emotion",
            "status": "queued",
            "message_id": payload.message_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enqueueing emotion analysis: {str(e)}")


# ============================================================================
# CLASSIFICATION JOBS
# ============================================================================

@router.post("/classification")
def enqueue_classification(
    payload: ClassificationJobPayload,
    user: UserCtx = Depends(user_ctx),
):
    """
    Queue a text classification job
    Categorizes messages into predefined labels
    """
    if not is_admin(user) and payload.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot queue jobs for other users")
    
    try:
        job_id = queue_service.enqueue_classification(payload)
        return {
            "job_id": job_id,
            "queue": "classification",
            "status": "queued",
            "message_id": payload.message_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enqueueing classification: {str(e)}")


# ============================================================================
# GEOLOCATION EXTRACTION JOBS
# ============================================================================

@router.post("/geolocation")
def enqueue_geolocation(
    payload: GeolocationJobPayload,
    user: UserCtx = Depends(user_ctx),
):
    """
    Queue a geolocation extraction job
    Extracts location mentions from text
    """
    if not is_admin(user) and payload.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot queue jobs for other users")
    
    try:
        job_id = queue_service.enqueue_geolocation(payload)
        return {
            "job_id": job_id,
            "queue": "geolocation",
            "status": "queued",
            "message_id": payload.message_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enqueueing geolocation: {str(e)}")


# ============================================================================
# QUEUE HEALTH CHECK
# ============================================================================

@router.get("/health")
def queue_health():
    """
    Check queue service health
    Returns status of all queues
    """
    health_status = {}
    
    for queue_name, queue in queue_service.queues.items():
        try:
            # Check Redis connection
            queue.connection.ping()
            
            health_status[queue_name] = {
                "status": "healthy",
                "queued": len(queue),
                "workers": queue.count,
            }
        except Exception as e:
            health_status[queue_name] = {
                "status": "unhealthy",
                "error": str(e)
            }
    
    return {
        "service": "queue_service",
        "queues": health_status
    }