# modal/download_models.py
# =============================================================================
# One-shot script to seed all Modal volumes with model weights.
# Run this once before deploying the workers.
#
# Usage:
#   modal run modal/download_models.py::download_all
#   # or individually:
#   modal run modal/download_models.py::download_llm
#   modal run modal/download_models.py::download_translation
#   modal run modal/download_models.py::download_emotion
# =============================================================================

import modal

from modal.llm_service import download_model as download_llm          # noqa: F401
from modal.translation_worker import download_model as download_translation  # noqa: F401
from modal.emotion_worker import download_model as download_emotion    # noqa: F401

app = modal.App("aether-download-models")


@app.function(
    timeout=7200,
)
def download_all():
    """Download all model weights to their respective Modal volumes."""
    print("=" * 60)
    print("Downloading LLM model (Codestral 22B Q4) ...")
    print("=" * 60)
    download_llm.local()

    print("=" * 60)
    print("Downloading Translation model (NLLB-200 600M) ...")
    print("=" * 60)
    download_translation.local()

    print("=" * 60)
    print("Downloading Emotion model (german-emotions) ...")
    print("=" * 60)
    download_emotion.local()

    print("=" * 60)
    print("All models downloaded successfully.")
    print("=" * 60)
