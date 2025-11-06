# ============================================================================
# workers/classification_worker/worker.py (UPDATED for aether_lib architecture)
# ============================================================================

import os
import logging
from redis import Redis
from rq import Queue
import torch
from transformers import pipeline
from neo4j import AsyncGraphDatabase
import asyncio

# Import our Neo4j utilities
from .neo4j_utils import (
    store_classifications_in_neo4j,
    get_messages_pending_classification,
    mark_classification_failed
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
# Classification Labels - 20 Categories
# ---------------------------------------------------------------
CLASSIFICATION_LABELS = {
    1: "Propaganda",
    2: "Aufruf zur Gewalt",
    3: "Hassrede / Hate Speech",
    4: "Drogenhandel",
    5: "Waffenhandel",
    6: "Finanzbetrug / Scam",
    7: "Cybercrime / Hacking",
    8: "Extremismus / Terrorismus",
    9: "Fake News / Desinformation",
    10: "Rekrutierung / Mobilisierung",
    11: "Demonstrationsaufruf",
    12: "Kinderpornografie / Sexualdelikte",
    13: "Menschenhandel / Ausbeutung",
    14: "Geldwäsche / Krypto-Transfers",
    15: "Bedrohung / Erpressung",
    16: "Koordinierte Aktion / Gruppe",
    17: "Anleitung / How-To (illegale Handlung)",
    18: "Codewörter / Verschleierung",
    19: "Finanztransaktion / Spende",
    20: "Allgemeine Kommunikation / Unauffällig"
}

LABEL_DESCRIPTIONS = {
    1: "Politische oder ideologische Beeinflussung, Propaganda, Meinungsmache",
    2: "Direkte oder indirekte Gewaltandrohung, Aufruf zu gewalttätigen Aktionen",
    3: "Abwertung, Diskriminierung oder Hass gegen bestimmte Gruppen oder Personen",
    4: "Angebote, Nachfrage oder Handel mit illegalen Drogen und Substanzen",
    5: "Handel, Verkauf oder Besitz illegaler Waffen",
    6: "Phishing, Fake-Investments, Schneeballsysteme, Betrug",
    7: "Hinweise auf digitale Angriffe, Hacking, Datenhandel, Malware",
    8: "Extremistische Inhalte, Terrorismus, radikale Ideologien",
    9: "Falschinformationen, Desinformation, gezielte Manipulation",
    10: "Versuch Personen für illegale Aktivitäten oder Bewegungen zu rekrutieren",
    11: "Organisation von Demonstrationen, Protesten oder realen Versammlungen",
    12: "Hinweise auf sexuellen Missbrauch oder Verbreitung illegaler sexueller Inhalte",
    13: "Menschenhandel, Zwangsarbeit, Ausbeutung von Personen",
    14: "Verdächtige Geldflüsse, Kryptowährungstransfers, Geldwäsche",
    15: "Individuelle Drohungen, Erpressung, Nötigung",
    16: "Planung koordinierter illegaler Aktionen in Gruppen",
    17: "Anleitungen für illegale Handlungen wie Waffenbau oder Drogensynthese",
    18: "Verwendung von Codewörtern, Slang oder Tarnsprache zur Verschleierung",
    19: "Aufrufe zu Spenden oder Geldtransfers für illegale Zwecke",
    20: "Normale, unauffällige Kommunikation ohne verdächtige Inhalte"
}

# ---------------------------------------------------------------
# Model Configuration
# ---------------------------------------------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"📱 Using device: {DEVICE}")

CLASSIFIER = None

def load_classification_model():
    """Load multilingual zero-shot classification model"""
    global CLASSIFIER
    
    if CLASSIFIER is None:
        logger.info("📦 Loading Zero-Shot Classification model...")
        
        model_name = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
        model_path = f"/app/models/classifier/{model_name.split('/')[-1]}"
        
        if os.path.exists(model_path):
            logger.info(f"📁 Loading from local path: {model_path}")
            load_from = model_path
        else:
            logger.info(f"📥 Downloading from HuggingFace: {model_name}")
            load_from = model_name
        
        CLASSIFIER = pipeline(
            "zero-shot-classification",
            model=load_from,
            device=0 if DEVICE == "cuda" else -1,
            use_fast=True
        )
        
        logger.info(f"✅ Classification model loaded")
        
        if load_from == model_name:
            logger.info(f"💾 Saving model to: {model_path}")
            os.makedirs(model_path, exist_ok=True)
            CLASSIFIER.model.save_pretrained(model_path)
            CLASSIFIER.tokenizer.save_pretrained(model_path)

load_classification_model()

# ---------------------------------------------------------------
# Classification Service
# ---------------------------------------------------------------
class PostClassificationService:
    def classify(
        self, 
        text: str, 
        threshold: float = 0.3, 
        top_k: int = 3,
        use_multi_label: bool = True
    ):
        """Classify post into predefined categories using zero-shot classification"""
        if not text or not text.strip():
            return [{
                "label_id": 20,
                "label": CLASSIFICATION_LABELS[20],
                "description": LABEL_DESCRIPTIONS[20],
                "confidence": 1.0,
                "method": "empty_text"
            }]
        
        text = text[:512]
        
        try:
            candidate_labels = list(LABEL_DESCRIPTIONS.values())
            
            result = CLASSIFIER(
                text,
                candidate_labels,
                multi_label=use_multi_label,
                truncation=True
            )
            
            classifications = []
            
            for label_desc, score in zip(result['labels'], result['scores']):
                label_id = None
                for lid, desc in LABEL_DESCRIPTIONS.items():
                    if desc == label_desc:
                        label_id = lid
                        break
                
                if label_id and score >= threshold:
                    classifications.append({
                        "label_id": label_id,
                        "label": CLASSIFICATION_LABELS[label_id],
                        "description": label_desc,
                        "confidence": float(score),
                        "method": "zero-shot"
                    })
            
            if not classifications and result['scores']:
                top_label_desc = result['labels'][0]
                top_score = result['scores'][0]
                
                for lid, desc in LABEL_DESCRIPTIONS.items():
                    if desc == top_label_desc:
                        classifications.append({
                            "label_id": lid,
                            "label": CLASSIFICATION_LABELS[lid],
                            "description": top_label_desc,
                            "confidence": float(top_score),
                            "method": "top-prediction"
                        })
                        break
            
            classifications = classifications[:top_k]
            
            logger.info(f"📊 Classification results:")
            for cls in classifications:
                logger.info(f"   [{cls['label_id']}] {cls['label']} ({cls['confidence']:.2f})")
            
            return classifications
            
        except Exception as e:
            logger.error(f"❌ Classification error: {e}")
            logger.exception("Full traceback:")
            return [{
                "label_id": 20,
                "label": CLASSIFICATION_LABELS[20],
                "description": LABEL_DESCRIPTIONS[20],
                "confidence": 0.5,
                "method": "error_fallback"
            }]

classification_service = PostClassificationService()

# ---------------------------------------------------------------
# Worker Job Function (Updated for async Neo4j)
# ---------------------------------------------------------------
def classify_post_job(
    message_id: str,
    text: str,
    threshold: float = 0.3,
    top_k: int = 3,
    use_multi_label: bool = True,
    owner_id: str = None,
    case_id: str = None
):
    """
    Main post classification worker function (synchronous wrapper for RQ)
    """
    
    try:
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_user = os.getenv("NEO4J_USER")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        # Classify post (sync operation)
        classifications = classification_service.classify(
            text, 
            threshold=threshold, 
            top_k=top_k,
            use_multi_label=use_multi_label
        )
        
        # Store in Neo4j (async operation wrapped in sync)
        asyncio.run(_store_async(
            neo4j_uri,
            neo4j_user,
            neo4j_password,
            message_id,
            classifications,
            owner_id
        ))
        return classifications
        
    except Exception as e:
        logger.error(f"❌ Post classification failed: {e}")
        
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
    message_id, classifications, owner_id
):
    """Async helper to store classifications"""
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )
    try:
        await store_classifications_in_neo4j(
            driver, message_id, classifications, owner_id
        )
    finally:
        await driver.close()


async def _mark_failed_async(
    neo4j_uri, neo4j_user, neo4j_password,
    message_id, error, owner_id
):
    """Async helper to mark classification as failed"""
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )
    try:
        await mark_classification_failed(
            driver, message_id, error, owner_id
        )
    finally:
        await driver.close()