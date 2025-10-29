# main.py
"""
Job Launcher - Central Queue Manager
Manages all processing queues (translation, image, audio, etc.)
"""
from fastapi import FastAPI, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Optional, List
from rq import Queue, Retry
from redis import Redis
import os
import uuid
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Aether Job Launcher", version="2.0")

# Redis Connections for different queues
default_redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=0)
translation_redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=1)
image_redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=2)
audio_redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=3)
emotion_redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=4)
classification_redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=5)
geolocation_redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=6)

queues = {
    'translation': Queue('translation-jobs', connection=translation_redis_conn),
    'image': Queue('image-jobs', connection=image_redis_conn),
    'audio': Queue('audio-jobs', connection=audio_redis_conn),
    'emotion': Queue('emotion-jobs', connection=emotion_redis_conn),
    'telegram': Queue('telegram-jobs', connection=default_redis_conn),
    'classification': Queue('classification-jobs', connection=classification_redis_conn),
    'geolocation': Queue('geolocation-jobs', connection=geolocation_redis_conn),
}

SECRET = os.getenv("JOB_SECRET_TOKEN", "changeme")

# ============================================================================
#  REQUEST MODELS
# ============================================================================

class TranslationJobRequest(BaseModel):
    message_id: str
    original_text: str
    source_language: str
    owner_id: Optional[str] = "unknown"
    case_id: Optional[int] = None
    # For chained jobs
    parent_job_id: Optional[str] = None
    chained_from: Optional[str] = None  # e.g., "image-ocr"
    image_text: bool = False
    audio_text: bool = False  # NEW: Flag for audio text translation

class ImageJobRequest(BaseModel):
    message_id: str
    image_path: str
    owner_id: Optional[str] = "unknown"
    case_id: Optional[int] = None
    # Options
    extract_text: bool = True
    detect_objects: bool = True
    translate_extracted_text: bool = True  # NEW: Auto-translate OCR text

class AudioJobRequest(BaseModel):
    message_id: str
    audio_path: str
    owner_id: Optional[str] = "unknown"
    case_id: Optional[int] = None
    translate_transcript: bool = True  # NEW: Auto-translate transcription

class EmotionJobRequest(BaseModel):
    message_id: str
    text: str
    owner_id: Optional[str] = None
    case_id: Optional[int] = None
    threshold: float = 0.3
    top_k: int = 3
    chained_from: Optional[str] = None
    parent_job_id: Optional[str] = None

class JobListRequest(BaseModel):
    owner_id: Optional[str] = None
    case_id: Optional[int] = None
    queue_name: Optional[str] = None

class ScrapeRequest(BaseModel):
    channels: list[str]
    tg_session: str
    mode: str = "scrape"
    recursive: bool = False
    neo4j: bool = True
    owner_id: str = "unknown"
    parent_container_id: Optional[str] = None
    depth: int = 0
    max_discover_messages: int = 200
    case_id: Optional[int] = None
    enable_translation: bool = True
    enable_image_analysis: bool = True
    enable_audio_transcription: bool = True
    enable_emotion_analysis: bool = False
    enable_label_classifier: bool = False
    enable_geolocation_extraction: bool = False

# Audio transcription job model
class AudioTranscriptionJob(BaseModel):
    message_id: str
    media_path: str
    media_type: Optional[str] = None  # 'audio' or 'video', auto-detect if None
    language_hint: Optional[str] = None
    translate_transcription: bool = True
    owner_id: Optional[str] = None
    case_id: Optional[int] = None
    parent_job_id: Optional[str] = None
    chained_from: Optional[str] = None

# Geolocation extraction job model
class GeolocationRequest(BaseModel):
    message_id: str
    text: str
    owner_id: Optional[str] = None
    case_id: Optional[int] = None

# ============================================================================
#  HELPER FUNCTIONS
# ============================================================================

def _check_auth(request: Request):
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {SECRET}":
        raise HTTPException(status_code=403, detail="Unauthorized")

def _get_queue_by_name(queue_name: str) -> Queue:
    """Get queue by name"""
    if queue_name not in queues:
        raise HTTPException(status_code=400, detail=f"Unknown queue: {queue_name}")
    return queues[queue_name]

def load_string_session(session_name: str, owner_id: str) -> tuple:
    """StringSession aus JSON-Datei"""
    from pathlib import Path
    import json
    
    SESSION_DIR = Path("/app/sessions")
    session_file = SESSION_DIR / f"user_{owner_id}/{session_name}.json"
    if not session_file.exists():
        return None, None
    
    with open(session_file, 'r') as f:
        data = json.load(f)
    
    return data.get("session_string"), data.get("user_info")

