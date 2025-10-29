# workers/translation_worker/worker.py
import asyncio
import os
import logging
from redis import Redis
from rq import Queue
import torch
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

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
# Redis Queue setup
# ---------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT)
translation_queue = Queue('translation-jobs', connection=redis_conn)

# ---------------------------------------------------------------
# M2M-100 Model - Load ONCE at startup
# ---------------------------------------------------------------
logger.info("🚀 Loading M2M-100 translation model at worker startup...")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"📱 Using device: {DEVICE}")

# Language code mapping for M2M-100
LANG_CODES = {
    "en": "en",
    "de": "de",
    "ru": "ru",
    "ar": "ar",
    "tr": "tr",
    "trk": "tr"  # Alias
}

# Global model and tokenizer
TRANSLATION_MODEL = None
TRANSLATION_TOKENIZER = None

def load_m2m_model():
    """Load M2M-100 from local path"""
    global TRANSLATION_MODEL, TRANSLATION_TOKENIZER
    
    if TRANSLATION_MODEL is None:
        logger.info("📦 Loading M2M-100-418M model...")
        
        model_path = "/app/models/translation/m2m100_418M"
        
        # Check if files exist
        import os
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                f"Please download the model first using the download script."
            )
        
        logger.info(f"📁 Loading from: {model_path}")
        
        # Load from local files
        TRANSLATION_TOKENIZER = M2M100Tokenizer.from_pretrained(
            model_path,
            local_files_only=True  # Don't try to download
        )
        
        TRANSLATION_MODEL = M2M100ForConditionalGeneration.from_pretrained(
            model_path,
            local_files_only=True,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True
        )
        
        TRANSLATION_MODEL = TRANSLATION_MODEL.to(DEVICE)
        
        logger.info("✅ M2M-100 model loaded!")
        
        # Log file sizes for verification
        import os
        total_size = 0
        for root, dirs, files in os.walk(model_path):
            for file in files:
                size = os.path.getsize(os.path.join(root, file))
                total_size += size
        
        logger.info(f"📊 Total model size: {total_size / (1024**2):.1f} MB")
# Load at import time
load_m2m_model()


# ---------------------------------------------------------------
# Translation Service
# ---------------------------------------------------------------
class TranslationService:
    def translate(self, text: str, source_lang: str, target_lang: str = "de") -> str:
        """
        Translate text using M2M-100 model
        
        Args:
            text: Text to translate
            source_lang: Source language code (en, ru, ar, tr)
            target_lang: Target language code (default: de)
        
        Returns:
            Translated text
        """
        if not text.strip():
            return text
        
        if source_lang == target_lang:
            logger.info(f"🔄 Text already in {target_lang}, skipping")
            return text
        
        # Get M2M language codes
        src_code = LANG_CODES.get(source_lang)
        tgt_code = LANG_CODES.get(target_lang, "de")
        
        if not src_code:
            logger.warning(f"⚠️ Unsupported language: {source_lang}, returning original")
            return text
        
        logger.info(f"🔤 Translating {source_lang} → {target_lang}")
        
        # Truncate for performance
        if len(text) > 1000:
            logger.warning(f"⚠️ Truncating text from {len(text)} to 1000 chars")
            text = text[:1000]
        
        try:
            # Set source language
            TRANSLATION_TOKENIZER.src_lang = src_code
            
            # Tokenize
            inputs = TRANSLATION_TOKENIZER(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=200
            ).to(DEVICE)
            
            # Generate translation
            with torch.no_grad():
                generated_tokens = TRANSLATION_MODEL.generate(
                    **inputs,
                    forced_bos_token_id=TRANSLATION_TOKENIZER.get_lang_id(tgt_code),
                    max_length=200,
                    num_beams=1,  # Greedy - fastest
                    early_stopping=True
                )
            
            # Decode
            translated = TRANSLATION_TOKENIZER.decode(generated_tokens[0], skip_special_tokens=True)
            
            logger.info(f"✅ Translation: {translated[:50]}...")
            return translated
            
        except Exception as e:
            logger.error(f"❌ Translation error: {e}")
            logger.exception("Full traceback:")
            return text  # Return original on error


translation_service = TranslationService()


