# aether_lib/queue_client.py
"""
Zentrale Queue-Client Library
Wird von Backend UND Workern verwendet
"""

from redis import Redis
from rq import Queue
import os
from aether_lib.schemas.jobs import (
    TelegramScrapePayload,
    TranslationJobPayload,
    ImageJobPayload,
    AudioJobPayload,
    EmotionJobPayload,
    ClassificationJobPayload,
    GeolocationJobPayload,
)
class QueueClient:
    def __init__(self):
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
        self.queues = {
            'telegram': Queue('telegram-jobs', 
                connection=Redis(host=redis_host, port=redis_port, db=0)),
            'translation': Queue('translation-jobs', 
                connection=Redis(host=redis_host, port=redis_port, db=1)),
            'image': Queue('image-jobs', 
                connection=Redis(host=redis_host, port=redis_port, db=2)),
            'audio': Queue('audio-jobs', 
                connection=Redis(host=redis_host, port=redis_port, db=3)),
            'emotion': Queue('emotion-jobs', 
                connection=Redis(host=redis_host, port=redis_port, db=4)),
            'classification': Queue('classification-jobs',
                connection=Redis(host=redis_host, port=redis_port, db=5)),
            'geolocation': Queue('geolocation-jobs',
                connection=Redis(host=redis_host, port=redis_port, db=6)),
        }

    def enqueue_telegram_scraper(self, payload: TelegramScrapePayload, session_string: str):
        """Telegram Scraper"""
        job = self.queues['telegram'].enqueue(
            'workers.telegram_scraper.worker.scrape_telegram_job',
            kwargs={
                'message_id': payload.message_id,
                'session_string': session_string,
                'channels': payload.channels,
                'mode': payload.mode,
                'limit_messages': payload.limit_messages,
                'owner_id': payload.owner_id,
                'case_id': payload.case_id,
            },
            meta={'owner_id': payload.owner_id, 'case_id': payload.case_id}
        )
        return job.id
    def enqueue_translation(self, translation_payload: TranslationJobPayload):
        """Translation Job"""
        job = self.queues['translation'].enqueue(
            'workers.translation_worker.worker.translate_and_update_job',
            kwargs={
                'message_id': translation_payload.message_id,
                'original_text': translation_payload.original_text,
                'source_language': translation_payload.source_language,
                'owner_id': translation_payload.owner_id,
                'case_id': translation_payload.case_id,
                'parent_job_id': translation_payload.parent_job_id,
                'image_text': translation_payload.image_text,
                'audio_text': translation_payload.audio_text,
            },
            meta={'owner_id': translation_payload.owner_id, 'case_id': translation_payload.case_id}
        )
        return job.id

    def enqueue_emotion(self, emotion_payload: EmotionJobPayload):
        """Emotion Analysis"""
        job = self.queues['emotion'].enqueue(
            'workers.emotion_worker.worker.classify_emotion_job',
            kwargs={
                'message_id': emotion_payload.message_id,
                'text': emotion_payload.text,
                'owner_id': emotion_payload.owner_id,
                'case_id': emotion_payload.case_id,
            },
            meta={'owner_id': emotion_payload.owner_id, 'case_id': emotion_payload.case_id}
        )
        return job.id

    def enqueue_classification(self, classification_payload: ClassificationJobPayload):
        """Label Classification"""
        job = self.queues['classification'].enqueue(
            'workers.classification_worker.worker.classify_post_job',
            kwargs={
                'message_id': classification_payload.message_id,
                'text': classification_payload.text,
                'owner_id': classification_payload.owner_id,
                'case_id': classification_payload.case_id,
            },
            meta={'owner_id': classification_payload.owner_id, 'case_id': classification_payload.case_id}
        )
        return job.id

    def enqueue_image_analysis(self, image_analysis_payload: ImageJobPayload):
        """Image Analysis"""
        job = self.queues['image'].enqueue(
            'workers.image_worker.worker.analyze_and_update',
            kwargs={
                'message_id': image_analysis_payload.message_id,
                'image_path': image_analysis_payload.image_path,
                'extract_text': image_analysis_payload.extract_text,
                'detect_objects': image_analysis_payload.detect_objects,
                'translate_extracted_text': image_analysis_payload.translate_extracted_text,
                'owner_id': image_analysis_payload.owner_id,
                'case_id': image_analysis_payload.case_id,
            },
            meta={'owner_id': image_analysis_payload.owner_id, 'case_id': image_analysis_payload.case_id}
        )
        return job.id

    def enqueue_audio_transcription(self, audio_transcription_payload: AudioJobPayload):
        """Audio Transcription"""
        job = self.queues['audio'].enqueue(
            'workers.audio_worker.worker.transcribe_and_update',
            kwargs={
                'message_id': audio_transcription_payload.message_id,
                'media_path': audio_transcription_payload.audio_path,
                'translate_transcription': audio_transcription_payload.translate_transcription,
                'owner_id': audio_transcription_payload.owner_id,
                'case_id': audio_transcription_payload.case_id,
            },
            meta={'owner_id': audio_transcription_payload.owner_id, 'case_id': audio_transcription_payload.case_id}
        )
        return job.id

    def enqueue_geolocation(self, geolocation_payload: GeolocationJobPayload):
        """Geolocation Extraction"""
        job = self.queues['geolocation'].enqueue(
            'workers.geolocation_worker.worker.extract_and_update_location',
            kwargs={
                'message_id': geolocation_payload.message_id,
                'text': geolocation_payload.text,
                'owner_id': geolocation_payload.owner_id,
                'case_id': geolocation_payload.case_id,
            },
            meta={'owner_id': geolocation_payload.owner_id, 'case_id': geolocation_payload.case_id}
        )
        return job.id

# Singleton
queue_client = QueueClient()