# ============================================================================
#  QUEUE ENDPOINTS - TRANSLATION
# ============================================================================

@app.post("/queue/translation")
def queue_translation_job(req: TranslationJobRequest, request: Request):
    """
    Queue a translation job
    Can be called by scraper OR by other workers (chaining)
    """
    _check_auth(request)
    
    job_id = f"translate_{req.message_id}_{uuid.uuid4().hex[:6]}"
    
    print(f"[QUEUE] Translation job: {req.source_language} -> de for message {req.message_id}")
    
    if req.chained_from:
        print(f"[QUEUE] Chained from: {req.chained_from} (parent: {req.parent_job_id})")
    
    # Check if this is image text translation
    is_image_text = getattr(req, 'image_text', False)
    if is_image_text:
        print(f"[QUEUE] Image text translation (will update image_text_translated field)")
    
    is_audio_text = getattr(req, 'audio_text', False)
    if is_audio_text:
        print(f"[QUEUE] Audio text translation (will update audio_text_translated field)")

    job = queues['translation'].enqueue(
        'workers.translation_worker.translate_and_update',
        message_id=req.message_id,
        original_text=req.original_text,
        source_language=req.source_language,
        owner_id=req.owner_id,
        image_text=is_image_text,
        job_timeout='5m',
        result_ttl=600,
        failure_ttl=86400,
        ttl=None,
        meta={
            'owner_id': req.owner_id,
            'case_id': req.case_id,
            'parent_job_id': req.parent_job_id,
            'chained_from': req.chained_from,
            'image_text': is_image_text,  # Include in metadata
            'audio_text': is_audio_text  # Include in metadata
        
        }
    )
    return {
        "job_id": job.id,
        "queue": "translation-jobs",
        "status": job.get_status(),
        "message_id": req.message_id,
        "image_text": is_image_text,
        "audio_text": is_audio_text,
        "queued_at": str(job.enqueued_at)
    }

# ============================================================================
#  QUEUE ENDPOINTS - IMAGE
# ============================================================================

@app.post("/queue/image")
def queue_image_job(req: ImageJobRequest, request: Request):
    """
    Queue an image analysis job
    Can automatically chain to translation if text is extracted
    """
    _check_auth(request)
    
    job_id = f"image_{req.message_id}_{uuid.uuid4().hex[:6]}"
    
    print(f"[QUEUE] Image analysis job for message {req.message_id}")
    print(f"[QUEUE] Options: OCR={req.extract_text}, Objects={req.detect_objects}, Auto-translate={req.translate_extracted_text}")
    
    job = queues['image'].enqueue(
    'workers.image_worker.worker.analyze_and_update',
    message_id=req.message_id,
    image_path=req.image_path,
    extract_text=req.extract_text,
    detect_objects=req.detect_objects,
    translate_extracted_text=req.translate_extracted_text,
    owner_id=req.owner_id,
    case_id=req.case_id,
    job_id=job_id,
    job_timeout='5m',
    result_ttl=86400,
    failure_ttl=86400,
    ttl=None,
    meta={
        'owner_id': req.owner_id,
        'case_id': req.case_id
    }
)
    
    return {
        "job_id": job.id,
        "queue": "image-jobs",
        "status": job.get_status(),
        "message_id": req.message_id,
        "queued_at": str(job.enqueued_at)
    }

# ============================================================================
#  QUEUE ENDPOINTS - AUDIO
# ============================================================================

