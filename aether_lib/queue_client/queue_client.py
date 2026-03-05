# aether_lib/queue_client.py
"""
Zentrale Queue-Client Library
Wird von Backend UND Workern verwendet
"""

from redis import Redis
from rq import Queue
import os
import logging

logger = logging.getLogger(__name__)

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
        self.use_modal = os.getenv("USE_MODAL", "false").lower() == "true"
        self.modal_emotion_url = os.getenv("MODAL_EMOTION_URL", "")
        self.modal_translation_url = os.getenv("MODAL_TRANSLATION_URL", "")

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
                'enable_translation': payload.enable_translation,
                'enable_image_analysis': payload.enable_image_analysis,
                'enable_audio_transcription': payload.enable_audio_transcription,
                'enable_emotion_analysis': payload.enable_emotion_analysis,
                'enable_label_classifier': payload.enable_label_classifier,
                'enable_geolocation_extraction': payload.enable_geolocation_extraction,
                'ocr_languages': payload.ocr_languages
            },
            meta={'owner_id': payload.owner_id, 'case_id': payload.case_id}
        )
        return job.id
    def enqueue_translation(self, translation_payload: TranslationJobPayload):
        """Translation Job — uses Modal HTTP endpoint when USE_MODAL=true, otherwise RQ."""
        if self.use_modal and self.modal_translation_url:
            self._enqueue_translation_modal(translation_payload)
            return None
        job = self.queues['translation'].enqueue(
            'workers.translation_worker.worker.translate_and_update',
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

    def _enqueue_translation_modal(self, translation_payload: TranslationJobPayload):
        """Fire-and-forget Modal translation call in a background thread."""
        import threading
        import httpx

        def _call():
            try:
                resp = httpx.post(
                    self.modal_translation_url,
                    json={
                        "text": translation_payload.original_text,
                        "source_language": translation_payload.source_language,
                        "target_language": "de",
                    },
                    timeout=300.0,
                )
                resp.raise_for_status()
                translated = resp.json().get("translated_text", "")
                if translated:
                    self._neo4j_update_translation(
                        translation_payload.message_id,
                        translation_payload.owner_id,
                        translated,
                        translation_payload.image_text,
                        translation_payload.audio_text,
                    )
                    # Chain emotion analysis on the translated text
                    if len(translated.strip()) > 10 and self.modal_emotion_url:
                        self._enqueue_emotion_modal_sync(
                            translation_payload.message_id,
                            translated,
                            translation_payload.owner_id,
                            translation_payload.case_id,
                        )
            except Exception as e:
                logger.error(f"Modal translation failed for {translation_payload.message_id}: {e}")

        threading.Thread(target=_call, daemon=True).start()

    def enqueue_emotion(self, emotion_payload: EmotionJobPayload):
        """Emotion Analysis — uses Modal HTTP endpoint when USE_MODAL=true, otherwise RQ."""
        if self.use_modal and self.modal_emotion_url:
            self._enqueue_emotion_modal(emotion_payload)
            return None
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

    def _enqueue_emotion_modal(self, emotion_payload: EmotionJobPayload):
        """Fire-and-forget Modal emotion call in a background thread."""
        import threading
        threading.Thread(
            target=self._enqueue_emotion_modal_sync,
            args=(emotion_payload.message_id, emotion_payload.text,
                  emotion_payload.owner_id, emotion_payload.case_id),
            daemon=True,
        ).start()

    def _enqueue_emotion_modal_sync(self, message_id: str, text: str, owner_id: str, case_id: str):
        """Synchronous Modal emotion call — runs inside a background thread."""
        import httpx
        try:
            resp = httpx.post(
                self.modal_emotion_url,
                json={"text": text, "threshold": 0.3, "top_k": 3},
                timeout=300.0,
            )
            resp.raise_for_status()
            emotions = resp.json().get("emotions", [])
            if emotions:
                self._neo4j_store_emotions(message_id, owner_id, emotions)
        except Exception as e:
            logger.error(f"Modal emotion failed for {message_id}: {e}")

    def _neo4j_update_translation(self, message_id: str, owner_id: str,
                                   translated_text: str, image_text: bool, audio_text: bool):
        """Write translated text back to Neo4j."""
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            with driver.session() as session:
                if image_text:
                    cypher = "MATCH (m:Message {mid: $mid, owner_id: $owner_id}) SET m.image_text_translated = $text"
                elif audio_text:
                    cypher = "MATCH (m:Message {mid: $mid, owner_id: $owner_id}) SET m.audio_text_translated = $text"
                else:
                    cypher = "MATCH (m:Message {mid: $mid, owner_id: $owner_id}) SET m.translated_text = $text, m.translation_status = 'completed'"
                session.run(cypher, mid=message_id, owner_id=owner_id, text=translated_text)
        finally:
            driver.close()

    def _neo4j_store_emotions(self, message_id: str, owner_id: str, emotions: list):
        """Write emotion results to Neo4j as Emotion nodes with HAS_EMOTION relationships."""
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")
        cypher = """
        MATCH (m:Message {mid: $message_id})
        WHERE $owner_id IS NULL OR m.owner_id = $owner_id
        MERGE (e:Emotion {label_id: $label_id})
        ON CREATE SET e.name = $label, e.label_id = $label_id, e.created_at = datetime()
        MERGE (m)-[r:HAS_EMOTION]->(e)
        ON CREATE SET r.confidence = $confidence, r.method = $method,
                      r.source_emotions = $source_emotions, r.detected_at = datetime()
        ON MATCH SET  r.confidence = CASE WHEN $confidence > r.confidence
                          THEN $confidence ELSE r.confidence END,
                      r.method = $method, r.source_emotions = $source_emotions,
                      r.updated_at = datetime()
        SET m.emotion_status = 'completed', m.emotion_analyzed_at = datetime()
        """
        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            with driver.session() as session:
                for emo in emotions:
                    session.run(
                        cypher,
                        message_id=message_id,
                        owner_id=owner_id,
                        label_id=emo["label_id"],
                        label=emo["label"],
                        confidence=emo["confidence"],
                        method=emo.get("method", "unknown"),
                        source_emotions=emo.get("source_emotions", []),
                    )
        finally:
            driver.close()

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
                'modes': image_analysis_payload.ocr_languages
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
