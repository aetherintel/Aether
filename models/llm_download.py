# workers/models/download_model.py
"""
Model Download & Management für Aether LLM Services
Lädt Models herunter und macht sie für Container verfügbar
"""
import os
from pathlib import Path
from huggingface_hub import hf_hub_download
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models directory
MODELS_DIR = Path(__file__).parent.resolve() / "llm"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_REGISTRY = {
    "qwen3-0.6b-q4": {
        "repo_id": "unsloth/Qwen3-0.6B-GGUF", 
        "filename": "Qwen3-0.6B-Q4_K_M.gguf",
        "output_name": "qwen3-0.6b-q4.gguf",
        "size_gb": 0.5
    },
    "phi3.5-mini-q4": {
        "repo_id": "bartowski/Phi-3.5-mini-instruct-GGUF",
        "filename": "Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "output_name": "phi3.5-mini-q4.gguf",
        "size_gb": 2.2
    },
    "phi3.5-mini-q6": {
        "repo_id": "bartowski/Phi-3.5-mini-instruct-GGUF",
        "filename": "Phi-3.5-mini-instruct-Q6_K.gguf",
        "output_name": "Phi-3.5-mini-instruct-Q6_K.gguf",
        "size_gb": 3.0
    },
    "llama3.2-1b-q4": {
        "repo_id": "bartowski/Llama-3.2-1B-Instruct-GGUF",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "output_name": "llama3.2-1b-q4.gguf",
        "size_gb": 0.8
    },
    "llama3.2-1b-q4": {
        "repo_id": "bartowski/Llama-3.2-1B-Instruct-GGUF",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "output_name": "llama3.2-1b-q4.gguf",
        "size_gb": 0.8
    },
    "qwen2.5-coder-0.5b-instruct": {
        "repo_id": "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
        "output_name": "qwen2.5-coder-0.5b-instruct.gguf",
        "size_gb": 0.4
    },
    "qwen2.5-7b-instruct-q4": {
        "repo_id": "paultimothymooney/Qwen2.5-7B-Instruct-Q4_K_M-GGUF",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "output_name": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "size_gb": 4.4
    },
    "qwen2.5-14b-instruct-q4": {
        "repo_id": "bartowski/Qwen2.5-14B-Instruct-GGUF",
        "filename": "Qwen2.5-14B-Instruct-Q4_K_M.gguf",
        "output_name": "qwen2.5-14b-instruct-q4_k_m.gguf",
        "size_gb": 9.0
    },
    "qwen2.5-32b-instruct-q4": {
        "repo_id": "bartowski/Qwen2.5-32B-Instruct-GGUF",
        "filename": "Qwen2.5-32B-Instruct-Q4_K_M.gguf",
        "output_name": "qwen2.5-32b-instruct-q4_k_m.gguf",
        "size_gb": 19.9
    },
    "mistral-small-24b-instruct-q4": {
        "repo_id": "bartowski/Mistral-Small-24B-Instruct-2501-GGUF",
        "filename": "Mistral-Small-24B-Instruct-2501-Q4_K_M.gguf",
        "output_name": "mistral-small-24b-instruct-2501-q4_k_m.gguf",
        "size_gb": 15.0
    },
    "codestral-22b-v0.1-q4": {
        "repo_id": "bartowski/Codestral-22B-v0.1-GGUF",
        "filename": "Codestral-22B-v0.1-Q4_K_M.gguf",
        "output_name": "codestral-22b-v0.1-q4_k_m.gguf",
        "size_gb": 13.3
    }
}

def get_model_path(model_key: str) -> Path:
    """Returns full path for model"""
    if model_key not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_key}. Available: {list(MODEL_REGISTRY.keys())}")
    
    config = MODEL_REGISTRY[model_key]
    return MODELS_DIR / config["output_name"]

def is_model_downloaded(model_key: str) -> bool:
    """Check if model exists"""
    model_path = get_model_path(model_key)
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Model {model_key}: {model_path.name} ({size_mb:.1f} MB)")
        return True
    logger.info(f"✗ Model {model_key}: not found")
    return False

def download_model(model_key: str, force: bool = False) -> Path:
    """Download model from HuggingFace"""
    if model_key not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_key}. Available: {list(MODEL_REGISTRY.keys())}")
    
    config = MODEL_REGISTRY[model_key]
    output_path = get_model_path(model_key)
    
    if not force and output_path.exists():
        logger.info(f"Model {model_key} already exists, skipping")
        return output_path
    
    logger.info(f"Downloading {model_key}...")
    logger.info(f"  Repo: {config['repo_id']}")
    logger.info(f"  File: {config['filename']}")
    logger.info(f"  Size: ~{config['size_gb']:.1f} GB")
    logger.info(f"  Target: {output_path}")
    
    try:
        downloaded_path = hf_hub_download(
            repo_id=config["repo_id"],
            filename=config["filename"],
            cache_dir=MODELS_DIR / ".cache",
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False
        )
        
        downloaded_file = Path(downloaded_path)
        
        # Rename to standard name
        if downloaded_file.name != config["output_name"]:
            logger.info(f"Renaming to {config['output_name']}")
            downloaded_file.rename(output_path)
        
        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Downloaded {model_key} ({size_mb:.1f} MB)")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to download {model_key}: {e}")
        raise

def list_models():
    """List all models"""
    logger.info("\n=== Available Models ===")
    for key, config in MODEL_REGISTRY.items():
        status = "✓" if is_model_downloaded(key) else "✗"
        logger.info(f"{status} {key:20s} (~{config['size_gb']:.1f} GB)")
    
    # Show actual files in directory
    logger.info("\n=== Files in models/ ===")
    for file in sorted(MODELS_DIR.glob("*.gguf")):
        size_mb = file.stat().st_size / (1024 * 1024)
        logger.info(f"  {file.name} ({size_mb:.1f} MB)")

def cleanup(keep_models: list[str] = None):
    """Remove old models"""
    if keep_models is None:
        keep_models = []
    
    keep_paths = {get_model_path(m) for m in keep_models if m in MODEL_REGISTRY}
    
    logger.info("Cleaning up old models...")
    removed_count = 0
    for model_file in MODELS_DIR.glob("*.gguf"):
        if model_file not in keep_paths:
            size_mb = model_file.stat().st_size / (1024 * 1024)
            logger.info(f"  Removing {model_file.name} ({size_mb:.1f} MB)")
            model_file.unlink()
            removed_count += 1
    
    if removed_count == 0:
        logger.info("  No models to remove")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage LLM models for Aether")
    parser.add_argument(
        "action",
        choices=["download", "list", "cleanup", "check"],
        help="Action to perform"
    )
    parser.add_argument(
        "--model",
        default="qwen3-0.6b-q4",
        help="Model key (default: qwen3-0.6b-q4)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download"
    )
    parser.add_argument(
        "--keep",
        nargs="+",
        help="Models to keep during cleanup"
    )
    
    args = parser.parse_args()
    
    try:
        if args.action == "download":
            download_model(args.model, force=args.force)
            
        elif args.action == "list":
            list_models()
            
        elif args.action == "cleanup":
            cleanup(keep_models=args.keep)
            
        elif args.action == "check":
            exists = is_model_downloaded(args.model)
            exit(0 if exists else 1)
                
    except Exception as e:
        logger.error(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()