# aether_lib/queue_client.py
"""
Zentrale Queue-Client Library
Wird von Backend UND Workern verwendet
"""

from redis import Redis
from rq import Queue
import os

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
            'geoloacation': Queue('geolocation-jobs',
                connection=Redis(host=redis_host, port=redis_port, db=6)),
        }
        
    def enqueue_translation(self, message_id, text, source_lang, owner_id, case_id):
        """Kann von Backend UND Workern genutzt werden"""
        job = self.queues['translation'].enqueue(
            'workers.translation_worker.worker.translate_and_update',
            message_id=message_id,
            original_text=text,
            source_language=source_lang,
            owner_id=owner_id,
            case_id=case_id,
            meta={'owner_id': owner_id, 'case_id': case_id}
        )
        return job.id
    
    def enqueue_emotion(self, message_id, text, owner_id, case_id):
        """Emotion Analysis"""
        job = self.queues['emotion'].enqueue(
            'workers.emotion_worker.worker.analyze_emotion',
            message_id=message_id,
            text=text,
            owner_id=owner_id,
            case_id=case_id,
            meta={'owner_id': owner_id, 'case_id': case_id}
        )
        return job.id
    
    def enqueue_classification(self, message_id, text, owner_id, case_id):
        """Label Classification"""
        job = self.queues['classification'].enqueue(
            'workers.classification_worker.worker.classify_labels',
            message_id=message_id,
            text=text,
            owner_id=owner_id,
            case_id=case_id,
            meta={'owner_id': owner_id, 'case_id': case_id}
        )
        return job.id
    def enqueue_image_analysis(self, message_id, image_path, extract_text, detect_objects, translate_extracted_text, owner_id, case_id):
        """Image Analysis"""
        job = self.queues['image'].enqueue(
            'workers.image_worker.worker.analyze_image',
            message_id=message_id,
            image_path=image_path,
            extract_text=extract_text,
            detect_objects=detect_objects,
            translate_extracted_text=translate_extracted_text,
            owner_id=owner_id,
            case_id=case_id,
            meta={'owner_id': owner_id, 'case_id': case_id}
        )
        return job.id

    def enqueue_audio_transcription(self, message_id, audio_path, translate_transcription, owner_id, case_id):
        """Audio Transcription"""
        job = self.queues['audio'].enqueue(
            'workers.audio_worker.worker.transcribe_audio',
            message_id=message_id,
            audio_path=audio_path,
            translate_transcription=translate_transcription,
            owner_id=owner_id,
            case_id=case_id,
            meta={'owner_id': owner_id, 'case_id': case_id}
        )
        return job.id
    def enqueue_geolocation(self, message_id, text, owner_id, case_id):
        """Geolocation Extraction"""
        job = self.queues['geoloacation'].enqueue(
            'workers.geolocation_worker.worker.extract_geolocation',
            message_id=message_id,
            text=text,
            owner_id=owner_id,
            case_id=case_id,
            meta={'owner_id': owner_id, 'case_id': case_id}
        )
        return job.id

# Singleton
queue_client = QueueClient()