@app.post("/queue/audio-transcription")
def queue_audio_transcription(req: AudioTranscriptionJob, request: Request):
    """
    Queue an audio transcription job
    Can automatically chain to translation if requested
    """
    _check_auth(request)

    job_id = f"audio_{req.message_id}_{uuid.uuid4().hex[:6]}"

    print(f"[QUEUE] Audio transcription job for message {req.message_id}")
    print(f"[QUEUE] Options: Translate={req.translate_transcription}, Language hint={req.language_hint or 'auto'}, Media type={req.media_type or 'auto'}")

    if not os.path.exists(req.media_path):
        raise HTTPException(
            status_code=404,
            detail=f"Media file not found: {req.media_path}"
        )

    # Check file size (limit: 500 MB)
    file_size_mb = os.path.getsize(req.media_path) / (1024 * 1024)
    if file_size_mb > 500:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size_mb:.1f} MB (max 500 MB)"
        )

    # Dynamically choose timeout based on file size
    timeout = "30m" if file_size_mb > 100 else "15m"

    job = queues['audio'].enqueue(
        'workers.audio_worker.worker.transcribe_and_update',
        message_id=req.message_id,
        media_path=req.media_path,
        media_type=req.media_type,
        language_hint=req.language_hint,
        translate_transcription=req.translate_transcription,
        owner_id=req.owner_id,
        case_id=req.case_id,
        job_id=job_id,
        job_timeout=timeout,
        result_ttl=86400,
        failure_ttl=86400,
        ttl=None,
        meta={
            'owner_id': req.owner_id,
            'case_id': req.case_id
        }
    )

    print(f"[QUEUE] ✅ Audio transcription job queued successfully")
    print(f"[QUEUE] File size: {file_size_mb:.1f} MB | Timeout: {timeout}")

    return {
        "job_id": job.id,
        "queue": "audio-jobs",
        "status": job.get_status(),
        "message_id": req.message_id,
        "media_type": req.media_type,
        "file_size_mb": round(file_size_mb, 2),
        "queued_at": str(job.enqueued_at)
    }

# ============================================================================
#  EMOTION ANALYSIS QUEUE
# ===========================================================================
@app.post("/queue/emotion")
def queue_emotion_job(req: EmotionJobRequest, request: Request):
    """
    Queue an emotion analysis job
    Can be called by scraper (German text) OR translation worker (after translation)
    """
    _check_auth(request)
    
    job_id = f"emotion_{req.message_id}_{uuid.uuid4().hex[:6]}"
    
    print(f"[QUEUE] Emotion analysis job for message {req.message_id}")
    
    if req.chained_from:
        print(f"[QUEUE] Chained from: {req.chained_from} (parent: {req.parent_job_id})")
    
    # Queue the job
    job = queues['emotion'].enqueue(
        'workers.emotion_worker.worker.classify_emotion_job',
        message_id=req.message_id,
        text=req.text,
        neo4j_uri=os.getenv('NEO4J_URI'),
        neo4j_user=os.getenv('NEO4J_USER'),
        neo4j_password=os.getenv('NEO4J_PASSWORD'),
        threshold=req.threshold,
        top_k=req.top_k,
        job_timeout='5m',
        result_ttl=600,
        failure_ttl=86400,
        ttl=None,
        meta={
            'owner_id': req.owner_id,
            'case_id': req.case_id,
            'parent_job_id': req.parent_job_id,
            'chained_from': req.chained_from
        }
    )
    
    print(f"[QUEUE] ✅ Emotion analysis job queued successfully")
    print(f"[QUEUE] Job ID: {job.id}")
    
    return {
        "job_id": job.id,
        "queue": "emotion-jobs",
        "status": job.get_status(),
        "message_id": req.message_id,
        "queued_at": str(job.enqueued_at)
    }

# =============================
# Classification queue endpoint
# =============================
@app.post("/queue/classification")
def queue_classification_job(req: EmotionJobRequest, request: Request):
    """
    Queue a text classification job
    Can be called by scraper (German text) OR translation worker (after translation)
    """
    _check_auth(request)
    
    job_id = f"classification_{req.message_id}_{uuid.uuid4().hex[:6]}"
    
    print(f"[QUEUE] Text classification job for message {req.message_id}")
    
    if req.chained_from:
        print(f"[QUEUE] Chained from: {req.chained_from} (parent: {req.parent_job_id})")
    
    # Queue the job
    job = queues['classification'].enqueue(
        'workers.classification_worker.worker.classify_post_job',
        message_id=req.message_id,
        text=req.text,
        neo4j_uri=os.getenv('NEO4J_URI'),
        neo4j_user=os.getenv('NEO4J_USER'),
        neo4j_password=os.getenv('NEO4J_PASSWORD'),
        job_timeout='5m',
        result_ttl=600,
        failure_ttl=86400,
        ttl=None,
        meta={
            'owner_id': req.owner_id,
            'case_id': req.case_id,
            'parent_job_id': req.parent_job_id,
            'chained_from': req.chained_from
        }
    )
    
    print(f"[QUEUE] ✅ Text classification job queued successfully")
    print(f"[QUEUE] Job ID: {job.id}")
    
    return {
        "job_id": job.id,
        "queue": "emotion-jobs",
        "status": job.get_status(),
        "message_id": req.message_id,
        "queued_at": str(job.enqueued_at)
    }

