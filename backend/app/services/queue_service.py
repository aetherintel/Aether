"""
Queue Service - Centralized Job Queue Management
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
    def __init__(self):
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        self.redis_connections = {
            'telegram':       Redis(host=redis_host, port=redis_port, db=0),
            'translation':    Redis(host=redis_host, port=redis_port, db=1),
            'image':          Redis(host=redis_host, port=redis_port, db=2),
            'audio':          Redis(host=redis_host, port=redis_port, db=3),
            'emotion':        Redis(host=redis_host, port=redis_port, db=4),
            'classification': Redis(host=redis_host, port=redis_port, db=5),
            'geolocation':    Redis(host=redis_host, port=redis_port, db=6),
        }

        self.queues: Dict[str, Queue] = {
            'telegram':       Queue('telegram-jobs',       connection=self.redis_connections['telegram']),
            'translation':    Queue('translation-jobs',    connection=self.redis_connections['translation']),
            'image':          Queue('image-jobs',          connection=self.redis_connections['image']),
            'audio':          Queue('audio-jobs',          connection=self.redis_connections['audio']),
            'emotion':        Queue('emotion-jobs',        connection=self.redis_connections['emotion']),
            'classification': Queue('classification-jobs', connection=self.redis_connections['classification']),
            'geolocation':    Queue('geolocation-jobs',    connection=self.redis_connections['geolocation']),
        }

        logger.info(f"✅ QueueService initialized with {len(self.queues)} queues")

    # ========================================================================
    # TELEGRAM SCRAPER JOBS
    # ========================================================================

    def enqueue_telegram_scraper(self, payload: TelegramScrapePayload, session_string: str) -> str:
        job_id = f"{payload.mode}_{uuid.uuid4().hex[:6]}"
        logger.info(f"📤 Enqueueing Telegram scraper job: {job_id}")

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
            meta={'owner_id': payload.owner_id, 'case_id': payload.case_id},
        )

        logger.info(f"✅ Telegram job enqueued: {job.id}")
        return job.id

    # ========================================================================
    # TRANSLATION JOBS  — RQ → Modal worker
    # ========================================================================

    def enqueue_translation(self, payload: TranslationJobPayload) -> str:
        job_id = f"translation_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        logger.info(f"📤 Enqueueing translation job: {job_id}")

        job = self.queues['translation'].enqueue(
            'translation_worker.modal_worker.translate_and_update',
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
            },
        )

        logger.info(f"✅ Translation job enqueued: {job.id}")
        return job.id

    # ========================================================================
    # IMAGE ANALYSIS JOBS
    # ========================================================================

    def enqueue_image_analysis(self, payload: ImageJobPayload) -> str:
        job_id = f"image_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        logger.info(f"📤 Enqueueing image analysis job: {job_id}")

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
            meta={'owner_id': payload.owner_id, 'case_id': payload.case_id},
        )

        logger.info(f"✅ Image analysis job enqueued: {job.id}")
        return job.id

    # ========================================================================
    # AUDIO TRANSCRIPTION JOBS
    # ========================================================================

    def enqueue_audio_transcription(self, payload: AudioJobPayload) -> str:
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
            },
        )

        logger.info(f"✅ Audio transcription job enqueued: {job.id}")
        return job.id

    # ========================================================================
    # EMOTION ANALYSIS JOBS  — RQ → Modal worker
    # ========================================================================

    def enqueue_emotion_analysis(self, payload: EmotionJobPayload) -> str:
        job_id = f"emotion_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        logger.info(f"📤 Enqueueing emotion analysis job: {job_id}")

        job = self.queues['emotion'].enqueue(
            'emotion_worker.modal_worker.classify_emotion_job',
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
            },
        )

        logger.info(f"✅ Emotion analysis job enqueued: {job.id}")
        return job.id

    # ========================================================================
    # CLASSIFICATION JOBS  — RQ → Modal worker
    # ========================================================================

    def enqueue_classification(self, payload: ClassificationJobPayload) -> str:
        job_id = f"classification_{payload.message_id}_{uuid.uuid4().hex[:6]}"
        logger.info(f"📤 Enqueueing classification job: {job_id}")

        job = self.queues['classification'].enqueue(
            'classification_worker.modal_worker.classify_post_job',
            message_id=payload.message_id,
            text=payload.text,
            owner_id=payload.owner_id,
            case_id=payload.case_id,
            threshold=getattr(payload, 'threshold', 0.3),
            top_k=getattr(payload, 'top_k', 3),
            job_timeout='5m',
            result_ttl=600,
            failure_ttl=86400,
            ttl=None,
            meta={
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
                'parent_job_id': payload.parent_job_id,
            },
        )

        logger.info(f"✅ Classification job enqueued: {job.id}")
        return job.id

    # ========================================================================
    # GEOLOCATION EXTRACTION JOBS
    # ========================================================================

    def enqueue_geolocation(self, payload: GeolocationJobPayload) -> str:
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
            },
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
        queue_name: Optional[str] = None,
    ) -> Dict:
        all_jobs = []

        if queue_name:
            if queue_name not in self.queues:
                raise ValueError(f"Unknown queue: {queue_name}")
            queues_to_check = {queue_name: self.queues[queue_name]}
        else:
            queues_to_check = self.queues

        for qname, queue in queues_to_check.items():
            try:
                for job in queue.jobs:
                    if job and self._job_matches_filter(job, owner_id, case_id):
                        all_jobs.append(self._format_job(job, "queued", qname))

                started_registry = StartedJobRegistry(queue=queue)
                for job_id in started_registry.get_job_ids():
                    try:
                        job = queue.fetch_job(job_id)
                        if job and self._job_matches_filter(job, owner_id, case_id):
                            all_jobs.append(self._format_job(job, "started", qname))
                    except Exception as e:
                        logger.warning(f"Could not fetch started job {job_id}: {e}")

                finished_registry = FinishedJobRegistry(queue=queue)
                for job_id in list(finished_registry.get_job_ids())[-50:]:
                    try:
                        job = queue.fetch_job(job_id)
                        if job and self._job_matches_filter(job, owner_id, case_id):
                            all_jobs.append(self._format_job(job, "finished", qname))
                    except Exception as e:
                        logger.warning(f"Could not fetch finished job {job_id}: {e}")

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

        all_jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return {
            "total": len(all_jobs),
            "jobs": all_jobs,
            "queues": list(queues_to_check.keys()),
            "filters": {"owner_id": owner_id, "case_id": case_id, "queue_name": queue_name},
        }

    def _job_matches_filter(self, job: Job, owner_id: Optional[str], case_id: Optional[int]) -> bool:
        if not job:
            return False
        if not owner_id and not case_id:
            return True

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

        if owner_id and job_owner != owner_id:
            return False
        if case_id and job_case != case_id:
            return False

        return True

    def _format_job(self, job: Job, status: str, queue_name: str) -> dict:
        channels = []
        if hasattr(job, 'kwargs') and job.kwargs:
            channels = job.kwargs.get('channels', [])

        mode = "unknown"
        if hasattr(job, 'kwargs') and job.kwargs:
            mode = job.kwargs.get('mode', queue_name)

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

    def fetch_job(self, job_id: str) -> Optional[Job]:
        """Fetch a job by ID across all queues without modifying it."""
        for queue in self.queues.values():
            try:
                job = queue.fetch_job(job_id)
                if job:
                    return job
            except Exception:
                pass
        return None

    def cancel_job(self, job_id: str) -> bool:
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

    # ========================================================================
    # RECONCILIATION SUPPORT
    # ========================================================================

    def get_active_message_ids(self, queue_name: str) -> set[str]:
        queue = self.queues.get(queue_name)
        if not queue:
            return set()

        active: set[str] = set()

        def _extract(job: Job | None):
            if not job:
                return
            mid = None
            if hasattr(job, 'meta') and job.meta:
                mid = job.meta.get('message_id')
            if not mid and hasattr(job, 'kwargs') and job.kwargs:
                mid = job.kwargs.get('message_id')
            if mid:
                active.add(str(mid))

        try:
            for job in queue.jobs:
                _extract(job)
        except Exception as e:
            logger.warning(f"Error reading queued jobs for {queue_name}: {e}")

        try:
            started_registry = StartedJobRegistry(queue=queue)
            for job_id in started_registry.get_job_ids():
                try:
                    _extract(queue.fetch_job(job_id))
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error reading started jobs for {queue_name}: {e}")

        return active


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

queue_service = QueueService()
