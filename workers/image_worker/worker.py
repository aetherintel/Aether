# workers/image_worker/worker.py - Florence-2 Version
"""
Advanced Image Analysis Worker with Microsoft Florence-2-large
Extracts text (OCR) AND detailed captions from images.
"""
import os
import logging
import requests
import torch
from PIL import Image
from pathlib import Path
from transformers import AutoProcessor, AutoModelForCausalLM, AutoConfig
from aether_lib.neo4j_client.messages import update_message_image_analysis
from aether_lib.queue_client.queue_client import queue_client
from aether_lib.neo4j_client.connection import run_in_neo4j_loop

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Local model paths (mounted from host)
MODEL_BASE_DIR = Path(os.getenv("MODEL_BASE_DIR", "/app/models/image"))
FLORENCE_MODEL_PATH = MODEL_BASE_DIR / "florence-2-large"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Global Model instance
FLORENCE_MODEL = None
FLORENCE_PROCESSOR = None

# Translation Configuration
SUPPORTED_TRANSLATION_LANGUAGES = ['ru', 'ar', 'tr', 'en']

def load_models():
    """Load Florence-2 model from local directory"""
    global FLORENCE_MODEL, FLORENCE_PROCESSOR
    
    logger.info("=" * 80)
    logger.info("📦 LOADING FLORENCE-2-LARGE")
    logger.info("=" * 80)
    
    try:
        if not FLORENCE_MODEL_PATH.exists():
            raise FileNotFoundError(f"Model not found at {FLORENCE_MODEL_PATH}")
            
        logger.info(f"📁 Loading from: {FLORENCE_MODEL_PATH}")
        logger.info(f"📱 Device: {DEVICE}")
        
        # Load Processor
        FLORENCE_PROCESSOR = AutoProcessor.from_pretrained(
            FLORENCE_MODEL_PATH, 
            local_files_only=True
        )
        
        # Use float16 for GPU, float32 for CPU
        dtype = torch.float16 if DEVICE == "cuda" else torch.float32
        
        FLORENCE_MODEL = AutoModelForCausalLM.from_pretrained(
            FLORENCE_MODEL_PATH,
            local_files_only=True,
            torch_dtype=dtype
        ).to(DEVICE)
        
        logger.info("✅ Florence-2 loaded successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to load Florence-2: {e}")
        logger.exception("Full traceback:")
        FLORENCE_MODEL = None
        FLORENCE_PROCESSOR = None
    
    logger.info("=" * 80)


class FlorenceService:
    """Service for Florence-2 VLM inference"""
    
    def __init__(self):
        if FLORENCE_MODEL is None:
            logger.info("🔄 Florence model not loaded, loading now...")
            load_models()
            
    def run_inference(self, image: Image.Image, task_prompt: str, text_input: str = None) -> str:
        """Run a specific task on the image"""
        if FLORENCE_MODEL is None:
            return ""
            
        try:
            if text_input is None:
                prompt = task_prompt
            else:
                prompt = task_prompt + text_input
                
            inputs = FLORENCE_PROCESSOR(text=prompt, images=image, return_tensors="pt", padding=True).to(DEVICE, FLORENCE_MODEL.dtype)
            
            generated_ids = FLORENCE_MODEL.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=3,
            )
            
            generated_text = FLORENCE_PROCESSOR.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = FLORENCE_PROCESSOR.post_process_generation(
                generated_text, 
                task=task_prompt, 
                image_size=(image.width, image.height)
            )
            
            return parsed_answer
            
        except Exception as e:
            logger.error(f"❌ Inference error ({task_prompt}): {e}")
            return ""

    def analyze_image(self, image_path: str) -> dict:
        """Run comprehensive analysis (OCR + Caption)"""
        import gc
        
        if FLORENCE_MODEL is None:
            return {}
            
        try:
            image = Image.open(image_path)
            if image.mode != "RGB":
                image = image.convert("RGB")
                
            results = {}
            
            # 1. Detailed Caption
            logger.info("   Generating DETAILED_CAPTION...")
            caption_result = self.run_inference(image, "<MORE_DETAILED_CAPTION>")
            if caption_result and caption_result.get("<MORE_DETAILED_CAPTION>"):
                results['caption'] = caption_result["<MORE_DETAILED_CAPTION>"]
                logger.info(f"   📝 Caption: {results['caption'][:100]}...")
                
            # 2. OCR
            logger.info("   Running OCR...")
            ocr_result = self.run_inference(image, "<OCR>")
            if ocr_result and ocr_result.get("<OCR>"):
                ocr_text = ocr_result["<OCR>"]
                # Florence OCR output might be string or structured
                if isinstance(ocr_text, str):
                    results['ocr'] = ocr_text
                else:
                    results['ocr'] = str(ocr_text)
                logger.info(f"   🔤 OCR: {len(results['ocr'])} chars")
                
            image.close()
            return results
            
        except Exception as e:
            logger.error(f"❌ Analysis error: {e}")
            return {}
        finally:
            gc.collect()
            if DEVICE == "cuda":
                torch.cuda.empty_cache()

