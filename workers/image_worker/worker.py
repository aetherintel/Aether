# workers/image_worker/worker.py - EasyOCR Multi-Pass Version
"""
Fast Image Analysis Worker with EasyOCR
Extracts text (OCR) from images supporting multiple languages using a multi-pass strategy.
"""
import os
import logging
import easyocr
import torch
import gc
from pathlib import Path
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

# Using CPU or CUDA
DEVICE = True if torch.cuda.is_available() else False
logger.info(f"📱 Device for OCR: {'GPU' if DEVICE else 'CPU'}")

# Model Storage Directory (Volume Mount)
# EasyOCR looks here for .pth files and detector models
MODEL_STORAGE_DIR = "/app/models/image"

# Language Groups (EasyOCR does not support mixing incompatible scripts)
# We initialize multiple readers and run them sequentially if needed.
OCR_READER_GROUPS = {
    "latin": ['en', 'de', 'tr'],  # Latin script: English, German, Turkish
    "cyrillic": ['ru', 'en'],    # Cyrillic: Russian (includes English for mix)
    "arabic": ['ar', 'en']       # Arabic: (includes English for mix)
}

# Global dictionary to hold initialized readers



class EasyOCRService:
    """Service for EasyOCR inference using Single-Active-Reader strategy for memory efficiency"""
    
    def __init__(self):
        # Only hold ONE active reader to save RAM
        self.active_reader = None
        self.active_group = None
            
    def get_reader(self, group_name: str):
        """Lazy load reader, unloading previous one if necessary"""
        import gc
        
        if self.active_reader and self.active_group == group_name:
            return self.active_reader
            
        # Unload previous
        if self.active_reader:
            logger.info(f"   ♻️ Unloading '{self.active_group}' reader to free RAM...")
            del self.active_reader
            self.active_reader = None
            gc.collect()
            if DEVICE:
                torch.cuda.empty_cache()
        
        # Load new
        try:
            langs = OCR_READER_GROUPS.get(group_name)
            if not langs:
                logger.error(f"   ❌ Unknown group: {group_name}")
                return None
                
            logger.info(f"   ⏳ Loading Group '{group_name.upper()}': {langs}...")
            reader = easyocr.Reader(
                lang_list=langs,
                gpu=DEVICE,
                model_storage_directory=MODEL_STORAGE_DIR,
                download_enabled=True,
                verbose=False
            )
            self.active_reader = reader
            self.active_group = group_name
            return reader
            
        except Exception as e:
            logger.error(f"   ❌ Failed to load '{group_name}': {e}")
            return None

    def analyze_image(self, image_path: str, modes: list = None) -> dict:
        """Run OCR analysis using requested modes (default: latin)"""
        import gc
        
        # Default to LATIN only for efficiency (prevents running 3 passes on every image)
        if not modes:
            modes = ['latin']
            
        full_text_results = []
        
        try:
            logger.info(f"   Running OCR on {image_path} (Modes: {modes})...")
            
            seen_texts = set()
            
            for group_name in modes:
                reader = self.get_reader(group_name)
                if not reader:
                    continue
                    
                try:
                    # detail=0 returns simple list of strings
                    # paragraph=True merges lines
                    text_list = reader.readtext(image_path, detail=0, paragraph=True)
                    
                    if text_list:
                        joined_text = "\n".join(text_list).strip()
                        if joined_text and joined_text not in seen_texts:
                            logger.info(f"      [{group_name}] Found: {len(joined_text)} chars")
                            # Add header only if we run multiple modes to distinguish
                            if len(modes) > 1:
                                full_text_results.append(f"--- {group_name.upper()} ---")
                            full_text_results.append(joined_text)
                            seen_texts.add(joined_text)
                except Exception as ex:
                    logger.warning(f"      [{group_name}] Error: {ex}")
            
            extracted_text = "\n\n".join(full_text_results)
            
            results = {}
            if extracted_text.strip():
                results['ocr'] = extracted_text
            else:
                logger.info("   🔤 OCR Found: No text")
                
            return results
            
        except Exception as e:
            logger.error(f"❌ Analysis error: {e}")
            return {}
        finally:
            # Optional: Aggressively cleanup if RAM is critical
            # gc.collect()
            pass

ocr_service = EasyOCRService()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_language(text: str) -> str:
    """Detect language of extracted text"""
    if not text or len(text.strip()) < 10:
        return 'de'
    
    try:
        from langdetect import detect
        # If we have headers like "--- LATIN ---", strip them for detection
        clean_text = text.replace("--- LATIN ---", "").replace("--- CYRILLIC ---", "").replace("--- ARABIC ---", "")
        lang = detect(clean_text)
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


def analyze_and_update(
    message_id: str,
    image_path: str,
    extract_text: bool = True,
    detect_objects: bool = False, 
    translate_extracted_text: bool = True,
    owner_id: str = None,
    case_id: int = None,
    job_id: str = None,
    modes: list = None
):
    """
    Main Image Analysis worker function using EasyOCR Multi-Pass
    """
    import gc
    
    try:
        # Verify image exists
        if not os.path.exists(image_path):
            logger.error(f"❌ Image not found: {image_path}")
            return False
        
        extracted_text = ""
        detected_lang = None
        
        # Step 1: Analyze with EasyOCR
        if extract_text:
            logger.info("🔍 Step 1: Analyzing image with EasyOCR Multi-Pass...")
            analysis_results = ocr_service.analyze_image(image_path, modes=modes)
            
            ocr_text = analysis_results.get('ocr', '')
            
            if ocr_text:
                extracted_text = f"[TEXT IN IMAGE]\n{ocr_text}"
                
                # Detect language 
                detected_lang = detect_language(ocr_text)
                logger.info(f"   Detected language: {detected_lang}")
            else:
                 logger.info("ℹ️ Step 1: No text found")
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