# Add to job_launcher/main.py

@app.post("/queue/geolocation")
def launch_geolocation_job(req: GeolocationRequest, request: Request):
    """Queue geolocation extraction job"""
    _check_auth(request)
    
    job_id = f"geo_{uuid.uuid4().hex[:6]}"
    
    job = queues['geolocation'].enqueue(
        'workers.geolocation_worker.worker.extract_and_update_location',
        message_id=req.message_id,
        text=req.text,
        owner_id=req.owner_id,
        case_id=req.case_id,
        job_timeout='5m',
        result_ttl=86400,
        failure_ttl=86400,
        meta={
            'owner_id': req.owner_id,
            'case_id': req.case_id,
            'message_id': req.message_id
        }
    )
    
    return {
        "job_id": job.id,
        "queue": "geolocation-jobs",
        "status": job.get_status(),
        "message_id": req.message_id
    }

# ============================================================================
#  TELEGRAM SCRAPER QUEUE (Your existing endpoint)
# ============================================================================

@app.post("/scrape")
def launch_scraper(req: ScrapeRequest, request: Request):
    """Launch telegram scraper job (your existing endpoint)"""
    _check_auth(request)
    session_string, user_info = load_string_session(req.tg_session, req.owner_id)
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    # Your existing scraper logic
    job_id = f"{req.mode}_{uuid.uuid4().hex[:6]}"
    
    job = queues['telegram'].enqueue(
        'rq_worker.run_job',
        kwargs={
            'mode': req.mode,
            'channels': req.channels,
            'session_string': session_string,  # Load from session
            'session_name': req.tg_session,
            'recursive': req.recursive,
            'neo4j_write': req.neo4j,
            'owner_id': req.owner_id,
            'case_id': req.case_id,
            'enable_translation': req.enable_translation,
            'enable_image_analysis': req.enable_image_analysis,
            'enable_audio_transcription': req.enable_audio_transcription,
            'enable_emotion_analysis': req.enable_emotion_analysis,
            'enable_label_classifier': req.enable_label_classifier,
            'enable_geolocation_extraction': req.enable_geolocation_extraction,
        },
        job_id=job_id,
        timeout='6h',
        result_ttl=86400,
        failure_ttl=86400,
        ttl=None,
        retry=Retry(max=3, interval=[10, 30, 60]),
        meta={
            'owner_id': req.owner_id,
            'case_id': req.case_id,
        }   
    )
    
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "queued_at": str(job.enqueued_at)
    }

# ============================================================================
#  JOB MANAGEMENT
# ============================================================================
# job-launcher/main.py - Improved Job Management

