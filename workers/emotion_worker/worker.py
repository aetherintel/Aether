# ============================================================================
# workers/emotion_worker/worker.py (UPDATED for aether_lib architecture)
# Complete RQ Worker Implementation with Correct Neo4j Integration
# ============================================================================

import asyncio
import os
import logging
from redis import Redis
from rq import Queue
import torch
from transformers import pipeline
from neo4j import AsyncGraphDatabase

# Import our Neo4j utilities
from .neo4j_utils import (
    store_emotions_in_neo4j,
    get_messages_pending_emotion_analysis,
    mark_emotion_analysis_failed
)

# ---------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# German-Emotions Model - Load ONCE at startup
# ---------------------------------------------------------------
logger.info("🚀 Loading German-Emotions model at worker startup...")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"📱 Using device: {DEVICE}")

# Police investigation emotion labels (20 categories)
POLICE_LABELS = {
    1: "Wut / Aggression",
    2: "Hass / Feindbild", 
    3: "Empörung / Entrüstung",
    4: "Angst / Bedrohungsempfinden",
    5: "Panik / Hysterie",
    6: "Verzweiflung / Hoffnungslosigkeit",
    7: "Trauer / Mitgefühl",
    8: "Solidarität / Zusammenhalt",
    9: "Stolz / Selbstermächtigung",
    10: "Freude / Zufriedenheit",
    11: "Ironie / Sarkasmus",
    12: "Aggressive Motivation / Aufpeitschend",
    13: "Feindliche Mobilisierung",
    14: "Resignation / Rückzug",
    15: "Misstrauen / Paranoia",
    16: "Euphorie / Begeisterung",
    17: "Zynismus / Verachtung",
    18: "Mobilisierende Hoffnung",
    19: "Neutral / Informationsorientiert",
    20: "Ambivalent / Gemischt"
}

# GoEmotions → Police Label Mapping
EMOTION_TO_POLICE = {
    'anger': 1, 'annoyance': 1,
    'disgust': 2, 'disapproval': 2,
    'disappointment': 3,
    'fear': 4,
    'nervousness': 5,
    'sadness': 6, 'grief': 7, 'remorse': 7, 'embarrassment': 6,
    'caring': 8, 'gratitude': 8, 'love': 8,
    'pride': 9, 'admiration': 9,
    'joy': 10, 'amusement': 10, 'relief': 10,
    'excitement': 16, 'optimism': 18, 'desire': 16,
    'curiosity': 19, 'confusion': 15, 'surprise': 19, 'realization': 19, 'approval': 19,
    'neutral': 19,
}

# Emotion combinations for complex labels
EMOTION_COMBINATIONS = {
    frozenset(['anger', 'excitement']): 12,  # Aggressive motivation
    frozenset(['anger', 'desire']): 12,
    frozenset(['anger', 'pride']): 13,  # Hostile mobilization
    frozenset(['disgust', 'anger']): 13,
    frozenset(['amusement', 'annoyance']): 11,  # Irony
    frozenset(['amusement', 'disapproval']): 11,
    frozenset(['amusement', 'disgust']): 17,  # Cynicism
    frozenset(['sadness', 'disappointment']): 14,  # Resignation
    frozenset(['disappointment', 'disapproval']): 14,
    frozenset(['fear', 'confusion']): 15,  # Paranoia
    frozenset(['nervousness', 'confusion']): 15,
    frozenset(['optimism', 'pride']): 18,  # Mobilizing hope
    frozenset(['optimism', 'excitement']): 18,
}

# Global model
EMOTION_MODEL = None

def load_emotion_model():
    """Load German-Emotions model from local path"""
    global EMOTION_MODEL
    
    if EMOTION_MODEL is None:
        logger.info("📦 Loading German-Emotions model...")
        
        model_path = "/app/models/emotion/german-emotions"
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                f"Please download the model first."
            )
        
        logger.info(f"📁 Loading from: {model_path}")
        logger.info("⚠️  Using slow tokenizer to avoid compatibility issues")
        
        # Load with slow tokenizer to avoid tokenizers 0.15.x issues
        EMOTION_MODEL = pipeline(
            "text-classification",
            model=model_path,
            tokenizer=model_path,
            device=0 if DEVICE == "cuda" else -1,
            truncation=True,
            max_length=512,
            return_all_scores=True,
            top_k=None,
            use_fast=False  # Critical fix for tokenizer compatibility
        )
        
        logger.info("✅ German-Emotions model loaded (27 emotions)")
        logger.info("ℹ️  Using slow tokenizer (stable, slightly slower)")
        
        # Log model size
        total_size = 0
        for root, dirs, files in os.walk(model_path):
            for file in files:
                size = os.path.getsize(os.path.join(root, file))
                total_size += size
        
        logger.info(f"📊 Total model size: {total_size / (1024**2):.1f} MB")

