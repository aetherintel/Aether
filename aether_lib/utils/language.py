# lib/utils/language.py
"""
Language detection and translation utilities
"""
from langdetect import detect, LangDetectException

SUPPORTED_TRANSLATION_LANGUAGES = ['ru', 'ar', 'trk', 'en']


def detect_language(text: str) -> str:
    """
    Detect language of text
    Returns language code or 'de' if detection fails
    """
    if not text or len(text.strip()) < 10:
        return 'de'
    
    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        return 'de'


def needs_translation(text: str) -> tuple[bool, str]:
    """
    Check if text needs translation
    
    Returns:
        (needs_translation, detected_language)
    """
    detected_lang = detect_language(text)
    
    # Already German
    if detected_lang == 'de':
        return False, 'de'
    
    # Supported language - needs translation
    if detected_lang in SUPPORTED_TRANSLATION_LANGUAGES:
        return True, detected_lang
    
    # Unsupported language - store as-is
    return False, detected_lang