# modal/classification_worker.py
# =============================================================================
# Aether Classification Worker — Modal deployment
# =============================================================================
# Pure inference endpoint: accepts text, returns illegal/suspicious content
# classifications. No database access, no business logic — the calling backend
# handles all that.
#
# Setup (one-time):
#   modal run modal/classification_worker.py::download_model
#   modal deploy modal/classification_worker.py
# =============================================================================

import os
import logging
import time
from typing import List

import modal
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modal primitives
# ---------------------------------------------------------------------------

app = modal.App("aether-classification-worker")

classification_volume = modal.Volume.from_name("aether-classification-models", create_if_missing=True)

MODEL_DIR = "/models/classification"
MODEL_NAME = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
MODEL_PATH = f"{MODEL_DIR}/mDeBERTa-v3-base-xnli"

classification_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers>=4.35.0",
        "torch",
        "huggingface_hub",
        "fastapi[standard]",
        "pydantic>=2",
    )
)

# ---------------------------------------------------------------------------
# 20-category illegal/suspicious content taxonomy
# ---------------------------------------------------------------------------

CLASSIFICATION_LABELS = {
    1: "Propaganda",
    2: "Aufruf zur Gewalt",
    3: "Hassrede / Hate Speech",
    4: "Drogenhandel",
    5: "Waffenhandel",
    6: "Finanzbetrug / Scam",
    7: "Cybercrime / Hacking",
    8: "Extremismus / Terrorismus",
    9: "Fake News / Desinformation",
    10: "Rekrutierung / Mobilisierung",
    11: "Demonstrationsaufruf",
    12: "Kinderpornografie / Sexualdelikte",
    13: "Menschenhandel / Ausbeutung",
    14: "Geldwäsche / Krypto-Transfers",
    15: "Bedrohung / Erpressung",
    16: "Koordinierte Aktion / Gruppe",
    17: "Anleitung / How-To (illegale Handlung)",
    18: "Codewörter / Verschleierung",
    19: "Finanztransaktion / Spende",
    20: "Allgemeine Kommunikation / Unauffällig",
}

LABEL_DESCRIPTIONS = {
    1: "Politische oder ideologische Beeinflussung, Propaganda, Meinungsmache",
    2: "Direkte oder indirekte Gewaltandrohung, Aufruf zu gewalttätigen Aktionen",
    3: "Abwertung, Diskriminierung oder Hass gegen bestimmte Gruppen oder Personen",
    4: "Angebote, Nachfrage oder Handel mit illegalen Drogen und Substanzen",
    5: "Handel, Verkauf oder Besitz illegaler Waffen",
    6: "Phishing, Fake-Investments, Schneeballsysteme, Betrug",
    7: "Hinweise auf digitale Angriffe, Hacking, Datenhandel, Malware",
    8: "Extremistische Inhalte, Terrorismus, radikale Ideologien",
    9: "Falschinformationen, Desinformation, gezielte Manipulation",
    10: "Versuch Personen für illegale Aktivitäten oder Bewegungen zu rekrutieren",
    11: "Organisation von Demonstrationen, Protesten oder realen Versammlungen",
    12: "Hinweise auf sexuellen Missbrauch oder Verbreitung illegaler sexueller Inhalte",
    13: "Menschenhandel, Zwangsarbeit, Ausbeutung von Personen",
    14: "Verdächtige Geldflüsse, Kryptowährungstransfers, Geldwäsche",
    15: "Individuelle Drohungen, Erpressung, Nötigung",
    16: "Planung koordinierter illegaler Aktionen in Gruppen",
    17: "Anleitungen für illegale Handlungen wie Waffenbau oder Drogensynthese",
    18: "Verwendung von Codewörtern, Slang oder Tarnsprache zur Verschleierung",
    19: "Aufrufe zu Spenden oder Geldtransfers für illegale Zwecke",
    20: "Normale, unauffällige Kommunikation ohne verdächtige Inhalte",
}

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ClassificationRequest(BaseModel):
    text: str
    threshold: float = 0.7
    top_k: int = 3


class ClassificationLabel(BaseModel):
    label_id: int
    label: str
    description: str
    confidence: float
    method: str


class ClassificationResponse(BaseModel):
    classifications: List[ClassificationLabel]
    inference_time: float


# ---------------------------------------------------------------------------
# One-shot model downloader
# ---------------------------------------------------------------------------

