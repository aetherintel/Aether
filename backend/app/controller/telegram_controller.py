"""
Telegram Controller - Refactored to use QueueService
Now enqueues jobs directly instead of HTTP calls to job-launcher
"""
from fastapi import HTTPException
from typing import Optional

from aether_lib.schemas.jobs import TelegramScrapePayload
from services.queue_service import queue_service
from services.telegram_auth_service import load_string_session


def run_similarity(
    channel: str,
    tg_session: str,
    owner_id: str,
    case_id: Optional[int] = None
) -> dict:
    """
    Run channel similarity analysis
    TODO: This still needs implementation as a proper queue job
    """
    # For now, this could remain as-is or be converted to a queue job
    raise NotImplementedError("Similarity analysis not yet migrated to queue service")


def start_scraper(
    channels: list[str],
    tg_session: str,
    owner_id: str,
    case_id: int,
    mode: str = "scrape"
) -> str:
    """
    Start a basic scraper job
    
    Args:
        channels: List of channel usernames
        tg_session: Telegram session name
        owner_id: User ID
        case_id: Case ID
        mode: Scraper mode (default: "scrape")
        
    Returns:
        Job ID
    """
    # Load session string
    session_string, user_info = load_string_session(tg_session, owner_id)
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create payload
    payload = TelegramScrapePayload(
        channels=channels,
        session_name=tg_session,
        mode=mode,
        owner_id=owner_id,
        case_id=case_id,
        recursive=False,
        neo4j_write=True,
    )
    
    # Enqueue directly via queue service
    try:
        job_id = queue_service.enqueue_telegram_scraper(payload, session_string)
        return job_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scraper: {str(e)}")


def launch_full_scrape_job(
    channel: str,
    tg_session: str,
    recursive: bool = True,
    neo4j: bool = True,
    owner_id: str = "",
    case_id: Optional[int] = None,
    # AI Worker Flags
    enable_translation: bool = True,
    enable_image_analysis: bool = True,
    enable_audio_transcription: bool = True,
    enable_emotion_analysis: bool = False,
    enable_label_classifier: bool = False,
    enable_geolocation_extraction: bool = False,
) -> dict:
    """
    Launch a full scrape job with all AI workers enabled
    
    Args:
        channel: Single channel username
        tg_session: Telegram session name
        recursive: Enable recursive channel discovery
        neo4j: Write to Neo4j graph database
        owner_id: User ID
        case_id: Case ID
        enable_*: Feature flags for AI workers
        
    Returns:
        Job info dictionary
    """
    # Load session string
    session_string, user_info = load_string_session(tg_session, owner_id)
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create payload with all flags
    payload = TelegramScrapePayload(
        channels=[channel],  # Single channel as list
        session_name=tg_session,
        mode="full",
        recursive=recursive,
        neo4j_write=neo4j,
        owner_id=owner_id,
        case_id=case_id,
        enable_translation=enable_translation,
        enable_image_analysis=enable_image_analysis,
        enable_audio_transcription=enable_audio_transcription,
        enable_emotion_analysis=enable_emotion_analysis,
        enable_label_classifier=enable_label_classifier,
        enable_geolocation_extraction=enable_geolocation_extraction,
    )
    
    # Enqueue directly via queue service
    try:
        job_id = queue_service.enqueue_telegram_scraper(payload, session_string)
        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Full scraper job enqueued successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch scraper job: {str(e)}")


