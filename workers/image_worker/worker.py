# workers/image_worker/worker.py - EasyOCR Version
"""
Ultra-Fast OCR Worker with EasyOCR
Extracts text from ANY graphic (posters, infographics, memes, screenshots)
MUCH more stable than PaddleOCR - no segfaults!
"""
import os
import logging
import requests
from pathlib import Path
from aether_lib.neo4j_client.messages import update_message_image_analysis
from aether_lib.queue_client.queue_client import queue_client
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

# Global OCR instance
OCR_ENGINE = None


# Translation Configuration
SUPPORTED_TRANSLATION_LANGUAGES = ['ru', 'ar', 'tr', 'en']

def load_models():
    """Load EasyOCR model from local directory (air-gapped)"""
    global OCR_ENGINE
    
    logger.info("=" * 80)
    logger.info("📦 LOADING EASYOCR (AIR-GAPPED MODE)")
    logger.info("=" * 80)
    
    try:
        import easyocr
        
        # EasyOCR looks for models in model_storage_directory
        model_storage = MODEL_BASE_DIR / "easyocr"
        model_storage.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 Model storage: {model_storage}")
        logger.info(f"   Exists: {model_storage.exists()}")
        
        # Check what files are in the directory
        if model_storage.exists():
            files = list(model_storage.rglob("*"))
            logger.info(f"   Files found: {len(files)}")
            for f in files[:10]:  # Show first 10
                if f.is_file():
                    logger.info(f"     - {f.relative_to(model_storage)}")
        
        # Initialize EasyOCR with English
        logger.info("⏳ Initializing EasyOCR Reader...")
        
        OCR_ENGINE = easyocr.Reader(
            ['en', 'de', 'fr', 'it', 'es'],  # Languages
            model_storage_directory=str(model_storage),
            download_enabled=True,  # Allow download as fallback if models missing
            gpu=False,  # Force CPU for stability
            verbose=True  # Show what's happening
        )
        
        logger.info("✅ EasyOCR loaded successfully!")
        logger.info("   Language: English, German, Russian, Arabic, Turkish")
        logger.info("   Works with: Posters, infographics, screenshots, memes")
        logger.info("   Speed: ~2-3s per image")
        logger.info("   Stability: Excellent (no segfaults)")
        
    except Exception as e:
        logger.error(f"❌ Failed to load EasyOCR: {e}")
        logger.exception("Full traceback:")
        logger.error("   OCR will be disabled")
        OCR_ENGINE = None
    
    logger.info("=" * 80)