@app.get("/jobs")
def list_all_jobs(
    owner_id: Optional[str] = Query(None),  # ← FIXED: Explicitly use Query()
    case_id: Optional[int] = Query(None),   # ← FIXED: Explicitly use Query()
    queue_name: Optional[str] = Query(None), # ← FIXED: Explicitly use Query()
    request: Request = None
):
    """
    List jobs across all queues with proper filtering
    Returns jobs in a format compatible with frontend
    """
    _check_auth(request)
    
    all_jobs = []
    
    # Determine which queues to check
    if queue_name:
        if queue_name not in queues:
            raise HTTPException(status_code=400, detail=f"Unknown queue: {queue_name}")
        queues_to_check = {queue_name: queues[queue_name]}
    else:
        # Show ALL queues by default (telegram, translation, image, audio, sentiment)
        queues_to_check = queues
    
    for queue_name, queue in queues_to_check.items():
        try:
            # 1. Queued jobs (waiting to be processed)
            queued_jobs = list(queue.jobs)
            for job in queued_jobs:
                if job:
                    job_owner = job.meta.get('owner_id') if hasattr(job, 'meta') and job.meta else None
                    if not job_owner and hasattr(job, 'kwargs') and job.kwargs:
                        job_owner = job.kwargs.get('owner_id')
                    job_case = job.meta.get('case_id') if hasattr(job, 'meta') and job.meta else None
                    if not job_case and hasattr(job, 'kwargs') and job.kwargs:
                        job_case = job.kwargs.get('case_id')
                
                if _job_matches_filter(job, owner_id, case_id):
                    all_jobs.append(_format_job(job, "queued", queue_name))
                else:
                    print(f"[DEBUG] Job {job.id} DOES NOT MATCH filter")
            
            # 2. Started jobs (currently processing)
            started_job_ids = list(queue.started_job_registry.get_job_ids())
            for job_id in started_job_ids:
                try:
                    job = queue.fetch_job(job_id)
                    if job:
                        job_owner = job.meta.get('owner_id') if hasattr(job, 'meta') and job.meta else None
                        if not job_owner and hasattr(job, 'kwargs') and job.kwargs:
                            job_owner = job.kwargs.get('owner_id')
                        job_case = job.meta.get('case_id') if hasattr(job, 'meta') and job.meta else None
                        if not job_case and hasattr(job, 'kwargs') and job.kwargs:
                            job_case = job.kwargs.get('case_id')
                        if _job_matches_filter(job, owner_id, case_id):
                            all_jobs.append(_format_job(job, "started", queue_name))
                        else:
                            print(f"[DEBUG] Started job {job.id} DOES NOT MATCH")
                except Exception as e:
                    logger.warning(f"Could not fetch started job {job_id}: {e}")
            
            # 3. Finished jobs (last 50)
            for job_id in list(queue.finished_job_registry.get_job_ids())[-50:]:
                try:
                    job = queue.fetch_job(job_id)
                    if job and _job_matches_filter(job, owner_id, case_id):
                        all_jobs.append(_format_job(job, "finished", queue_name))
                except Exception as e:
                    logger.warning(f"Could not fetch finished job {job_id}: {e}")
            
            # 4. Failed jobs (last 50)
            for job_id in list(queue.failed_job_registry.get_job_ids())[-50:]:
                try:
                    job = queue.fetch_job(job_id)
                    if job and _job_matches_filter(job, owner_id, case_id):
                        all_jobs.append(_format_job(job, "failed", queue_name))
                except Exception as e:
                    logger.warning(f"Could not fetch failed job {job_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing queue {queue_name}: {e}")
    
    # Sort by creation time (newest first)
    all_jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return {
        "total": len(all_jobs),
        "jobs": all_jobs,
        "queues": list(queues_to_check.keys()),
        "filters": {
            "owner_id": owner_id,
            "case_id": case_id,
            "queue_name": queue_name
        }
    }


def _job_matches_filter(job, owner_id, case_id) -> bool:
    """Check if job matches filter criteria"""
    if not job:
        return False
    
    # If no filters specified, include all jobs
    if not owner_id and not case_id:
        return True
    
    # Get job metadata
    job_owner = None
    job_case = None
    
    if hasattr(job, 'meta') and job.meta:
        job_owner = job.meta.get('owner_id')
        job_case = job.meta.get('case_id')
    
    if hasattr(job, 'kwargs') and job.kwargs:
        if not job_owner:
            job_owner = job.kwargs.get('owner_id')
        if not job_case:
            job_case = job.kwargs.get('case_id')
    
    # Filter by owner_id
    if owner_id and job_owner != owner_id:
        return False
    
    # Filter by case_id
    if case_id and job_case != case_id:
        return False
    
    return True


def _format_job(job, status, queue_name) -> dict:
    """Format job for API response - frontend compatible"""
    
    # Extract channels from job args
    channels = []
    if hasattr(job, 'kwargs') and job.kwargs:
        channels = job.kwargs.get('channels', [])
    
    # Extract mode from job function name or queue
    mode = "unknown"
    if hasattr(job, 'kwargs') and job.kwargs:
        mode = job.kwargs.get('mode', 'unknown')
    
    # If mode not in kwargs, infer from queue name
    if mode == "unknown":
        if 'telegram' in queue_name:
            mode = 'scrape'
        elif 'translation' in queue_name:
            mode = 'translation'
        elif 'image' in queue_name:
            mode = 'image-analysis'
        elif 'audio' in queue_name:
            mode = 'audio-transcription'
        elif 'emotion' in queue_name:
            mode = 'emotion-analysis'
    
    # Calculate runtime for started jobs
    runtime = None
    if status == "started" and job.started_at:
        from datetime import datetime, timezone
        runtime_seconds = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        runtime = _format_runtime(runtime_seconds)
    
    return {
        "id": job.id,
        "job_id": job.id,
        "status": status,
        "queue": queue_name,
        "mode": mode,
        "channels": channels,
        "owner_id": job.meta.get('owner_id') if hasattr(job, 'meta') and job.meta else None,
        "case_id": job.meta.get('case_id') if hasattr(job, 'meta') and job.meta else None,
        "created_at": str(job.created_at) if job.created_at else None,
        "started_at": str(job.started_at) if job.started_at else None,
        "ended_at": str(job.ended_at) if job.ended_at else None,
        "runtime": runtime,
        "parent_job_id": job.meta.get('parent_job_id') if hasattr(job, 'meta') and job.meta else None,
        "chained_from": job.meta.get('chained_from') if hasattr(job, 'meta') and job.meta else None,
        "session_name": job.kwargs.get('session_name') if hasattr(job, 'kwargs') and job.kwargs else None,
        "message_id": job.kwargs.get('message_id') if hasattr(job, 'kwargs') and job.kwargs else None,
    }


