# workers/audio_worker/worker.py
"""
Audio Transcription Worker with Whisper
Transcribes audio messages and extracts audio from videos
Fully air-gapped with local models
"""
import os
import logging
import requests
from pathlib import Path
import subprocess
import tempfile
from typing import Optional, Tuple

from aether_lib.queue_client import queue_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Local model paths (mounted from host)
MODEL_BASE_DIR = Path(os.getenv("MODEL_BASE_DIR", "/app/models/audio"))

# Global Whisper model
WHISPER_MODEL = None


# Translation Configuration
SUPPORTED_TRANSLATION_LANGUAGES = ['ru', 'ar', 'tr', 'en']

# Supported audio/video formats
AUDIO_FORMATS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.opus', '.wma', '.aac'}
VIDEO_FORMATS = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v'}

# ============================================================================
# MODEL LOADING
# ============================================================================

def load_whisper_model():
    """Load Whisper model from local directory (air-gapped)"""
    global WHISPER_MODEL
    
    logger.info("=" * 80)
    logger.info("🎙️ LOADING WHISPER MODEL (AIR-GAPPED MODE)")
    logger.info("=" * 80)
    
    try:
        import whisper
        import torch
        
        # Check device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"📱 Using device: {device}")
        
        # Model storage
        model_dir = MODEL_BASE_DIR / "whisper"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Use base model for faster performance
        # Options: tiny, base, small, medium, large
        model_name = "base"
        model_path = model_dir / f"{model_name}.pt"
        
        logger.info(f"📁 Model directory: {model_dir}")
        logger.info(f"   Model: whisper-{model_name}")
        logger.info(f"   Path: {model_path}")
        
        # Check if model exists locally
        if model_path.exists():
            logger.info(f"✅ Found local model: {model_path}")
            logger.info(f"   Size: {model_path.stat().st_size / (1024**3):.2f} GB")
            # Load from local file
            WHISPER_MODEL = whisper.load_model(
                str(model_path),
                device=device,
                download_root=str(model_dir)
            )
        else:
            logger.info(f"⏳ Model not found locally, loading whisper-{model_name}...")
            # This will download on first run, then use local cache
            WHISPER_MODEL = whisper.load_model(
                model_name,
                device=device,
                download_root=str(model_dir)
            )
            logger.info(f"💾 Model saved to: {model_dir}")
        
        logger.info("✅ Whisper loaded successfully!")
        logger.info(f"   Model: whisper-{model_name}")
        logger.info(f"   Languages: 100+ (auto-detect)")
        logger.info(f"   Speed: ~1-2x realtime on CPU")
        logger.info(f"   Quality: High (word error rate ~5-10%)")
        
    except Exception as e:
        logger.error(f"❌ Failed to load Whisper: {e}")
        logger.exception("Full traceback:")
        logger.error("   Transcription will be disabled")
        WHISPER_MODEL = None
    
    logger.info("=" * 80)


# Load at import time
load_whisper_model()


# ============================================================================
# AUDIO EXTRACTION SERVICE
# ============================================================================

