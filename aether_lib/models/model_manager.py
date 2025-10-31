"""
Central Model Manager for Aether
Handles loading and caching of AI models from local storage
Supports air-gapped deployments with manual model placement
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Manages loading and caching of AI models from local storage.
    Supports both programmatic download and manual model placement.
    """
    
    # Base path for all models (can be overridden via env var)
    MODELS_BASE_PATH = Path(os.getenv("MODELS_PATH", "/app/models"))
    
    # Model registry - maps model identifiers to local paths
    MODEL_REGISTRY = {
        "translation": {
            "ru-en": "opus-mt-ru-en",
            "ar-en": "opus-mt-ar-en",
            "trk-en": "opus-mt-trk-en",
            "en-de": "opus-mt-en-de",
        },
        "image_analysis": {
            # Add image models here in the future
            # "clip": "clip-vit-base-patch32",
        }
    }
    
    def __init__(self):
        self._model_cache: Dict[str, Tuple] = {}
        self._ensure_models_directory()
    
    def _ensure_models_directory(self):
        """Just check that model folders exist; don't create them."""
        logger.info(f"📁 Models base path: {self.MODELS_BASE_PATH}")
        if not self.MODELS_BASE_PATH.exists():
            logger.warning(f"⚠️ Model path {self.MODELS_BASE_PATH} does not exist")

    
    def get_model_path(self, model_type: str, model_key: str) -> Path:
        """
        Get the local path for a model
        
        Args:
            model_type: Type of model (e.g., "translation", "image_analysis")
            model_key: Specific model identifier (e.g., "ru-en")
            
        Returns:
            Path to the model directory
        """
        if model_type not in self.MODEL_REGISTRY:
            raise ValueError(f"Unknown model type: {model_type}")
        
        if model_key not in self.MODEL_REGISTRY[model_type]:
            raise ValueError(f"Unknown model key '{model_key}' for type '{model_type}'")
        
        model_name = self.MODEL_REGISTRY[model_type][model_key]
        return self.MODELS_BASE_PATH / model_type / model_name
    
    def is_model_available(self, model_type: str, model_key: str) -> bool:
        """
        Check if a model is available locally (supports .bin and .safetensors)
        """
        try:
            model_path = self.get_model_path(model_type, model_key)
            if not model_path.exists():
                return False

            # Essential config
            has_config = (model_path / "config.json").exists()

            # Accept either .bin or .safetensors
            has_model = (
                (model_path / "pytorch_model.bin").exists()
                or any(model_path.glob("pytorch_model-*.bin"))
                or (model_path / "model.safetensors").exists()
                or any(model_path.glob("model-*.safetensors"))
            )

            return has_config and has_model

        except (ValueError, OSError):
            return False

    def load_translation_model(
        self, 
        source_lang: str, 
        target_lang: str = "de",
        device: str = "cpu",
        use_quantization: bool = True
    ) -> Tuple[AutoModelForSeq2SeqLM, AutoTokenizer]:
        """
        Load a translation model from local storage
        
        Args:
            source_lang: Source language code (e.g., "ru", "ar")
            target_lang: Target language code (default: "en")
            device: Device to load model on ("cpu" or "cuda")
            use_quantization: Whether to apply dynamic quantization
            
        Returns:
            Tuple of (model, tokenizer)
        """
        model_key = f"{source_lang}-{target_lang}"
        cache_key = f"translation_{model_key}"
        
        # Return cached model if available
        if cache_key in self._model_cache:
            logger.info(f"♻️  Using cached model: {model_key}")
            return self._model_cache[cache_key]
        
        # Check if model is available locally
        if not self.is_model_available("translation", model_key):
            raise FileNotFoundError(
                f"Translation model '{model_key}' not found locally at "
                f"{self.get_model_path('translation', model_key)}\n"
                f"Please download the model using download_models.py or "
                f"manually place the model files in the models directory."
            )
        
        model_path = self.get_model_path("translation", model_key)
        logger.info(f"📦 Loading {model_key} from {model_path}")
        
        try:
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                local_files_only=True
            )
            
            # Load model
            model = AutoModelForSeq2SeqLM.from_pretrained(
                str(model_path),
                local_files_only=True
            )
            
            model = model.to(device)
            
            # Apply quantization if requested
            if use_quantization and device == "cpu":
                logger.info("  ⚡ Applying dynamic quantization")
                model = torch.quantization.quantize_dynamic(
                    model, {torch.nn.Linear}, dtype=torch.qint8
                )
            
            # Cache the model
            self._model_cache[cache_key] = (model, tokenizer)
            
            logger.info(f"  ✅ Loaded {model_key}")
            return model, tokenizer
            
        except Exception as e:
            logger.error(f"❌ Failed to load model {model_key}: {e}")
            raise
    
    def list_available_models(self) -> Dict[str, list]:
        """
        List all locally available models
        
        Returns:
            Dictionary mapping model types to lists of available model keys
        """
        available = {}
        
        for model_type, models in self.MODEL_REGISTRY.items():
            available[model_type] = [
                key for key in models.keys()
                if self.is_model_available(model_type, key)
            ]
        
        return available
    
    def clear_cache(self):
        """Clear the model cache to free up memory"""
        self._model_cache.clear()
        logger.info("🧹 Model cache cleared")


# Global instance
_model_manager = None

def get_model_manager() -> ModelManager:
    """Get or create the global ModelManager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
