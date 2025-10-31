"""
Shared utilities
"""
from .language import detect_language, needs_translation, SUPPORTED_TRANSLATION_LANGUAGES

__all__ = [
    'detect_language',
    'needs_translation',
    'SUPPORTED_TRANSLATION_LANGUAGES',
]