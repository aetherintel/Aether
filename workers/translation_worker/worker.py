# workers/translation_worker/worker.py
import asyncio
import os
import logging
from aether_lib.queue_client import queue_client
from aether_lib.schemas.jobs import EmotionJobPayload
from redis import Redis
from rq import Queue
import torch


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
# NLLB-200 Model - Load ONCE at startup
# ---------------------------------------------------------------
logger.info("🚀 Loading NLLB-200 translation model at worker startup...")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"📱 Using device: {DEVICE}")

# Language code mapping for NLLB-200 (BCP-47)
# See: https://github.com/facebookresearch/flores/blob/main/flores200/README.md#languages-in-flores-200
LANG_CODES = {
    "en": "eng_Latn",
    "de": "deu_Latn",
    "ru": "rus_Cyrl",
    "ar": "arb_Arab",
    "tr": "tur_Latn",
    "trk": "tur_Latn"  # Alias
}

# Global model and tokenizer
TRANSLATION_MODEL = None
TRANSLATION_TOKENIZER = None

def load_nllb_model():
    """Load NLLB-200 from local path"""
    global TRANSLATION_MODEL, TRANSLATION_TOKENIZER
    
    if TRANSLATION_MODEL is None:
        logger.info("📦 Loading NLLB-200-Distilled-600M model...")
        
        model_path = "/app/models/nllb-200-distilled-600M"
        
        # Check if files exist
        import os
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                f"Please download the model first using the download script."
            )
        
        logger.info(f"📁 Loading from: {model_path}")
        
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        
        # Load from local files
        # NLLB fast tokenizer can have issues with some versions of transformers/tokenizers
        # Force slow tokenizer (SentencePiece) to avoid "data did not match any variant" error
        TRANSLATION_TOKENIZER = AutoTokenizer.from_pretrained(
            model_path,
            local_files_only=True,
            use_fast=False,
            trust_remote_code=True
        )
        
        # Determine dtype for speed (fp16 on GPU)
        torch_dtype = torch.float16 if DEVICE == "cuda" else torch.float32
        
        TRANSLATION_MODEL = AutoModelForSeq2SeqLM.from_pretrained(
            model_path,
            local_files_only=True,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            trust_remote_code=True
        )
        
        # Dynamic quantization removed to prevent OOM (Signal 9) crashes
        # The 600M model should run fine on CPU without it
        
        TRANSLATION_MODEL = TRANSLATION_MODEL.to(DEVICE)
        
        logger.info(f"✅ NLLB-200 model loaded! (dtype={torch_dtype})")
        
        # Log file sizes for verification
        import os
        total_size = 0
        for root, dirs, files in os.walk(model_path):
            for file in files:
                size = os.path.getsize(os.path.join(root, file))
                total_size += size
        
        logger.info(f"📊 Total model size: {total_size / (1024**2):.1f} MB")
# Load at import time
load_nllb_model()


# ---------------------------------------------------------------
# Translation Service
# ---------------------------------------------------------------
class TranslationService:
    def translate(self, text: str, source_lang: str, target_lang: str = "de") -> str:
        """
        Translate text using NLLB-200 model
        
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
        
        # Get NLLB language codes
        src_code = LANG_CODES.get(source_lang)
        tgt_code = LANG_CODES.get(target_lang, "deu_Latn")
        
        if not src_code:
            logger.warning(f"⚠️ Unsupported language: {source_lang}, returning original")
            return text
        
        logger.info(f"🔤 Translating {source_lang} ({src_code}) → {target_lang} ({tgt_code})")
        
        # Truncate for performance
        if len(text) > 1000:
            logger.warning(f"⚠️ Truncating text from {len(text)} to 1000 chars")
            text = text[:1000]
        
        try:
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
                    forced_bos_token_id=TRANSLATION_TOKENIZER.convert_tokens_to_ids(tgt_code),
                    max_length=200,
                    num_beams=1,  # Greedy - fastest
                    early_stopping=False  # Must be False for num_beams=1
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
    case_id: int = None,
    parent_job_id: str = None,
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
                emotion_job_id = queue_client.enqueue_emotion(EmotionJobPayload(message_id=message_id, text=translated_text, owner_id=owner_id, case_id=case_id))
                if emotion_job_id:
                    logger.info(f"✅ Step 3: Emotion analysis queued: {emotion_job_id}")
                else:
                    logger.warning("⚠️ Step 3: Emotion analysis not queued")
            except Exception as e:
                logger.error(f"❌ Step 3: Failed to trigger emotion analysis: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"   Error: {e}")
        raise