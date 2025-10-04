# job-launcher/main.py
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from rq import Queue, Retry
from redis import Redis
import os
import uuid

app = FastAPI()

# Redis-Connection
redis_conn = Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379))
)
telegram_queue = Queue('telegram-jobs', connection=redis_conn)

SECRET = os.getenv("JOB_SECRET_TOKEN", "changeme")

# WICHTIG: Pydantic-Modelle MÜSSEN definiert bleiben!
class ContainerControlRequest(BaseModel):
    owner_id: str
    force: Optional[bool] = False

class SimilarRequest(BaseModel):
    channel: str
    tg_session: str
    owner_id: str = "unknown"
    case_id: Optional[int] = None

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

class JobListRequest(BaseModel):
    owner_id: str
    case_id: Optional[int] = None

def _check_auth(request: Request):
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {SECRET}":
        raise HTTPException(status_code=403, detail="Unauthorized")

# Hilfsfunktion aus deinem Code
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

# job-launcher/main.py

@app.post("/jobs")
def list_jobs(req: JobListRequest, request: Request):
    _check_auth(request)
    
    all_jobs = []
    print(f"[DEBUG] Listing jobs for owner={req.owner_id}, case={req.case_id}")
    
    def add_job_if_matches(job, status):
        if not job:
            print(f"[WARN] Received None job with status={status}")
            return
        
        if not hasattr(job, 'kwargs') or not job.kwargs:
            print(f"[WARN] Job {job.id if hasattr(job, 'id') else 'unknown'} has no kwargs")
            return
        
        job_owner = job.kwargs.get('owner_id')
        if job_owner != req.owner_id:
            print(f"[DEBUG] Skipping job {job.id}: owner mismatch")
            return
        
        if req.case_id is not None:
            job_case = job.kwargs.get('case_id')
            if job_case != req.case_id:
                print(f"[DEBUG] Skipping job {job.id}: case mismatch")
                return
        
        print(f"[DEBUG] Adding job {job.id} with status={status}")
        all_jobs.append({
            "id": job.id,
            "status": status,
            "mode": job.kwargs.get('mode', 'unknown'),
            "channels": job.kwargs.get('channels', []),
            "owner_id": job_owner,
            "case_id": job.kwargs.get('case_id'),
            "session_name": job.kwargs.get('session_name'),
            "created_at": str(job.created_at) if job.created_at else None,
            "started_at": str(job.started_at) if job.started_at else None,
            "ended_at": str(job.ended_at) if job.ended_at else None,
        })
    
    # Started jobs - VERBESSERTER ANSATZ
    started_registry = telegram_queue.started_job_registry
    started_ids = started_registry.get_job_ids()
    print(f"[DEBUG] Found {len(started_ids)} started job IDs in registry")
    
    for full_job_id in started_ids:
        try:
            # Versuche zuerst die volle ID
            job = telegram_queue.fetch_job(full_job_id)
            
            if not job:
                # Falls nicht gefunden, versuche ohne Suffix
                short_id = full_job_id.split(':')[0]
                print(f"[DEBUG] Trying short ID: {short_id}")
                job = telegram_queue.fetch_job(short_id)
            
            if not job:
                print(f"[WARN] Started job {full_job_id} not found (tried full and short ID)")
                continue
            
            print(f"[DEBUG] Found started job: {job.id}, owner={job.kwargs.get('owner_id')}, case={job.kwargs.get('case_id')}")
            add_job_if_matches(job, "started")
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch started job {full_job_id}: {e}")
            import traceback
            traceback.print_exc()
    
    # Queued, Finished, Failed - wie vorher
    for job in telegram_queue.jobs:
        add_job_if_matches(job, "queued")
    
    finished_registry = telegram_queue.finished_job_registry
    for job_id in list(finished_registry.get_job_ids())[-50:]:
        try:
            job = telegram_queue.fetch_job(job_id)
            if job:
                add_job_if_matches(job, "finished")
        except Exception as e:
            print(f"[ERROR] Failed to fetch finished job: {e}")
    
    failed_registry = telegram_queue.failed_job_registry
    for job_id in list(failed_registry.get_job_ids())[-50:]:
        try:
            job = telegram_queue.fetch_job(job_id)
            if job:
                add_job_if_matches(job, "failed")
        except Exception as e:
            print(f"[ERROR] Failed to fetch failed job: {e}")
    
    print(f"[DEBUG] Returning {len(all_jobs)} total jobs")
    return {"jobs": all_jobs}
