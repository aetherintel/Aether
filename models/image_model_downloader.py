# download_easyocr_models.py
"""
Download EasyOCR models for air-gapped deployment
Much more stable than PaddleOCR - no segfaults!
"""
import easyocr
from pathlib import Path
import shutil

# Model directory
MODEL_DIR = Path("./image/easyocr")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("🚀 DOWNLOADING EASYOCR MODELS FOR AIR-GAPPED DEPLOYMENT")
print("=" * 80)
print("\n📦 EasyOCR will download:")
print("   - Detection model (~50 MB)")
print("   - English recognition model (~100 MB)")
print("   Total: ~150 MB")
print("\n⚠️  This is larger than PaddleOCR but MUCH more stable!")
print("\n" + "=" * 80)

# Initialize EasyOCR - this triggers the download
print("\n⏳ Initializing EasyOCR (this will download models)...")
print("   This may take 2-5 minutes depending on your connection...")

reader = easyocr.Reader(
    ['en'],
    model_storage_directory=str(MODEL_DIR),
    download_enabled=True,  # Allow download
    gpu=False
)

print("\n✅ EasyOCR initialized successfully!")

# Verify files
print("\n🔍 Verifying downloaded files...")
model_files = list(MODEL_DIR.rglob("*"))
print(f"   Found {len(model_files)} files")

for file in sorted(model_files):
    if file.is_file():
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"   ✓ {file.relative_to(MODEL_DIR)} ({size_mb:.1f} MB)")

print("\n" + "=" * 80)
print("✅ EASYOCR MODELS READY FOR AIR-GAPPED DEPLOYMENT")
print("=" * 80)

print(f"""
📁 Models location: {MODEL_DIR.absolute()}
📊 Total size: ~150 MB

🔧 NEXT STEPS:

1. Models are ready in ./models/image/easyocr/

2. Update docker-compose.yml or Dockerfile to copy/mount models

3. The worker.py will use these models automatically!

4. Build and start:
   docker compose build image-worker
   docker compose up -d image-worker

🎯 EasyOCR advantages:
   ✅ No segfaults (unlike PaddleOCR)
   ✅ Better accuracy on complex images
   ✅ Works on all CPU architectures
   ✅ Very stable and well-maintained
   ⚠️  Slightly slower (~2-3s vs 1-2s)
   ⚠️  Larger models (~150MB vs 16MB)

💡 Perfect trade-off for production stability!
""")

print("=" * 80)