# ---------------------------------------------------------------
# Worker job function
# ---------------------------------------------------------------
def translate_and_update(
    message_id: str,
    original_text: str,
    source_language: str,
    owner_id: str = None,
    image_text: bool = False,
    audio_text: bool = False,
    target_language: str = "de"
):
    """
    Main translation worker function
    
    Args:
        message_id: Message ID to update
        original_text: Text to translate
        source_language: Source language code
        owner_id: Owner ID for logging
        image_text: If True, update image_text_translated instead of translated_text
    """
    logger.info("=" * 80)
    logger.info(f"🔄 Translation job started")
    logger.info(f"   Message: {message_id}")
    logger.info(f"   Language: {source_language} → de")
    logger.info(f"   Length: {len(original_text)} chars")
    logger.info(f"   Target field: {'image_text_translated' if image_text else 'translated_text'}")
    logger.info("=" * 80)
    
    try:
        # Step 1: Translate
        logger.info("📝 Step 1: Translating...")
        translated_text = translation_service.translate(original_text, source_language, target_language)
        logger.info(f"✅ Step 1: {translated_text[:60]}...")
        
        # Step 2: Update Neo4j with appropriate field
        logger.info("💾 Step 2: Updating Neo4j...")
        
        from aether_lib.neo4j_client.connection import run_in_neo4j_loop
        from aether_lib.neo4j_client.messages import update_message_translation
        
        # Pass image_text flag to Neo4j update function
        result = run_in_neo4j_loop(
            update_message_translation,
            message_id=message_id,
            translated_text=translated_text,
            image_text=image_text,  # NEW: Pass the flag
            audio_text=audio_text  # NEW: Pass the flag
        )
        
        if result:
            field_name = 'image_text_translated' if image_text else 'translated_text'
            logger.info(f"✅ Step 2: Neo4j updated ({field_name})")
        else:
            logger.warning("⚠️ Step 2: Update returned False")

        if translated_text and len(translated_text.strip()) > 10:
            # Step 3: Trigger emotion analysis
            logger.info("🎭 Step 3: Triggering emotion analysis...")
            try:
                emotion_job_id = trigger_emotion_analysis(
                message_id=message_id,
                text=translated_text,
                owner_id=owner_id
            )
                if emotion_job_id:
                    logger.info(f"✅ Step 3: Emotion analysis queued: {emotion_job_id}")
                else:
                    logger.warning("⚠️ Step 3: Emotion analysis not queued")
            except Exception as e:
                logger.error(f"❌ Step 3: Failed to trigger emotion analysis: {e}")
            
            # Step 4: Trigger classification (runs independently)
            logger.info("🏷️ Step 4: Triggering classification...")
            try:
                classification_job_id = trigger_classification(
                message_id=message_id,
                text=translated_text,
                owner_id=owner_id
            )
                if classification_job_id:
                    logger.info(f"✅ Step 4: Classification queued: {classification_job_id}")
                else:
                    logger.warning("⚠️ Step 4: Classification not queued")
            except Exception as e:
                logger.error(f"❌ Step 4: Failed to trigger classification: {e}")
        logger.info("=" * 80)
        logger.info(f"✅ Job completed: {message_id}")
        logger.info("=" * 80)
        
        return result
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Job FAILED: {message_id}")
        logger.error(f"   Error: {e}")
        logger.exception("Full traceback:")
        logger.error("=" * 80)
        raise

def enqueue_translation(message_id: str, original_text: str, source_language: str, owner_id: str = None):
    """Enqueue translation job"""
    job = translation_queue.enqueue(
        'workers.translation_worker.translate_and_update',
        message_id=message_id,
        original_text=original_text,
        source_language=source_language,
        owner_id=owner_id,
        job_timeout="10m",
        result_ttl=3600,
        failure_ttl=86400
    )
    logger.info(f"📤 Enqueued job {job.id} for {message_id}")
    return job

def trigger_emotion_analysis(message_id: str, text: str, owner_id: str = None) -> str:
    """
    Trigger emotion analysis job via job-launcher
    
    Args:
        message_id: Message ID
        text: German text (already translated)
        owner_id: Owner ID for tracking
        
    Returns:
        Job ID or None
    """
    import requests
    
    JOB_LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL", "http://job-launcher:9001")
    JOB_SECRET_TOKEN = os.getenv("JOB_SECRET_TOKEN")
    
    try:
        response = requests.post(
            f"{JOB_LAUNCHER_URL}/queue/emotion",
            json={
                "message_id": message_id,
                "text": text,
                "owner_id": owner_id,
                "chained_from": "translation",
                "threshold": 0.3,
                "top_k": 3
            },
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            timeout=10
        )
        response.raise_for_status()
        
        job_data = response.json()
        return job_data.get('job_id')
        
    except Exception as e:
        logger.error(f"❌ Failed to trigger emotion analysis: {e}")
        return None

def trigger_classification(message_id: str, text: str, owner_id: str = None) -> str:
    """
    Trigger classification job via job-launcher
    
    Args:
        message_id: Message ID
        text: German text (already translated)
        owner_id: Owner ID for tracking
        
    Returns:
        Job ID or None
    """
    import requests
    
    JOB_LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL", "http://job-launcher:9001")
    JOB_SECRET_TOKEN = os.getenv("JOB_SECRET_TOKEN")
    
    try:
        response = requests.post(
            f"{JOB_LAUNCHER_URL}/queue/classification",
            json={
                "message_id": message_id,
                "text": text,
                "owner_id": owner_id,
                "chained_from": "translation"
            },
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            timeout=10
        )
        response.raise_for_status()
        
        job_data = response.json()
        return job_data.get('job_id')
        
    except Exception as e:
        logger.error(f"❌ Failed to trigger classification: {e}")
        return None