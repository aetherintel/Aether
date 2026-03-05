# modal/emotion_worker.py
# =============================================================================
# Aether Emotion Worker — Modal deployment
# =============================================================================
# Pure inference endpoint: accepts text, returns classified emotions.
# No database access, no business logic — the calling backend handles all that.
#
# Setup (one-time):
#   modal run modal/emotion_worker.py::download_model
#   modal deploy modal/emotion_worker.py
# =============================================================================

import os
import logging
import time
from typing import List, Optional

import modal
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modal primitives
# ---------------------------------------------------------------------------

app = modal.App("aether-emotion-worker")

emotion_volume = modal.Volume.from_name("aether-emotion-models", create_if_missing=True)

MODEL_DIR = "/models/emotion"
MODEL_PATH = f"{MODEL_DIR}/german-emotions"

emotion_image = (
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
# Police investigation emotion taxonomy
# ---------------------------------------------------------------------------

POLICE_LABELS = {
    1: "Wut / Aggression",
    2: "Hass / Feindbild",
    3: "Empörung / Entrüstung",
    4: "Angst / Bedrohungsempfinden",
    5: "Panik / Hysterie",
    6: "Verzweiflung / Hoffnungslosigkeit",
    7: "Trauer / Mitgefühl",
    8: "Solidarität / Zusammenhalt",
    9: "Stolz / Selbstermächtigung",
    10: "Freude / Zufriedenheit",
    11: "Ironie / Sarkasmus",
    12: "Aggressive Motivation / Aufpeitschend",
    13: "Feindliche Mobilisierung",
    14: "Resignation / Rückzug",
    15: "Misstrauen / Paranoia",
    16: "Euphorie / Begeisterung",
    17: "Zynismus / Verachtung",
    18: "Mobilisierende Hoffnung",
    19: "Neutral / Informationsorientiert",
    20: "Ambivalent / Gemischt",
}

EMOTION_TO_POLICE = {
    "anger": 1, "annoyance": 1,
    "disgust": 2, "disapproval": 2,
    "disappointment": 3,
    "fear": 4,
    "nervousness": 5,
    "sadness": 6, "grief": 7, "remorse": 7, "embarrassment": 6,
    "caring": 8, "gratitude": 8, "love": 8,
    "pride": 9, "admiration": 9,
    "joy": 10, "amusement": 10, "relief": 10,
    "excitement": 16, "optimism": 18, "desire": 16,
    "curiosity": 19, "confusion": 15, "surprise": 19, "realization": 19, "approval": 19,
    "neutral": 19,
}

EMOTION_COMBINATIONS = {
    frozenset(["anger", "excitement"]): 12,
    frozenset(["anger", "desire"]): 12,
    frozenset(["anger", "pride"]): 13,
    frozenset(["disgust", "anger"]): 13,
    frozenset(["amusement", "annoyance"]): 11,
    frozenset(["amusement", "disapproval"]): 11,
    frozenset(["amusement", "disgust"]): 17,
    frozenset(["sadness", "disappointment"]): 14,
    frozenset(["disappointment", "disapproval"]): 14,
    frozenset(["fear", "confusion"]): 15,
    frozenset(["nervousness", "confusion"]): 15,
    frozenset(["optimism", "pride"]): 18,
    frozenset(["optimism", "excitement"]): 18,
}

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class EmotionRequest(BaseModel):
    text: str
    threshold: float = 0.3
    top_k: int = 3


class EmotionLabel(BaseModel):
    label_id: int
    label: str
    confidence: float
    source_emotions: List[str]
    method: str


class EmotionResponse(BaseModel):
    emotions: List[EmotionLabel]
    inference_time: float


# ---------------------------------------------------------------------------
# One-shot model downloader
# ---------------------------------------------------------------------------

@app.function(
    image=emotion_image,
    volumes={MODEL_DIR: emotion_volume},
    timeout=1800,
)
def download_model():
    """
    Download ChrisLalk/German-Emotions from HuggingFace to the Modal volume.
    Run once: modal run modal/emotion_worker.py::download_model
    """
    from huggingface_hub import snapshot_download

    if os.path.exists(MODEL_PATH) and os.listdir(MODEL_PATH):
        print(f"Model already present at {MODEL_PATH} — skipping download.")
        return

    os.makedirs(MODEL_PATH, exist_ok=True)
    print(f"Downloading ChrisLalk/German-Emotions to {MODEL_PATH} ...")
    snapshot_download(
        repo_id="ChrisLalk/German-Emotions",
        local_dir=MODEL_PATH,
    )
    emotion_volume.commit()
    print(f"Done. Model saved to {MODEL_PATH}.")


# ---------------------------------------------------------------------------
# Modal service class — pure inference, no database access
# ---------------------------------------------------------------------------

@app.cls(
    gpu="T4",
    image=emotion_image,
    volumes={MODEL_DIR: emotion_volume},
    min_containers=0,
    timeout=300,
)
@modal.concurrent(max_inputs=16)
class EmotionWorker:

    @modal.enter()
    def load_model(self):
        import torch
        from transformers import pipeline

        if not os.path.exists(MODEL_PATH) or not os.listdir(MODEL_PATH):
            raise RuntimeError(
                f"Model not found at {MODEL_PATH}. "
                "Run: modal run modal/emotion_worker.py::download_model"
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading german-emotions from {MODEL_PATH} on {self.device} ...")

        self.pipeline = pipeline(
            "text-classification",
            model=MODEL_PATH,
            tokenizer=MODEL_PATH,
            device=0 if self.device == "cuda" else -1,
            truncation=True,
            max_length=512,
            return_all_scores=True,
            top_k=None,
            use_fast=False,
        )

        logger.info("German-emotions model loaded (27 emotions).")

    def _run_inference(self, text: str, threshold: float, top_k: int) -> list:
        if not text or not text.strip():
            return [{
                "label_id": 19, "label": POLICE_LABELS[19],
                "confidence": 1.0, "source_emotions": ["neutral"], "method": "empty_text",
            }]

        text = text[:512]
        emotion_results = self.pipeline(text)[0]
        emotion_scores = {item["label"]: item["score"] for item in emotion_results}

        significant = {e: s for e, s in emotion_scores.items() if s >= threshold}
        if not significant:
            top = max(emotion_scores.items(), key=lambda x: x[1])
            significant = {top[0]: top[1]}

        results = []
        emotion_set = set(significant.keys())

        for combo, label_id in EMOTION_COMBINATIONS.items():
            if combo.issubset(emotion_set):
                combined_conf = sum(significant[e] for e in combo) / len(combo)
                results.append({
                    "label_id": label_id, "label": POLICE_LABELS[label_id],
                    "confidence": combined_conf, "source_emotions": list(combo),
                    "method": "combination",
                })

        label_scores: dict = {}
        label_sources: dict = {}
        for emotion, score in significant.items():
            if emotion in EMOTION_TO_POLICE:
                label_id = EMOTION_TO_POLICE[emotion]
                if label_id not in label_scores:
                    label_scores[label_id] = score
                    label_sources[label_id] = [emotion]
                else:
                    label_scores[label_id] = max(label_scores[label_id], score)
                    label_sources[label_id].append(emotion)

        for label_id, score in label_scores.items():
            if not any(r["label_id"] == label_id for r in results):
                results.append({
                    "label_id": label_id, "label": POLICE_LABELS[label_id],
                    "confidence": score, "source_emotions": label_sources[label_id],
                    "method": "primary",
                })

        if len(results) >= 3:
            avg_conf = sum(r["confidence"] for r in results) / len(results)
            if avg_conf >= 0.3:
                results.append({
                    "label_id": 20, "label": POLICE_LABELS[20],
                    "confidence": min(avg_conf + 0.1, 0.95),
                    "source_emotions": list(significant.keys()), "method": "ambivalence",
                })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:top_k]

    @modal.fastapi_endpoint(method="POST", docs=True)
    def classify(self, request: EmotionRequest) -> EmotionResponse:
        start = time.time()
        emotions = self._run_inference(request.text, request.threshold, request.top_k)
        inference_time = time.time() - start
        logger.info(f"Classified {len(emotions)} emotions in {inference_time:.2f}s")
        return EmotionResponse(
            emotions=[EmotionLabel(**e) for e in emotions],
            inference_time=inference_time,
        )

    @modal.fastapi_endpoint(method="GET")
    def health(self):
        return {
            "status": "healthy" if hasattr(self, "pipeline") else "loading",
            "model": "german-emotions",
        }