@app.post("/scrape")
def launch_scraper(req: ScrapeRequest, request: Request):
    _check_auth(request)
    
    MAX_RECURSION_DEPTH = 3
    if req.depth >= MAX_RECURSION_DEPTH:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum recursion depth ({MAX_RECURSION_DEPTH}) exceeded"
        )
    
    session_string, user_info = load_string_session(req.tg_session, req.owner_id)
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    print(f"[QUEUE] Enqueueing {req.mode} job for: {req.channels} (depth: {req.depth})")
    
    job_id = f"{req.mode}_{uuid.uuid4().hex[:6]}"
    
    job = telegram_queue.enqueue(
        'rq_worker.run_job',
        kwargs={
            'mode': req.mode,
            'channels': req.channels,
            'session_string': session_string,
            'session_name': req.tg_session,
            'recursive': req.recursive,
            'neo4j_write': req.neo4j,
            'owner_id': req.owner_id,
            'parent_container_id': req.parent_container_id,
            'depth': req.depth,
            'case_id': req.case_id,
        },
        job_id=job_id,
        timeout='6h',
        result_ttl=86400,    # Ergebnis 24h behalten
        failure_ttl=86400,   # Fehler 24h behalten
        ttl=None,              # ← NEU: Job-Daten niemals löschen während Ausführung
        retry=Retry(max=3, interval=[10, 30, 60])
    )
    
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "queued_at": str(job.enqueued_at)
    }
@app.post("/similar")
def launch_similarity(req: SimilarRequest, request: Request):
    _check_auth(request)
    
    session_string, user_info = load_string_session(req.tg_session, req.owner_id)
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    print(f"[QUEUE] Enqueueing similar job for: {req.channel}")
    
    job = telegram_queue.enqueue(
        'rq_worker.run_job',
        kwargs={
            'mode': 'similar',
            'channels': [req.channel],
            'session_string': session_string,
            'session_name': req.tg_session,
            'recursive': False,
            'neo4j_write': True,
            'owner_id': req.owner_id,
            'case_id': req.case_id,
        },
        job_id=f"similar_{uuid.uuid4().hex[:6]}",
        timeout='2h',
    )
    
    return {
        "job_id": job.id,
        "status": job.get_status()
    }

# job-launcher/main.py

@app.delete("/jobs/{job_id}")
def cancel_job(job_id: str, req: ContainerControlRequest, request: Request):
    _check_auth(request)
    
    job = telegram_queue.fetch_job(job_id)
    if not job:
        # Auch wenn Job nicht gefunden, versuche Registry cleanup
        print(f"[WARN] Job {job_id} not found, cleaning registries anyway")
        _cleanup_job_from_registries(job_id)
        return {"message": f"Job {job_id} removed from registries", "status": "cancelled"}
    
    # Verify ownership
    if job.kwargs.get('owner_id') != req.owner_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Cancel and cleanup
    job.cancel()
    _cleanup_job_from_registries(job_id)
    job.delete()
    
    print(f"[INFO] Job {job_id} cancelled and deleted")
    return {"message": f"Job {job_id} cancelled", "status": "cancelled"}

def _cleanup_job_from_registries(job_id: str):
    """Remove job from all registries"""
    try:
        # Try both short and long ID formats
        for registry in [
            telegram_queue.started_job_registry,
            telegram_queue.finished_job_registry,
            telegram_queue.failed_job_registry,
            telegram_queue.deferred_job_registry,
        ]:
            # Remove by job_id
            try:
                registry.remove(job_id)
                print(f"[DEBUG] Removed {job_id} from {registry.__class__.__name__}")
            except:
                pass
            
            # Try with registry suffix
            for reg_job_id in registry.get_job_ids():
                if reg_job_id.startswith(job_id):
                    try:
                        registry.remove(reg_job_id)
                        print(f"[DEBUG] Removed {reg_job_id} from registry")
                    except:
                        pass
    except Exception as e:
        print(f"[ERROR] Registry cleanup failed: {e}")
@app.get("/jobs/{job_id}")
def get_job_status(job_id: str, request: Request):
    """Get status of a specific job"""
    _check_auth(request)
    
    job = telegram_queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "status": job.get_status(),
        "result": job.result,
        "exc_info": job.exc_info,
        "created_at": str(job.created_at) if job.created_at else None,
        "started_at": str(job.started_at) if job.started_at else None,
        "ended_at": str(job.ended_at) if job.ended_at else None,
    }

# Health check
@app.get("/health")
def health_check():
    try:
        redis_conn.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "redis": str(e)}