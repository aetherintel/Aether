#!/usr/bin/env python3
"""
Download Whisper models for air-gapped deployment
Run this on a machine with internet to prepare models
"""
import os
import sys
import whisper
from pathlib import Path

def download_whisper_models(output_dir: str = "./models/audio/whisper"):
    """Download Whisper models for offline use"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("🎙️ DOWNLOADING WHISPER MODELS FOR AIR-GAPPED DEPLOYMENT")
    print("=" * 80)
    
    # Models to download (choose based on your needs)
    # Size vs Quality tradeoff:
    # - tiny: 39M, fastest, lowest quality
    # - base: 74M, fast, decent quality
    # - small: 244M, good balance
    # - medium: 769M, recommended for production
    # - large: 1550M, best quality, slow
    
    models_to_download = [
        #"medium",  # Recommended for production
        #"small",   # Backup/faster option
        "base"     # Fastest option
    ]
    
    for model_name in models_to_download:
        print(f"\n📦 Downloading whisper-{model_name}...")
        
        try:
            # This downloads and caches the model
            model = whisper.load_model(
                model_name,
                download_root=str(output_path)
            )
            
            # Find the downloaded file
            model_file = output_path / f"{model_name}.pt"
            
            if model_file.exists():
                size_mb = model_file.stat().st_size / (1024**2)
                print(f"✅ Downloaded: {model_file}")
                print(f"   Size: {size_mb:.1f} MB")
            else:
                print(f"⚠️ Model file not found at expected location")
                
        except Exception as e:
            print(f"❌ Failed to download {model_name}: {e}")
            sys.exit(1)
    
    print("\n" + "=" * 80)
    print("✅ ALL MODELS DOWNLOADED SUCCESSFULLY")
    print(f"📁 Location: {output_path.absolute()}")
    print("\nNext steps:")
    print("1. Copy the entire folder to your air-gapped environment")
    print("2. Mount it at: /app/models/audio/whisper")
    print("3. The worker will automatically detect and use local models")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download Whisper models for offline use")
    parser.add_argument(
        "--output-dir",
        default="./models/audio/whisper",
        help="Directory to save models (default: ./models/audio/whisper)"
    )
    
    args = parser.parse_args()
    download_whisper_models(args.output_dir)