florence_service = FlorenceService()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_language(text: str) -> str:
    """Detect language of extracted text"""
    if not text or len(text.strip()) < 10:
        return 'de'
    
    try:
        from langdetect import detect
        lang = detect(text)
        return lang
    except Exception:
        logger.warning(f"[LANG] Could not detect language, assuming German")
        return 'de'


def needs_translation(text: str) -> tuple[bool, str]:
    """Check if extracted text needs translation"""
    detected_lang = detect_language(text)
    
    if detected_lang == 'de':
        return False, 'de'
    
    if detected_lang in SUPPORTED_TRANSLATION_LANGUAGES:
        logger.info(f"[LANG] Text needs translation: {detected_lang} -> de")
        return True, detected_lang
    
    logger.info(f"[LANG] Unsupported language {detected_lang}, storing original")
    return False, detected_lang

# ============================================================================
# WORKER JOB FUNCTION
# ============================================================================
def analyze_and_update(
    message_id: str,
    image_path: str,
    extract_text: bool = True,
    detect_objects: bool = False,
    translate_extracted_text: bool = True,
    owner_id: str = None,
    case_id: int = None,
    job_id: str = None
):
    """
    Main Image Analysis worker function
    """
    import gc
    
    try:
        # Verify image exists
        if not os.path.exists(image_path):
            logger.error(f"❌ Image not found: {image_path}")
            return False
        
        extracted_text = ""
        detected_lang = None
        
        # Step 1: Analyze with Florence-2
        if extract_text:
            logger.info("🔍 Step 1: Analyzing image with Florence-2...")
            analysis_results = florence_service.analyze_image(image_path)
            
            caption = analysis_results.get('caption', '')
            ocr = analysis_results.get('ocr', '')
            
            parts = []
            if caption:
                parts.append(f"[IMAGE DESCRIPTION]\n{caption}")
            if ocr:
                parts.append(f"[TEXT IN IMAGE]\n{ocr}")
                
            extracted_text = "\n\n".join(parts)
            
            if extracted_text:
                 # Detect language (prioritize OCR text for language detection)
                lang_source = ocr if len(ocr) > 20 else (caption if caption else "")
                detected_lang = detect_language(lang_source)
                logger.info(f"   Detected language: {detected_lang}")
            else:
                 logger.info("ℹ️ Step 1: No text/caption generated")
                 detected_lang = 'unknown'

        
        result = run_in_neo4j_loop(
            update_message_image_analysis,
            message_id=message_id,
            image_text=extracted_text,
            detected_language=detected_lang
        )
        
        if result:
            logger.info("✅ Step 2: Neo4j updated successfully")
        else:
            logger.warning("⚠️ Step 2: Neo4j update returned False")
        
        # Step 3: Queue translation if needed
        # Only translate if we have substantial text and it's not German
        if extracted_text and translate_extracted_text:
            needs_trans, _ = needs_translation(extracted_text)
            
            if needs_trans:
                logger.info(f"🌍 Step 3: Queueing translation ({detected_lang} → de)...")
                
                translation_job_id = queue_client.enqueue_translation(
                    message_id=message_id,
                    text=extracted_text,
                    source_language=detected_lang,
                    case_id=case_id,
                    owner_id=owner_id,
                    parent_job_id=job_id,
                    image_text=True
                )
                
                if translation_job_id:
                    logger.info(f"✅ Step 3: Translation queued (job: {translation_job_id})")
                else:
                    logger.warning("⚠️ Step 3: Translation queue failed")
            else:
                logger.info(f"ℹ️ Step 3: No translation needed (language: {detected_lang})")
        
        return True
        
    except Exception as e:
        logger.error(f"   Error: {e}")
        return False
        
    finally:
        gc.collect()