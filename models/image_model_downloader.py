import os
import easyocr
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EasyOCR_Downloader")

# Target directory matches volume mount target in worker or build context
OUTPUT_DIR = os.path.join(os.getcwd(), "easyocr_cache")

def download_models():
    logger.info(f"⬇️ Downloading EasyOCR models into: {OUTPUT_DIR}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Define groups to trigger downloads
    # We just need to initialize Readers; they will download missing models.
    groups = [
        ['en', 'de', 'tr'],
        ['ru', 'en'],
        ['ar', 'en']
    ]
    
    for langs in groups:
        logger.info(f"   Package: {langs}")
        try:
            # Initialize reader to trigger download
            # We set download_enabled=True and verbose=True
            easyocr.Reader(
                lang_list=langs,
                gpu=False,
                model_storage_directory=OUTPUT_DIR,
                download_enabled=True,
                verbose=True
            )
            logger.info("   ✅ Downloaded.")
        except Exception as e:
            logger.error(f"   ❌ Failed: {e}")

if __name__ == "__main__":
    download_models()