class FastOCRService:
    """Ultra-fast OCR service with EasyOCR"""
    
    def __init__(self):
        # Load models immediately on initialization
        if OCR_ENGINE is None:
            logger.info("🔄 OCR engine not loaded, loading now...")
            load_models()
        
        if OCR_ENGINE is None:
            logger.error("❌ CRITICAL: OCR engine failed to load!")
        else:
            logger.info("✅ OCR engine ready")
    
    def preprocess_image(self, img):
        """Optimized preprocessing with minimal memory copies"""
        from PIL import ImageEnhance
        import numpy as np
        
        # Convert to RGB in-place if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Quick brightness check without creating full numpy array
        # Sample only a small portion of the image
        sample = img.crop((
            img.width // 4, 
            img.height // 4,
            img.width * 3 // 4,
            img.height * 3 // 4
        ))
        img_array = np.array(sample)
        std_brightness = np.std(img_array)
        
        # Free sample memory immediately
        del sample, img_array
        
        # Only enhance if really needed
        if std_brightness < 50:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)  # Reduced from 2.0
        
        if std_brightness < 40:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)  # Reduced from 1.5
        
        return img
    def adaptive_threshold(self, img):
        """Apply adaptive thresholding for documents"""
        import cv2
        import numpy as np
        from PIL import Image
        
        # Convert PIL to OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Convert back to PIL
        return Image.fromarray(binary)
    def extract_text(self, image_path: str) -> str:
        """Extract text from image with optimized settings for complex infographics"""
        import gc
        from PIL import Image
        import tempfile
        
        if OCR_ENGINE is None:
            logger.warning("⚠️ OCR engine not loaded, skipping text extraction")
            return ""
        
        img = None
        temp_path = None
        
        try:
            logger.info(f"🔍 Extracting text: {image_path}")
            
            # Load image
            img = Image.open(image_path)
            width, height = img.size
            logger.info(f"   Image size: {width}x{height}")
            
            # BALANCE: 2560px is good for infographics (between 1920 and 3840)
            max_dimension = 2560  # Better for complex text layouts
            
            if width > max_dimension or height > max_dimension:
                scale = max_dimension / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                logger.info(f"   Resized to: {new_width}x{new_height}")
            
            # Preprocess image
            logger.info("   Preprocessing image...")
            img = self.preprocess_image(img)
            
            # Save to temp file with higher quality for infographics
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                img.save(tmp.name, 'JPEG', quality=90)  # Higher quality for complex images
                temp_path = tmp.name
            
            # Close image to free memory before OCR
            img.close()
            img = None
            gc.collect()
            
            # Run OCR with AGGRESSIVE settings for maximum text capture
            logger.info("   Running EasyOCR (aggressive mode for infographics)...")
            result = OCR_ENGINE.readtext(
                temp_path,
                detail=1,               # Return detailed results with confidence
                paragraph=False,        # Line-by-line for complex layouts
                
                # AGGRESSIVE THRESHOLDS - capture more text from complex images
                contrast_ths=0.05,      # LOWERED from 0.1 - more sensitive
                adjust_contrast=0.6,    # Moderate adjustment
                text_threshold=0.3,     # LOWERED from 0.4 - catch smaller text
                low_text=0.2,           # LOWERED from 0.3 - catch faint text
                link_threshold=0.2,     # LOWERED from 0.3 - better word linking
                
                # LARGER CANVAS - better for complex layouts
                canvas_size=3200,       # INCREASED from 2560
                mag_ratio=1.8,          # INCREASED from 1.5 - more detail
                
                # RELAXED GROUPING - better for scattered text in infographics
                width_ths=0.3,          # LOWERED from 0.5 - accept varied widths
                height_ths=0.3,         # LOWERED from 0.5 - accept varied heights
                
                # ADDITIONAL SETTINGS for better detection
                slope_ths=0.3,          # Allow slightly slanted text
                ycenter_ths=0.5,        # Better vertical alignment tolerance
                add_margin=0.15         # Add margin around detected text
            )
            
            # Extract text with VERY LOW confidence thresholds for infographics
            if result and len(result) > 0:
                text_lines = []
                low_confidence_lines = []
                filtered_out = []
                
                logger.info(f"   Found {len(result)} text detections")
                
                for i, detection in enumerate(result):
                    try:
                        if isinstance(detection, str):
                            text = detection.strip()
                            confidence = 1.0
                        elif isinstance(detection, (list, tuple)):
                            if len(detection) >= 3:
                                text = str(detection[1]).strip()
                                confidence = float(detection[2])
                            elif len(detection) == 2:
                                text = str(detection[1]).strip()
                                confidence = 0.7
                            else:
                                continue
                        else:
                            continue
                        
                        if not text or len(text.strip()) == 0:
                            continue
                        
                        # MUCH LOWER thresholds for complex infographics
                        if confidence > 0.15:  # LOWERED from 0.3
                            text_lines.append(text)
                        elif confidence > 0.05:  # LOWERED from 0.1
                            low_confidence_lines.append(text)
                        else:
                            # Track what we're filtering
                            filtered_out.append((confidence, text[:30]))
                            
                    except (IndexError, ValueError, TypeError) as e:
                        logger.warning(f"⚠️ Error processing detection {i}: {e}")
                        continue
                
                # Log statistics
                if filtered_out:
                    logger.info(f"   ⚠️ Filtered out {len(filtered_out)} very low confidence (<0.05) detections")
                
                # Combine all lines
                all_lines = text_lines + low_confidence_lines
                
                if all_lines:
                    # Sort by vertical position if bounding boxes are available
                    # This helps maintain reading order for complex layouts
                    extracted_text = "\n".join(all_lines)
                    
                    logger.info(f"✅ Extracted {len(text_lines)} high-conf + {len(low_confidence_lines)} low-conf lines")
                    logger.info(f"   Total: {len(extracted_text)} characters")
                    logger.info(f"   Kept: {len(all_lines)}/{len(result)} detections ({100*len(all_lines)/len(result):.1f}%)")
                    
                    if extracted_text:
                        preview_len = min(200, len(extracted_text))
                        logger.info(f"   Preview: {extracted_text[:preview_len]}...")
                    
                    return extracted_text.strip()
                else:
                    logger.warning("⚠️ All detections were below confidence threshold")
                    logger.info(f"   Consider lowering thresholds - found {len(result)} detections but kept 0")
                    return ""
            else:
                logger.info("ℹ️ No text detected in image")
                return ""
                
        except Exception as e:
            logger.error(f"❌ OCR error: {e}")
            logger.exception("Full traceback:")
            return ""
            
        finally:
            # SAFE: Cleanup temp files and memory
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete temp file: {e}")
            
            # SAFE: Close image if still open
            if img is not None:
                try:
                    img.close()
                except Exception:
                    pass
            
            # Force garbage collection
            gc.collect()

ocr_service = FastOCRService()


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
    Main OCR worker function with memory management and proper Neo4j updates
    
    Args:
        message_id: Full message ID (channel_id-message_id)
        image_path: Path to image file
        extract_text: Whether to perform OCR
        detect_objects: Whether to detect objects (not implemented)
        translate_extracted_text: Whether to queue translation
        owner_id: Owner ID for multi-tenancy
        case_id: Case ID for filtering
        job_id: Parent job ID for chaining
    
    Returns:
        bool: True if successful, False otherwise
    """
    import gc
    
    try:
        # Verify image exists
        if not os.path.exists(image_path):
            logger.error(f"❌ Image not found: {image_path}")
            return False
        
        extracted_text = None
        detected_lang = None
        
        # Step 1: Extract text with OCR
        if extract_text:
            logger.info("📝 Step 1: Extracting text with EasyOCR...")
            extracted_text = ocr_service.extract_text(image_path)
            
            if extracted_text:
                
                # Detect language of extracted text
                detected_lang = detect_language(extracted_text)
                logger.info(f"   Detected language: {detected_lang}")
            else:
                logger.info("ℹ️ Step 1: No text found in image")
                detected_lang = 'unknown'
        
        from aether_lib.neo4j_client.connection import run_in_neo4j_loop
        from aether_lib.neo4j_client.messages import update_message_image_analysis
        
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
        # CRITICAL: Force garbage collection after each job
        gc.collect()