def _format_runtime(seconds: float) -> str:
    """Format runtime in human-readable format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


@app.delete("/jobs/{job_id}")
def cancel_job(job_id: str, request: Request = None):
    """
    Cancel/remove a specific job
    Works across all queues
    """
    _check_auth(request)
    
    # Try to find job in all queues
    for queue_name, queue in queues.items():
        try:
            job = queue.fetch_job(job_id)
            if job:
                # Cancel the job (stops it if running)
                job.cancel()
                
                # Delete from queue
                job.delete()
                
                logger.info(f"Cancelled and deleted job {job_id} from {queue_name}")
                
                return {
                    "message": f"Job {job_id} cancelled successfully",
                    "job_id": job_id,
                    "queue": queue_name,
                    "status": "cancelled"
                }
        except Exception as e:
            logger.warning(f"Error checking queue {queue_name} for job {job_id}: {e}")
    
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found in any queue")


@app.post("/jobs/{job_id}/requeue")
def requeue_failed_job(job_id: str, request: Request = None):
    """
    Requeue a failed job
    """
    _check_auth(request)
    
    for queue_name, queue in queues.items():
        try:
            job = queue.fetch_job(job_id)
            if job:
                if job.get_status() == 'failed':
                    job.requeue()
                    logger.info(f"Requeued job {job_id} in {queue_name}")
                    return {
                        "message": f"Job {job_id} requeued successfully",
                        "job_id": job_id,
                        "queue": queue_name,
                        "status": "queued"
                    }
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Job {job_id} is not failed (status: {job.get_status()})"
                    )
        except Exception as e:
            logger.warning(f"Error checking queue {queue_name}: {e}")
    
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@app.get("/jobs/stats")
def get_job_stats(
    owner_id: Optional[str] = None,
    case_id: Optional[int] = None,
    request: Request = None
):
    """
    Get statistics about jobs across all queues
    """
    _check_auth(request)
    
    stats = {}
    
    for queue_name, queue in queues.items():
        try:
            # Count jobs by status
            queued_count = len([j for j in queue.jobs if _job_matches_filter(j, owner_id, case_id)])
            started_count = len([
                jid for jid in queue.started_job_registry.get_job_ids()
                if _job_matches_filter(queue.fetch_job(jid), owner_id, case_id)
            ])
            finished_count = len([
                jid for jid in list(queue.finished_job_registry.get_job_ids())[-100:]
                if _job_matches_filter(queue.fetch_job(jid), owner_id, case_id)
            ])
            failed_count = len([
                jid for jid in list(queue.failed_job_registry.get_job_ids())[-100:]
                if _job_matches_filter(queue.fetch_job(jid), owner_id, case_id)
            ])
            
            stats[queue_name] = {
                "queued": queued_count,
                "started": started_count,
                "finished": finished_count,
                "failed": failed_count,
                "total": queued_count + started_count + finished_count + failed_count
            }
        except Exception as e:
            logger.error(f"Error getting stats for {queue_name}: {e}")
            stats[queue_name] = {"error": str(e)}
    
    # Overall totals
    total_stats = {
        "queued": sum(q.get("queued", 0) for q in stats.values()),
        "started": sum(q.get("started", 0) for q in stats.values()),
        "finished": sum(q.get("finished", 0) for q in stats.values()),
        "failed": sum(q.get("failed", 0) for q in stats.values()),
    }
    total_stats["total"] = sum(total_stats.values())
    
    return {
        "by_queue": stats,
        "total": total_stats
    }
@app.get("/health")
def health_check():
    try:
        redis_conn.ping()
        return {
            "status": "healthy",
            "redis": "connected",
            "queues": list(queues.keys())
        }
    except Exception as e:
        return {"status": "unhealthy", "redis": str(e)}