# Load at import time
load_emotion_model()

# ---------------------------------------------------------------
# Emotion Classification Service
# ---------------------------------------------------------------
class EmotionService:
    def classify(self, text: str, threshold: float = 0.3, top_k: int = 3):
        """
        Classify emotions in German text
        
        Args:
            text: German text to analyze
            threshold: Minimum confidence for emotion detection
            top_k: Return top K emotions
            
        Returns:
            List of emotion labels with confidence scores
        """
        if not text or not text.strip():
            return [{
                "label_id": 19,
                "label": POLICE_LABELS[19],
                "confidence": 1.0,
                "source_emotions": ["neutral"],
                "method": "empty_text"
            }]
        
        # Truncate for performance
        text = text[:512]
        
        try:
            # Get all emotion scores
            emotion_results = EMOTION_MODEL(text)[0]
            
            # Convert to dict
            emotion_scores = {
                item['label']: item['score'] 
                for item in emotion_results
            }
            
            # Log top emotions
            sorted_emotions = sorted(
                emotion_scores.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            logger.info(f"📊 Top emotions:")
            for emo, score in sorted_emotions:
                logger.info(f"   - {emo}: {score:.3f}")
            
            # Filter significant emotions
            significant = {
                emo: score 
                for emo, score in emotion_scores.items() 
                if score >= threshold
            }
            
            if not significant:
                # Take top emotion if nothing above threshold
                top = max(emotion_scores.items(), key=lambda x: x[1])
                significant = {top[0]: top[1]}
            
            # Map to police labels
            mapped = self._map_to_police_labels(significant)
            
            return mapped[:top_k]
            
        except Exception as e:
            logger.error(f"❌ Classification error: {e}")
            logger.exception("Full traceback:")
            return [{
                "label_id": 19,
                "label": POLICE_LABELS[19],
                "confidence": 0.5,
                "source_emotions": [],
                "method": "error_fallback"
            }]
    
    def _map_to_police_labels(self, emotion_scores):
        """Map GoEmotions to police investigation labels"""
        results = []
        emotion_set = set(emotion_scores.keys())
        
        # Check combinations first
        for combo, label_id in EMOTION_COMBINATIONS.items():
            if combo.issubset(emotion_set):
                combined_conf = sum(emotion_scores[e] for e in combo) / len(combo)
                
                results.append({
                    "label_id": label_id,
                    "label": POLICE_LABELS[label_id],
                    "confidence": combined_conf,
                    "source_emotions": list(combo),
                    "method": "combination"
                })
        
        # Map individual emotions to police labels
        label_scores = {}
        label_sources = {}
        
        for emotion, score in emotion_scores.items():
            if emotion in EMOTION_TO_POLICE:
                label_id = EMOTION_TO_POLICE[emotion]
                
                if label_id not in label_scores:
                    label_scores[label_id] = score
                    label_sources[label_id] = [emotion]
                else:
                    label_scores[label_id] = max(label_scores[label_id], score)
                    label_sources[label_id].append(emotion)
        
        # Add to results
        for label_id, score in label_scores.items():
            if not any(r['label_id'] == label_id for r in results):
                results.append({
                    "label_id": label_id,
                    "label": POLICE_LABELS[label_id],
                    "confidence": score,
                    "source_emotions": label_sources[label_id],
                    "method": "primary"
                })
        
        # Check for ambivalence
        if len(results) >= 3:
            avg_conf = sum(r['confidence'] for r in results) / len(results)
            if avg_conf >= 0.3:
                results.append({
                    "label_id": 20,
                    "label": POLICE_LABELS[20],
                    "confidence": min(avg_conf + 0.1, 0.95),
                    "source_emotions": list(emotion_scores.keys()),
                    "method": "ambivalence"
                })
        
        # Sort by confidence
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        return results

emotion_service = EmotionService()

# ---------------------------------------------------------------
# Worker Job Function (Updated for async Neo4j)
# ---------------------------------------------------------------
def classify_emotion_job(
    message_id: str,
    text: str,
    threshold: float = 0.3,
    top_k: int = 3,
    owner_id: str = None,
    case_id: str = None
):
    """
    Main emotion classification worker function (synchronous wrapper for RQ)
    
    Args:
        message_id: Message ID (format: channel_id-message_id)
        text: German text content
        neo4j_uri: Neo4j connection string
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        threshold: Minimum confidence threshold
        top_k: Number of top emotions to store
        owner_id: Owner ID for multi-tenancy
        case_id: Case ID (optional, for context)
    """
    logger.info("=" * 80)
    logger.info(f"🎭 Emotion classification job started")
    logger.info(f"   Message: {message_id}")
    logger.info(f"   Text length: {len(text)} chars")
    logger.info(f"   Owner: {owner_id or 'None'}")
    logger.info(f"   Threshold: {threshold}")
    logger.info(f"   Top-K: {top_k}")
    logger.info("=" * 80)
    
    try:
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_user = os.getenv("NEO4J_USER")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        # Classify emotions (sync operation)
        emotions = emotion_service.classify(text, threshold=threshold, top_k=top_k)
        
        logger.info(f"📊 Classification results:")
        for emo in emotions:
            src = ", ".join(emo['source_emotions'])
            logger.info(
                f"   [{emo['label_id']}] {emo['label']} "
                f"({emo['confidence']:.2f}) "
                f"← {src} via {emo['method']}"
            )
        
        # Store in Neo4j (async operation wrapped in sync)
        asyncio.run(_store_async(
            neo4j_uri,
            neo4j_user,
            neo4j_password,
            message_id,
            emotions,
            owner_id
        ))
        
        logger.info("✅ Emotion classification completed")
        return emotions
        
    except Exception as e:
        logger.error(f"❌ Emotion classification failed: {e}")
        logger.exception("Full traceback:")
        
        # Mark as failed
        try:
            asyncio.run(_mark_failed_async(
                neo4j_uri,
                neo4j_user,
                neo4j_password,
                message_id,
                str(e),
                owner_id
            ))
        except:
            pass
        
        raise


async def _store_async(
    neo4j_uri, neo4j_user, neo4j_password,
    message_id, emotions, owner_id
):
    """Async helper to store emotions"""
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )
    try:
        await store_emotions_in_neo4j(
            driver, message_id, emotions, owner_id
        )
    finally:
        await driver.close()


