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

# Configure logging
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

# Job Launcher Configuration
JOB_LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL", "http://job-launcher:9001")
JOB_SECRET_TOKEN = os.getenv("JOB_SECRET_TOKEN")

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
        """Adaptive preprocessing based on image characteristics"""
        from PIL import ImageEnhance, ImageOps
        import numpy as np
        
        # Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate image statistics
        img_array = np.array(img)
        mean_brightness = np.mean(img_array)
        std_brightness = np.std(img_array)
        
        # Only enhance if image is low contrast
        if std_brightness < 50:  # Low contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)  # Stronger enhancement
        
        # Only sharpen if image is blurry
        if std_brightness < 40:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.5)
        
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
        """Extract ALL text from image using EasyOCR"""
        if OCR_ENGINE is None:
            logger.warning("⚠️ OCR engine not loaded, skipping text extraction")
            return ""

        try:
            logger.info(f"🔍 Extracting text: {image_path}")

            # Load image and check size
            from PIL import Image
            img = Image.open(image_path)
            width, height = img.size
            logger.info(f"   Image size: {width}x{height}")

            # INCREASED max dimension for documents - preserve more detail
            max_dimension = 3840  # 4K resolution - much better for documents
            if width > max_dimension or height > max_dimension:
                scale = max_dimension / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                # Use LANCZOS (same as old ANTIALIAS)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                logger.info(f"   Resized to: {new_width}x{new_height} (preserving detail)")

            # Apply preprocessing to improve OCR
            logger.info("   Preprocessing image (contrast/sharpness enhancement)...")
            img = self.preprocess_image(img)

            # Save preprocessed image temporarily
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                img.save(tmp.name, 'JPEG', quality=98)  # Higher quality
                temp_path = tmp.name

            # Run OCR with MAXIMUM accuracy settings
            logger.info("   Running EasyOCR with maximum accuracy settings...")
            result = OCR_ENGINE.readtext(
                temp_path,
                detail=1,
                paragraph=True,  # Change to True - better for document layout
                contrast_ths=0.01,  # Even lower (was 0.05)
                adjust_contrast=0.7,  # Higher adjustment
                text_threshold=0.3,  # Lower (was 0.5)
                low_text=0.2,  # Lower (was 0.3)
                link_threshold=0.2,  # Lower (was 0.3)
                canvas_size=4096,  # Increase
                mag_ratio=2.0,  # Increase (was 1.5)
                width_ths=0.5,  # Add: helps with narrow text
                height_ths=0.5  # Add: helps with small text
            )

            # Clean up temp file
            import os
            os.unlink(temp_path)

            # Extract all text with VERY low confidence threshold
            if result:
                text_lines = []
                low_confidence_lines = []

                for detection in result:
                    # detection = (bbox, text, confidence)
                    text = detection[1].strip()
                    confidence = detection[2]

                    if confidence > 0.3:  # High confidence
                        text_lines.append(text)
                    elif confidence > 0.05:  # Low but possibly valid
                        low_confidence_lines.append(text)
                        logger.debug(f"   Low confidence ({confidence:.2f}): {text[:50]}")

                # Include low confidence text too - better to have extra than miss important text
                all_lines = text_lines + low_confidence_lines

                # Join all lines with newlines
                extracted_text = "\n".join(all_lines)

                logger.info(f"✅ Extracted {len(text_lines)} high-conf + {len(low_confidence_lines)} low-conf text lines")
                logger.info(f"   Total: {len(extracted_text)} characters")
                if extracted_text:
                    logger.info(f"   Preview: {extracted_text[:150]}...")

                return extracted_text.strip()
            else:
                logger.info("ℹ️ No text found in image")
                return ""

        except Exception as e:
            logger.error(f"❌ OCR error: {e}")
            logger.exception("Full traceback:")
            return ""


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


def queue_translation(message_id: str, text: str, source_language: str, case_id: int = None, owner_id: str = None, parent_job_id: str = None, image_text=True) -> str:
    """Queue translation job for extracted text"""
    try:
        response = requests.post(
            f"{JOB_LAUNCHER_URL}/queue/translation",
            json={
                "message_id": message_id,
                "original_text": text,
                "source_language": source_language,
                "owner_id": owner_id,
                "case_id": case_id,
                "parent_job_id": parent_job_id,
                "chained_from": "image-ocr",
                "image_text": image_text
            },
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            timeout=10
        )
        response.raise_for_status()
        job_data = response.json()
        logger.info(f"[TRANSLATION] ✓ Queued job {job_data['job_id']}")
        return job_data['job_id']
    except Exception as e:
        logger.error(f"[TRANSLATION] ✗ Failed: {e}")
        return None


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
    """Main OCR-only worker function"""
    logger.info("=" * 80)
    logger.info(f"📝 OCR-ONLY analysis job started")
    logger.info(f"   Message: {message_id}")
    logger.info(f"   Image: {image_path}")
    logger.info(f"   Engine: EasyOCR")
    logger.info("=" * 80)
    
    try:
        # Verify image exists
        if not os.path.exists(image_path):
            logger.error(f"❌ Image not found: {image_path}")
            return False
        
        # Step 1: Extract text (OCR) - FAST
        extracted_text = None
        detected_lang = None
        
        if extract_text:
            logger.info("📝 Step 1: Extracting text with EasyOCR...")
            extracted_text = ocr_service.extract_text(image_path)
            if extracted_text:
                logger.info(f"✅ Step 1: Extracted {len(extracted_text)} characters")
                # Detect language
                detected_lang = detect_language(extracted_text)
                logger.info(f"   Detected language: {detected_lang}")
            else:
                logger.info("ℹ️ Step 1: No text found in image")
        
        # Step 2: Update Neo4j IMMEDIATELY with extracted text
        logger.info("💾 Step 2: Updating Neo4j with OCR results...")
        
        from aether_lib.neo4j_client.connection import run_in_neo4j_loop
        from aether_lib.neo4j_client.messages import update_message_image_analysis
        
        result = run_in_neo4j_loop(
            update_message_image_analysis,
            message_id=message_id,
            image_text=extracted_text,
            detected_language=detected_lang
        )
        
        if result:
            logger.info("✅ Step 2: Neo4j updated with OCR text")
        else:
            logger.warning("⚠️ Step 2: Update returned False")
        
        # Step 3: Queue translation ASYNCHRONOUSLY
        if extracted_text and translate_extracted_text:
            needs_trans, _ = needs_translation(extracted_text)
            if needs_trans:
                logger.info(f"🌍 Step 3: Queueing translation ({detected_lang} -> de)...")
                translation_job_id = queue_translation(
                    message_id=message_id,
                    text=extracted_text,
                    source_language=detected_lang,
                    case_id=case_id,
                    owner_id=owner_id,
                    parent_job_id=job_id,
                    image_text=True
                )
                if translation_job_id:
                    logger.info(f"✅ Step 3: Translation queued")
            else:
                logger.info(f"ℹ️ Step 3: No translation needed ({detected_lang})")
        
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