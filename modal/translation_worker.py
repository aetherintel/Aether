# modal/translation_worker.py
# =============================================================================
# Aether Translation Worker — Modal deployment
# =============================================================================
# Pure inference endpoint: accepts text, returns translated text.
# No database access, no business logic — the calling backend handles all that.
#
# Setup (one-time):
#   modal run modal/translation_worker.py::download_model
#   modal deploy modal/translation_worker.py
# =============================================================================

import os
import logging
import time
from typing import Optional

import modal
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modal primitives
# ---------------------------------------------------------------------------

app = modal.App("aether-translation-worker")

translation_volume = modal.Volume.from_name("aether-translation-models", create_if_missing=True)

MODEL_DIR = "/models/translation"
MODEL_PATH = f"{MODEL_DIR}/nllb-200-distilled-600M"

HF_REPO = "facebook/nllb-200-distilled-600M"

translation_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers>=4.35.0",
        "torch",
        "sentencepiece",
        "protobuf",
        "huggingface_hub",
        "fastapi[standard]",
        "pydantic>=2",
    )
)

# ---------------------------------------------------------------------------
# Language code mapping (BCP-47 → NLLB-200 codes)
# ---------------------------------------------------------------------------

LANG_CODES = {
    "en": "eng_Latn",
    "de": "deu_Latn",
    "ru": "rus_Cyrl",
    "ar": "arb_Arab",
    "tr": "tur_Latn",
    "trk": "tur_Latn",
}

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class TranslationRequest(BaseModel):
    text: str
    source_language: str
    target_language: str = "de"


class TranslationResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str
    inference_time: float


# ---------------------------------------------------------------------------
# One-shot model downloader
# ---------------------------------------------------------------------------

@app.function(
    image=translation_image,
    volumes={MODEL_DIR: translation_volume},
    timeout=3600,
)
def download_model():
    """
    Download NLLB-200-distilled-600M to the Modal volume.
    Run once: modal run modal/translation_worker.py::download_model
    """
    from huggingface_hub import snapshot_download

    if os.path.exists(MODEL_PATH) and os.listdir(MODEL_PATH):
        print(f"Model already present at {MODEL_PATH} — skipping download.")
        return

    os.makedirs(MODEL_PATH, exist_ok=True)
    print(f"Downloading {HF_REPO} to {MODEL_PATH} ...")
    snapshot_download(
        repo_id=HF_REPO,
        local_dir=MODEL_PATH,
        ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "rust_model*"],
    )
    translation_volume.commit()
    print(f"Done. Model saved to {MODEL_PATH}.")


# ---------------------------------------------------------------------------
# Modal service class — pure inference, no database access
# ---------------------------------------------------------------------------

@app.cls(
    gpu="L4",
    image=translation_image,
    volumes={MODEL_DIR: translation_volume},
    min_containers=0,
    timeout=300,
)
@modal.concurrent(max_inputs=8)
class TranslationWorker:

    @modal.enter()
    def load_model(self):
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        if not os.path.exists(MODEL_PATH) or not os.listdir(MODEL_PATH):
            raise RuntimeError(
                f"Model not found at {MODEL_PATH}. "
                "Run: modal run modal/translation_worker.py::download_model"
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading NLLB-200 from {MODEL_PATH} on {self.device} ...")

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
            use_fast=False,
        )

        torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
        ).to(self.device)

        logger.info("NLLB-200 model loaded successfully.")

    def _run_inference(self, text: str, source_lang: str, target_lang: str) -> str:
        import torch

        if not text.strip() or source_lang == target_lang:
            return text

        src_code = LANG_CODES.get(source_lang)
        tgt_code = LANG_CODES.get(target_lang, "deu_Latn")

        if not src_code:
            logger.warning(f"Unsupported language: {source_lang}, returning original")
            return text

        if len(text) > 1000:
            text = text[:1000]

        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=200
        ).to(self.device)

        with torch.no_grad():
            generated_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(tgt_code),
                max_length=200,
                num_beams=1,
                early_stopping=False,
            )

        return self.tokenizer.decode(generated_tokens[0], skip_special_tokens=True)

    @modal.fastapi_endpoint(method="POST", docs=True)
    def translate(self, request: TranslationRequest) -> TranslationResponse:
        start = time.time()
        translated_text = self._run_inference(
            request.text, request.source_language, request.target_language
        )
        inference_time = time.time() - start
        logger.info(
            f"Translated {request.source_language}→{request.target_language} "
            f"in {inference_time:.2f}s"
        )
        return TranslationResponse(
            translated_text=translated_text,
            source_language=request.source_language,
            target_language=request.target_language,
            inference_time=inference_time,
        )

    @modal.fastapi_endpoint(method="GET")
    def health(self):
        return {
            "status": "healthy" if hasattr(self, "model") else "loading",
            "model": "nllb-200-distilled-600M",
        }