async def _mark_failed_async(
    neo4j_uri, neo4j_user, neo4j_password,
    message_id, error, owner_id
):
    """Async helper to mark emotion analysis as failed"""
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )
    try:
        await mark_emotion_analysis_failed(
            driver, message_id, error, owner_id
        )
    finally:
        await driver.close()


# ---------------------------------------------------------------
# Batch Processing (Updated for correct architecture)
# ---------------------------------------------------------------
async def batch_classify_emotions(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    owner_id: str = None,
    case_id: str = None,
    limit: int = 1000,
    threshold: float = 0.3
):
    """
    Batch process messages that don't have emotions yet
    Useful for backfilling after deploying emotion worker
    
    Args:
        neo4j_uri: Neo4j connection
        neo4j_user: Username
        neo4j_password: Password
        owner_id: Owner ID for filtering
        case_id: Optional - only process messages from specific case
        limit: Maximum messages to process
        threshold: Emotion confidence threshold
    """
    logger.info("=" * 80)
    logger.info("🔄 BATCH EMOTION CLASSIFICATION")
    logger.info(f"   Owner: {owner_id or 'ALL'}")
    logger.info(f"   Case: {case_id or 'ALL'}")
    logger.info(f"   Limit: {limit}")
    logger.info("=" * 80)
    
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )
    
    try:
        # Get messages pending emotion analysis
        messages = await get_messages_pending_emotion_analysis(
            driver,
            owner_id=owner_id,
            case_id=case_id,
            limit=limit
        )
        
        logger.info(f"📊 Found {len(messages)} messages to process")
        
        if not messages:
            logger.info("✅ No messages need processing")
            return 0, 0
        
        processed = 0
        errors = 0
        
        for i, msg in enumerate(messages):
            msg_id = msg['message_id']
            text = msg['text']
            msg_owner = msg['owner_id']
            
            try:
                # Classify
                emotions = emotion_service.classify(text, threshold=threshold)
                
                # Store
                await store_emotions_in_neo4j(
                    driver, msg_id, emotions, msg_owner
                )
                
                processed += 1
                
                if (i + 1) % 100 == 0:
                    logger.info(
                        f"📊 Progress: {i + 1}/{len(messages)} "
                        f"({processed} success, {errors} errors)"
                    )
                    
            except Exception as e:
                logger.error(f"❌ Failed {msg_id}: {e}")
                await mark_emotion_analysis_failed(
                    driver, msg_id, str(e), msg_owner
                )
                errors += 1
        
        logger.info("=" * 80)
        logger.info(f"✅ Batch complete: {processed} processed, {errors} errors")
        logger.info("=" * 80)
        
        return processed, errors
        
    finally:
        await driver.close()


# ---------------------------------------------------------------
# Synchronous wrapper for batch processing (for RQ compatibility)
# ---------------------------------------------------------------
def batch_classify_emotions_sync(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    owner_id: str = None,
    case_id: str = None,
    limit: int = 1000,
    threshold: float = 0.3
):
    """Synchronous wrapper for batch processing"""
    return asyncio.run(batch_classify_emotions(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        owner_id=owner_id,
        case_id=case_id,
        limit=limit,
        threshold=threshold
    ))