def launch_live_scrape_job(
    channels: list[str],
    tg_session: str,
    neo4j: bool,
    owner_id: str,
    case_id: Optional[int] = None,
    # AI Worker Flags
    enable_translation: bool = True,
    enable_image_analysis: bool = True,
    enable_audio_transcription: bool = True,
    enable_emotion_analysis: bool = False,
    enable_label_classifier: bool = False,
    enable_geolocation_extraction: bool = False,
) -> dict:
    """
    Launch a live scrape job (monitoring mode)
    
    Args:
        channels: List of channel usernames
        tg_session: Telegram session name
        neo4j: Write to Neo4j graph database
        owner_id: User ID
        case_id: Case ID
        enable_*: Feature flags for AI workers
        
    Returns:
        Job info dictionary
    """
    # Load session string
    session_string, user_info = load_string_session(tg_session, owner_id)
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create payload
    payload = TelegramScrapePayload(
        channels=channels,
        session_name=tg_session,
        mode="live",
        recursive=False,  # Live mode doesn't do recursive discovery
        neo4j_write=neo4j,
        owner_id=owner_id,
        case_id=case_id,
        enable_translation=enable_translation,
        enable_image_analysis=enable_image_analysis,
        enable_audio_transcription=enable_audio_transcription,
        enable_emotion_analysis=enable_emotion_analysis,
        enable_label_classifier=enable_label_classifier,
        enable_geolocation_extraction=enable_geolocation_extraction,
    )
    
    # Enqueue directly via queue service
    try:
        job_id = queue_service.enqueue_telegram_scraper(payload, session_string)
        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Live scraper job enqueued successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live scraper job failed: {str(e)}")


def get_container_status(owner_id: str, case_id: Optional[str] = None) -> dict:
    """
    Get container/job status
    Now queries the queue service instead of Docker
    
    Args:
        owner_id: User ID
        case_id: Optional case ID filter
        
    Returns:
        Job status dictionary
    """
    try:
        # Convert case_id to int if provided
        case_id_int = int(case_id) if case_id else None
        
        # Use queue service to list jobs
        result = queue_service.list_jobs(
            owner_id=owner_id,
            case_id=case_id_int
        )
        
        # Format as "containers" for backward compatibility with frontend
        containers = []
        for job in result.get("jobs", []):
            # Map job status to container status
            status_map = {
                "queued": "created",
                "started": "running",
                "finished": "exited",
                "failed": "exited"
            }
            
            # Format channels display
            channels_display = ", ".join(job.get("channels", [])) if job.get("channels") else job.get("message_id", "N/A")
            
            # Determine image/name based on queue
            queue = job.get("queue", "unknown")
            if "telegram" in queue:
                image = "telegram-scraper"
            elif "translation" in queue:
                image = "translation-worker"
            elif "image" in queue:
                image = "image-worker"
            elif "emotion" in queue:
                image = "emotion-worker"
            elif "classification" in queue:
                image = "classification-worker"
            else:
                image = "unknown-worker"
            
            containers.append({
                "id": job.get("job_id", "unknown"),
                "name": f"{job.get('mode', 'job')}_{job.get('job_id', 'unknown')[:8]}",
                "status": status_map.get(job.get("status", "unknown"), "unknown"),
                "image": image,
                "labels": {
                    "case_id": str(job.get("case_id", "")),
                    "owner_id": job.get("owner_id", ""),
                    "channels": channels_display,
                    "mode": job.get("mode", "unknown"),
                    "queue": queue
                },
                "created": job.get("created_at"),
                "case_id": job.get("case_id"),
                "owner_id": job.get("owner_id"),
                "channels": channels_display,
                "mode": job.get("mode", "unknown"),
                "session": "N/A",  # We don't expose session names in job data
                "runtime": job.get("runtime"),
                "queue": queue
            })
        
        return {
            "containers": containers,
            "total": len(containers),
            "filtered_by_case": case_id,
            "user_id": owner_id,
            "queues": result.get("queues", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to get job status: {str(e)}")


def stop_container(container_id: str) -> dict:
    """
    Stop a container/job
    Now cancels the job in the queue
    """
    try:
        success = queue_service.cancel_job(container_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Job {container_id} not found")
        
        return {"success": True, "message": f"Job {container_id} cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop job: {str(e)}")


def remove_container(container_id: str) -> dict:
    """
    Remove a container/job
    In RQ, finished jobs are automatically cleaned up, so this just confirms
    """
    # For now, just return success - RQ handles cleanup automatically
    return {"success": True, "message": f"Job {container_id} will be cleaned up automatically"}


def restart_container(container_id: str) -> dict:
    """
    Restart a container/job
    TODO: Implement job retry logic
    """
    raise NotImplementedError("Job restart not yet implemented")


# Backward compatibility - these may be referenced elsewhere
start_container = start_scraper