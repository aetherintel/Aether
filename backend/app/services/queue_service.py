"""
Queue Service - Centralized Job Queue Management
Replaces the job-launcher service by managing RQ queues directly from backend.

This service:
- Manages connections to multiple Redis DBs (one per job type)
- Enqueues jobs to appropriate queues
- Monitors and lists jobs across all queues
- Provides job cancellation and status tracking
"""
import os
import uuid
import logging
from typing import Dict, List, Optional
from datetime import datetime

from redis import Redis
from rq import Queue, Retry
from rq.job import Job
from rq.registry import (
    StartedJobRegistry,
    FinishedJobRegistry,
    FailedJobRegistry,
)

from aether_lib.schemas.jobs import (
    TelegramScrapePayload,
    TranslationJobPayload,
    ImageJobPayload,
    AudioJobPayload,
    EmotionJobPayload,
    ClassificationJobPayload,
    GeolocationJobPayload,
)

logger = logging.getLogger(__name__)


class QueueService:
    """
    Centralized queue management service
    Handles all job enqueueing and monitoring
    """
    
    def __init__(self):
        """Initialize Redis connections and RQ queues"""
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
        # Initialize Redis connections (one per job type for isolation)
        self.redis_connections = {
            'telegram': Redis(host=redis_host, port=redis_port, db=0),
            'translation': Redis(host=redis_host, port=redis_port, db=1),
            'image': Redis(host=redis_host, port=redis_port, db=2),
            'audio': Redis(host=redis_host, port=redis_port, db=3),
            'emotion': Redis(host=redis_host, port=redis_port, db=4),
            'classification': Redis(host=redis_host, port=redis_port, db=5),
            'geolocation': Redis(host=redis_host, port=redis_port, db=6),
        }
        
        # Initialize RQ queues
        self.queues: Dict[str, Queue] = {
            'telegram': Queue('telegram-jobs', connection=self.redis_connections['telegram']),
            'translation': Queue('translation-jobs', connection=self.redis_connections['translation']),
            'image': Queue('image-jobs', connection=self.redis_connections['image']),
            'audio': Queue('audio-jobs', connection=self.redis_connections['audio']),
            'emotion': Queue('emotion-jobs', connection=self.redis_connections['emotion']),
            'classification': Queue('classification-jobs', connection=self.redis_connections['classification']),
            'geolocation': Queue('geolocation-jobs', connection=self.redis_connections['geolocation']),
        }
        
        logger.info(f"✅ QueueService initialized with {len(self.queues)} queues")
    
    # ========================================================================
    # TELEGRAM SCRAPER JOBS
    # ========================================================================
    
    def enqueue_telegram_scraper(
        self,
        payload: TelegramScrapePayload,
        session_string: str
    ) -> str:
        """
        Enqueue a Telegram scraper job
        
        Args:
            payload: Scraper configuration
            session_string: Telegram session string for authentication
            
        Returns:
            Job ID
        """
        job_id = f"{payload.mode}_{uuid.uuid4().hex[:6]}"
        
        logger.info(f"📤 Enqueueing Telegram scraper job: {job_id}")
        logger.info(f"   Channels: {', '.join(payload.channels)}")
        logger.info(f"   Session: {payload.session_name}")
        
        job = self.queues['telegram'].enqueue(
            'telegram_job.entry.run_job',
            kwargs={
                'mode': payload.mode,
                'channels': payload.channels,
                'session_string': session_string,
                'session_name': payload.session_name,
                'recursive': payload.recursive,
                'neo4j_write': payload.neo4j_write,
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
                'enable_translation': payload.enable_translation,
                'enable_image_analysis': payload.enable_image_analysis,
                'enable_audio_transcription': payload.enable_audio_transcription,
                'enable_emotion_analysis': payload.enable_emotion_analysis,
                'enable_label_classifier': payload.enable_label_classifier,
                'enable_geolocation_extraction': payload.enable_geolocation_extraction,
            },
            job_id=job_id,
            job_timeout='6h',
            result_ttl=86400,
            failure_ttl=86400,
            ttl=None,
            retry=Retry(max=3, interval=[10, 30, 60]),
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
            }
        )
        
        logger.info(f"✅ Job enqueued: {job.id}")
        return job.id
    
    # ========================================================================
    # TRANSLATION JOBS
    # ========================================================================
    
    def enqueue_translation(self, payload: TranslationJobPayload) -> str:
        """Enqueue a translation job"""
        job_id = f"translation_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        
        logger.info(f"📤 Enqueueing translation job: {job_id}")
        
        job = self.queues['translation'].enqueue(
            'workers.translation_worker.worker.translate_and_update',
            message_id=payload.message_id,
            original_text=payload.original_text,
            source_language=payload.source_language,
            owner_id=payload.owner_id,
            case_id=payload.case_id,
            parent_job_id=payload.parent_job_id,
            chained_from=payload.chained_from,
            image_text=payload.image_text,
            audio_text=payload.audio_text,
            job_id=job_id,
            job_timeout='10m',
            result_ttl=3600,
            failure_ttl=86400,
            ttl=None,
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
                'parent_job_id': payload.parent_job_id,
                'chained_from': payload.chained_from,
                'image_text': payload.image_text,
                'audio_text': payload.audio_text,
            }
        )
        
        logger.info(f"✅ Translation job enqueued: {job.id}")
        return job.id
    
    # ========================================================================
    # IMAGE ANALYSIS JOBS
    # ========================================================================
    
    def enqueue_image_analysis(self, payload: ImageJobPayload) -> str:
        """Enqueue an image analysis job"""
        job_id = f"image_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        
        logger.info(f"📤 Enqueueing image analysis job: {job_id}")
        logger.info(f"   OCR: {payload.extract_text}, Objects: {payload.detect_objects}")
        
        job = self.queues['image'].enqueue(
            'workers.image_worker.worker.analyze_and_update',
            message_id=payload.message_id,
            image_path=payload.image_path,
            extract_text=payload.extract_text,
            detect_objects=payload.detect_objects,
            translate_extracted_text=payload.translate_extracted_text,
            owner_id=payload.owner_id,
            case_id=payload.case_id,
            job_id=job_id,
            job_timeout='5m',
            result_ttl=86400,
            failure_ttl=86400,
            ttl=None,
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
            }
        )
        
        logger.info(f"✅ Image analysis job enqueued: {job.id}")
        return job.id
    
    # ========================================================================
    # AUDIO TRANSCRIPTION JOBS
    # ========================================================================
    
    def enqueue_audio_transcription(self, payload: AudioJobPayload) -> str:
        """Enqueue an audio transcription job"""
        job_id = f"audio_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        
        logger.info(f"📤 Enqueueing audio transcription job: {job_id}")
        
        job = self.queues['audio'].enqueue(
            'workers.audio_worker.worker.transcribe_and_update',
            message_id=payload.message_id,
            media_path=payload.audio_path,
            translate_transcription=payload.translate_transcription,
            owner_id=payload.owner_id,
            case_id=payload.case_id,
            parent_job_id=payload.parent_job_id,
            job_id=job_id,
            job_timeout='10m',
            result_ttl=86400,
            failure_ttl=86400,
            ttl=None,
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
                'parent_job_id': payload.parent_job_id,
            }
        )
        
        logger.info(f"✅ Audio transcription job enqueued: {job.id}")
        return job.id
    
    # ========================================================================
    # EMOTION ANALYSIS JOBS
    # ========================================================================
    
    def enqueue_emotion_analysis(self, payload: EmotionJobPayload) -> str:
        """Enqueue an emotion analysis job"""
        job_id = f"emotion_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        
        logger.info(f"📤 Enqueueing emotion analysis job: {job_id}")
        
        job = self.queues['emotion'].enqueue(
            'workers.emotion_worker.worker.classify_emotion_job',
            message_id=payload.message_id,
            text=payload.text,
            threshold=payload.threshold,
            owner_id=payload.owner_id,
            case_id=payload.case_id,
            top_k=payload.top_k,
            job_timeout='5m',
            result_ttl=600,
            failure_ttl=86400,
            ttl=None,
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
                'parent_job_id': payload.parent_job_id,
                'chained_from': payload.chained_from,
            }
        )
        
        logger.info(f"✅ Emotion analysis job enqueued: {job.id}")
        return job.id
    
    # ========================================================================
    # CLASSIFICATION JOBS
    # ========================================================================
    
    def enqueue_classification(self, payload: ClassificationJobPayload) -> str:
        """Enqueue a text classification job"""
        job_id = f"classification_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        
        logger.info(f"📤 Enqueueing classification job: {job_id}")
        
        job = self.queues['classification'].enqueue(
            'worker.classify_post_job',
            message_id=payload.message_id,
            text=payload.text,
            neo4j_uri=os.getenv('NEO4J_URI'),
            neo4j_user=os.getenv('NEO4J_USER'),
            neo4j_password=os.getenv('NEO4J_PASSWORD'),
            owner_id=payload.owner_id,
            case_id=payload.case_id,
            job_timeout='5m',
            result_ttl=600,
            failure_ttl=86400,
            ttl=None,
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
                'parent_job_id': payload.parent_job_id,
                'chained_from': payload.chained_from,
            }
        )
        
        logger.info(f"✅ Classification job enqueued: {job.id}")
        return job.id
    
    # ========================================================================
    # GEOLOCATION EXTRACTION JOBS
    # ========================================================================
    
    def enqueue_geolocation(self, payload: GeolocationJobPayload) -> str:
        """Enqueue a geolocation extraction job"""
        job_id = f"geo_{uuid.uuid4().hex[:6]}"
        
        logger.info(f"📤 Enqueueing geolocation job: {job_id}")
        
        job = self.queues['geolocation'].enqueue(
            'workers.geolocation_worker.worker.extract_and_update_location',
            message_id=payload.message_id,
            text=payload.text,
            owner_id=payload.owner_id,
            case_id=payload.case_id,
            job_timeout='5m',
            result_ttl=86400,
            failure_ttl=86400,
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
                'message_id': payload.message_id,
            }
        )
        
        logger.info(f"✅ Geolocation job enqueued: {job.id}")
        return job.id
    
    # ========================================================================
    # JOB MONITORING
    # ========================================================================
    
    def list_jobs(
        self,
        owner_id: Optional[str] = None,
        case_id: Optional[int] = None,
        queue_name: Optional[str] = None
    ) -> Dict:
        """
        List jobs across all queues with filtering
        
        Args:
            owner_id: Filter by owner ID
            case_id: Filter by case ID
            queue_name: Filter by specific queue
            
        Returns:
            Dictionary with jobs list and metadata
        """
        all_jobs = []
        
        # Determine which queues to check
        if queue_name:
            if queue_name not in self.queues:
                raise ValueError(f"Unknown queue: {queue_name}")
            queues_to_check = {queue_name: self.queues[queue_name]}
        else:
            queues_to_check = self.queues
        
        for qname, queue in queues_to_check.items():
            try:
                # 1. Queued jobs (waiting to be processed)
                for job in queue.jobs:
                    if job and self._job_matches_filter(job, owner_id, case_id):
                        all_jobs.append(self._format_job(job, "queued", qname))
                
                # 2. Started jobs (currently processing)
                started_registry = StartedJobRegistry(queue=queue)
                for job_id in started_registry.get_job_ids():
                    try:
                        job = queue.fetch_job(job_id)
                        if job and self._job_matches_filter(job, owner_id, case_id):
                            all_jobs.append(self._format_job(job, "started", qname))
                    except Exception as e:
                        logger.warning(f"Could not fetch started job {job_id}: {e}")
                
                # 3. Finished jobs (last 50)
                finished_registry = FinishedJobRegistry(queue=queue)
                for job_id in list(finished_registry.get_job_ids())[-50:]:
                    try:
                        job = queue.fetch_job(job_id)
                        if job and self._job_matches_filter(job, owner_id, case_id):
                            all_jobs.append(self._format_job(job, "finished", qname))
                    except Exception as e:
                        logger.warning(f"Could not fetch finished job {job_id}: {e}")
                
                # 4. Failed jobs (last 50)
                failed_registry = FailedJobRegistry(queue=queue)
                for job_id in list(failed_registry.get_job_ids())[-50:]:
                    try:
                        job = queue.fetch_job(job_id)
                        if job and self._job_matches_filter(job, owner_id, case_id):
                            all_jobs.append(self._format_job(job, "failed", qname))
                    except Exception as e:
                        logger.warning(f"Could not fetch failed job {job_id}: {e}")
                        
            except Exception as e:
                logger.error(f"Error processing queue {qname}: {e}")
        
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
    
    def _job_matches_filter(self, job: Job, owner_id: Optional[str], case_id: Optional[int]) -> bool:
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
    
    def _format_job(self, job: Job, status: str, queue_name: str) -> dict:
        """Format job for API response"""
        # Extract channels from job args
        channels = []
        if hasattr(job, 'kwargs') and job.kwargs:
            channels = job.kwargs.get('channels', [])
        
        # Extract mode from job function name or queue
        mode = "unknown"
        if hasattr(job, 'kwargs') and job.kwargs:
            mode = job.kwargs.get('mode', queue_name)
        
        # Calculate runtime if started
        runtime = None
        if status == "started" and job.started_at:
            runtime = str(datetime.now() - job.started_at)
        elif status == "finished" and job.started_at and job.ended_at:
            runtime = str(job.ended_at - job.started_at)
        
        return {
            "job_id": job.id,
            "id": job.id,
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
            "result": job.result if status == "finished" else None,
            "exc_info": job.exc_info if status == "failed" else None,
        }
    
    # ========================================================================
    # JOB CANCELLATION
    # ========================================================================
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job by ID
        Searches across all queues
        
        Returns:
            True if job was found and cancelled, False otherwise
        """
        for queue_name, queue in self.queues.items():
            try:
                job = queue.fetch_job(job_id)
                if job:
                    job.cancel()
                    logger.info(f"✅ Cancelled job {job_id} in queue {queue_name}")
                    return True
            except Exception as e:
                logger.warning(f"Error cancelling job {job_id} in {queue_name}: {e}")
        
        logger.warning(f"❌ Job {job_id} not found in any queue")
        return False


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

queue_service = QueueService()