class AudioExtractor:
    """Extract audio from video files using ffmpeg"""
    
    @staticmethod
    def check_ffmpeg() -> bool:
        """Check if ffmpeg is installed"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def extract_audio_from_video(video_path: str, output_path: str = None) -> Optional[str]:
        """
        Extract audio track from video file
        
        Args:
            video_path: Path to video file
            output_path: Optional output path for audio file
        
        Returns:
            Path to extracted audio file or None if failed
        """
        if not AudioExtractor.check_ffmpeg():
            logger.error("❌ ffmpeg not installed, cannot extract audio")
            return None
        
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                logger.error(f"❌ Video file not found: {video_path}")
                return None
            
            # Create output path if not specified
            if output_path is None:
                output_path = tempfile.mktemp(suffix='.wav')
            
            logger.info(f"🎬 Extracting audio from: {video_path.name}")
            logger.info(f"   Output: {output_path}")
            
            # ffmpeg command to extract audio as WAV (best for Whisper)
            cmd = [
                'ffmpeg',
                '-i', str(video_path),           # Input video
                '-vn',                            # No video
                '-acodec', 'pcm_s16le',          # PCM 16-bit for Whisper
                '-ar', '16000',                   # 16kHz sample rate (Whisper optimal)
                '-ac', '1',                       # Mono audio
                '-y',                             # Overwrite output
                str(output_path)
            ]
            
            # Run extraction
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"❌ ffmpeg failed: {result.stderr.decode()[:200]}")
                return None
            
            # Verify output file
            output_file = Path(output_path)
            if output_file.exists():
                size_mb = output_file.stat().st_size / (1024**2)
                logger.info(f"✅ Audio extracted: {size_mb:.1f} MB")
                return str(output_file)
            else:
                logger.error("❌ Output file not created")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Audio extraction timed out")
            return None
        except Exception as e:
            logger.error(f"❌ Audio extraction error: {e}")
            logger.exception("Full traceback:")
            return None


# ============================================================================
# TRANSCRIPTION SERVICE
# ============================================================================

class TranscriptionService:
    """Whisper-based transcription service"""
    
    def __init__(self):
        if WHISPER_MODEL is None:
            logger.info("🔄 Whisper model not loaded, loading now...")
            load_whisper_model()
        
        if WHISPER_MODEL is None:
            logger.error("❌ CRITICAL: Whisper model failed to load!")
        else:
            logger.info("✅ Transcription service ready")
        
        self.audio_extractor = AudioExtractor()
    
    def transcribe_audio(self, audio_path: str, language: str = None) -> Tuple[str, str]:
        """
        Transcribe audio file using Whisper
        
        Args:
            audio_path: Path to audio file
            language: Optional language hint (e.g., 'en', 'ru', 'ar')
        
        Returns:
            Tuple of (transcription, detected_language)
        """
        if WHISPER_MODEL is None:
            logger.warning("⚠️ Whisper not loaded, skipping transcription")
            return "", "unknown"
        
        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                logger.error(f"❌ Audio file not found: {audio_path}")
                return "", "unknown"
            
            # Get file info
            size_mb = audio_path.stat().st_size / (1024**2)
            logger.info(f"🎙️ Transcribing: {audio_path.name}")
            logger.info(f"   Size: {size_mb:.1f} MB")
            if language:
                logger.info(f"   Language hint: {language}")
            
            # Transcribe with Whisper
            logger.info("⏳ Running Whisper transcription...")
            result = WHISPER_MODEL.transcribe(
                str(audio_path),
                language=language,      # Optional language hint
                task="transcribe",       # "transcribe" or "translate" (to English)
                fp16=False,             # Disable FP16 for CPU compatibility
                verbose=False           # Reduce output noise
            )
            
            # Extract results
            text = result.get("text", "").strip()
            detected_lang = result.get("language", "unknown")
            
            if text:
                logger.info(f"✅ Transcribed {len(text)} characters")
                logger.info(f"   Language: {detected_lang}")
                logger.info(f"   Preview: {text[:100]}...")
            else:
                logger.warning("⚠️ No speech detected in audio")
            
            return text, detected_lang
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            logger.exception("Full traceback:")
            return "", "unknown"
    
    def transcribe_video(self, video_path: str, language: str = None) -> Tuple[str, str]:
        """
        Extract and transcribe audio from video file
        
        Args:
            video_path: Path to video file
            language: Optional language hint
        
        Returns:
            Tuple of (transcription, detected_language)
        """
        logger.info(f"🎬 Processing video: {video_path}")
        
        # Step 1: Extract audio from video
        audio_file = self.audio_extractor.extract_audio_from_video(video_path)
        if not audio_file:
            logger.error("❌ Failed to extract audio from video")
            return "", "unknown"
        
        try:
            # Step 2: Transcribe extracted audio
            text, detected_lang = self.transcribe_audio(audio_file, language)
            return text, detected_lang
            
        finally:
            # Cleanup temp audio file
            try:
                if audio_file and os.path.exists(audio_file):
                    os.unlink(audio_file)
                    logger.info(f"🗑️ Cleaned up temp file: {audio_file}")
            except Exception as e:
                logger.warning(f"⚠️ Could not cleanup temp file: {e}")


transcription_service = TranscriptionService()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_language(text: str) -> str:
    """Detect language of transcribed text"""
    if not text or len(text.strip()) < 10:
        return 'unknown'
    
    try:
        from langdetect import detect
        lang = detect(text)
        return lang
    except Exception:
        logger.warning(f"⚠️ Could not detect language")
        return 'unknown'


def needs_translation(text: str, detected_lang: str) -> bool:
    """Check if transcribed text needs translation"""
    if not text:
        return False
    
    if detected_lang == 'de':
        return False
    
    if detected_lang in SUPPORTED_TRANSLATION_LANGUAGES:
        logger.info(f"🌍 Text needs translation: {detected_lang} -> de")
        return True
    
    logger.info(f"ℹ️ Language {detected_lang} not supported for translation")
    return False



def get_file_type(file_path: str) -> str:
    """Determine if file is audio or video"""
    suffix = Path(file_path).suffix.lower()
    
    if suffix in AUDIO_FORMATS:
        return "audio"
    elif suffix in VIDEO_FORMATS:
        return "video"
    else:
        # Try to detect by content
        logger.warning(f"⚠️ Unknown file type: {suffix}, assuming audio")
        return "audio"


# ============================================================================
# WORKER JOB FUNCTION
# ============================================================================

def transcribe_and_update(
    message_id: str,
    media_path: str,
    media_type: str = None,  # 'audio' or 'video' (auto-detect if None)
    language_hint: str = None,
    translate_transcription: bool = True,
    owner_id: str = None,
    case_id: int = None,
    job_id: str = None
):
    """
    Main audio transcription worker function
    
    Args:
        message_id: Message ID to update
        media_path: Path to audio or video file
        media_type: 'audio' or 'video' (auto-detect if None)
        language_hint: Optional language hint for Whisper
        translate_transcription: Whether to queue translation
        owner_id: Owner ID for logging
        case_id: Case ID for context
        job_id: Current job ID
    """
    logger.info("=" * 80)
    logger.info(f"🎙️ Audio transcription job started")
    logger.info(f"   Message: {message_id}")
    logger.info(f"   Media: {media_path}")
    logger.info(f"   Type: {media_type or 'auto-detect'}")
    logger.info(f"   Engine: Whisper")
    logger.info("=" * 80)
    
    try:
        # Verify file exists
        if not os.path.exists(media_path):
            logger.error(f"❌ Media file not found: {media_path}")
            return False
        
        # Auto-detect media type if not specified
        if media_type is None:
            media_type = get_file_type(media_path)
            logger.info(f"   Detected type: {media_type}")
        
        # Step 1: Transcribe audio/video
        logger.info(f"📝 Step 1: Transcribing {media_type}...")
        
        if media_type == "video":
            transcription, detected_lang = transcription_service.transcribe_video(
                media_path,
                language_hint
            )
        else:
            transcription, detected_lang = transcription_service.transcribe_audio(
                media_path,
                language_hint
            )
        
        if transcription:
            logger.info(f"✅ Step 1: Transcribed {len(transcription)} characters")
        else:
            logger.info("ℹ️ Step 1: No speech detected")
        
        # Step 2: Update Neo4j with transcription
        logger.info("💾 Step 2: Updating Neo4j with transcription...")
        
        from aether_lib.neo4j_client.connection import run_in_neo4j_loop
        from aether_lib.neo4j_client.messages import update_message_audio_transcription
        
        result = run_in_neo4j_loop(
            update_message_audio_transcription,
            message_id=message_id,
            audio_text=transcription,
            detected_language=detected_lang,
            media_type=media_type
        )
        
        if result:
            logger.info("✅ Step 2: Neo4j updated with transcription")
        else:
            logger.warning("⚠️ Step 2: Update returned False")
        
        # Step 3: Queue translation if needed
        if transcription and translate_transcription:
            if needs_translation(transcription, detected_lang):
                logger.info(f"🌍 Step 3: Queueing translation ({detected_lang} -> de)...")
                translation_payload = {
                    'message_id': message_id,
                    'original_text': transcription, 
                    'source_language': detected_lang,
                    'case_id': case_id,
                    'owner_id': owner_id,
                    'parent_job_id': job_id,
                    'audio_text': True
                }
                translation_job_id = queue_client.QueueClient.enqueue_translation(
                    translation_payload=translation_payload
                )
                if translation_job_id:
                    logger.info(f"✅ Step 3: Translation queued")
            else:
                logger.info(f"ℹ️ Step 3: No translation needed ({detected_lang})")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Job FAILED: {message_id}")
        logger.error(f"   Error: {e}")
        raise