@app.function(
    image=classification_image,
    volumes={MODEL_DIR: classification_volume},
    timeout=1800,
)
def download_model():
    """
    Download mDeBERTa-v3-base-xnli from HuggingFace to the Modal volume.
    Run once: modal run modal/classification_worker.py::download_model
    """
    from huggingface_hub import snapshot_download

    if os.path.exists(MODEL_PATH) and os.listdir(MODEL_PATH):
        print(f"Model already present at {MODEL_PATH} — skipping download.")
        return

    os.makedirs(MODEL_PATH, exist_ok=True)
    print(f"Downloading {MODEL_NAME} to {MODEL_PATH} ...")
    snapshot_download(
        repo_id=MODEL_NAME,
        local_dir=MODEL_PATH,
    )
    classification_volume.commit()
    print(f"Done. Model saved to {MODEL_PATH}.")


# ---------------------------------------------------------------------------
# Modal service class — pure inference, no database access
# ---------------------------------------------------------------------------

@app.cls(
    gpu="T4",
    image=classification_image,
    volumes={MODEL_DIR: classification_volume},
    min_containers=0,
    timeout=300,
)
@modal.concurrent(max_inputs=16)
class ClassificationWorker:

    @modal.enter()
    def load_model(self):
        import torch
        from transformers import pipeline

        if not os.path.exists(MODEL_PATH) or not os.listdir(MODEL_PATH):
            raise RuntimeError(
                f"Model not found at {MODEL_PATH}. "
                "Run: modal run modal/classification_worker.py::download_model"
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading {MODEL_NAME} from {MODEL_PATH} on {self.device} ...")

        self.pipeline = pipeline(
            "zero-shot-classification",
            model=MODEL_PATH,
            device=0 if self.device == "cuda" else -1,
            use_fast=True,
        )

        # Candidate labels: all descriptions + a negative "normal content" anchor.
        # Including the anchor label makes the NLI model more discriminative —
        # it gives it an explicit non-criminal hypothesis to score against.
        self.candidate_labels = list(LABEL_DESCRIPTIONS.values())
        # Reverse map: description → label_id
        self.desc_to_id = {desc: lid for lid, desc in LABEL_DESCRIPTIONS.items()}

        logger.info("Classification model loaded (20 categories, multilingual zero-shot).")

    def _run_inference(self, text: str, threshold: float, top_k: int) -> list:
        if not text or not text.strip():
            return [{
                "label_id": 20,
                "label": CLASSIFICATION_LABELS[20],
                "description": LABEL_DESCRIPTIONS[20],
                "confidence": 1.0,
                "method": "empty_text",
            }]

        text = text[:512]

        try:
            result = self.pipeline(
                text,
                self.candidate_labels,
                multi_label=True,
                truncation=True,
            )

            classifications = []
            for desc, score in zip(result["labels"], result["scores"]):
                label_id = self.desc_to_id.get(desc)
                if label_id and score >= threshold:
                    classifications.append({
                        "label_id": label_id,
                        "label": CLASSIFICATION_LABELS[label_id],
                        "description": desc,
                        "confidence": float(score),
                        "method": "zero-shot",
                    })

            # Nothing cleared the threshold — return "Allgemeine Kommunikation".
            # Do NOT fall back to the top prediction: NLI scores are not calibrated
            # confidence values, and forcing a result produces false positives.
            if not classifications:
                classifications.append({
                    "label_id": 20,
                    "label": CLASSIFICATION_LABELS[20],
                    "description": LABEL_DESCRIPTIONS[20],
                    "confidence": 1.0,
                    "method": "below_threshold",
                })

            return classifications[:top_k]

        except Exception as e:
            logger.error(f"Classification inference error: {e}")
            return [{
                "label_id": 20,
                "label": CLASSIFICATION_LABELS[20],
                "description": LABEL_DESCRIPTIONS[20],
                "confidence": 0.5,
                "method": "error_fallback",
            }]

    @modal.fastapi_endpoint(method="POST", docs=True)
    def classify(self, request: ClassificationRequest) -> ClassificationResponse:
        start = time.time()
        classifications = self._run_inference(request.text, request.threshold, request.top_k)
        inference_time = time.time() - start
        logger.info(f"Classified into {len(classifications)} categories in {inference_time:.2f}s")
        return ClassificationResponse(
            classifications=[ClassificationLabel(**c) for c in classifications],
            inference_time=inference_time,
        )

    @modal.fastapi_endpoint(method="GET")
    def health(self):
        return {
            "status": "healthy" if hasattr(self, "pipeline") else "loading",
            "model": "mDeBERTa-v3-base-xnli-multilingual",
        }
