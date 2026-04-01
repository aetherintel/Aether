# modal/llm_service.py
# =============================================================================
# Aether LLM Service — Modal deployment
# =============================================================================
# Deploys the Cypher-plan LLM (Codestral 22B Q4) as a persistent Modal web
# endpoint. Model weights are stored in a Modal Volume so they survive cold
# starts without re-downloading.
#
# Setup (one-time):
#   pip install modal
#   modal setup               # authenticate
#   modal run modal/llm_service.py::download_model   # seed the volume
#   modal deploy modal/llm_service.py                # deploy endpoint
#
# The stable URL is printed after deploy. Set it as LLM_SERVICE_URL in the
# backend environment.
# =============================================================================

import os
import time
import logging
from typing import Optional

import modal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modal primitives
# ---------------------------------------------------------------------------

app = modal.App("aether-llm-service")

# Persistent volume — model is downloaded once, survives container restarts
llm_volume = modal.Volume.from_name("aether-llm-models", create_if_missing=True)

MODEL_DIR = "/models/llm"
MODEL_FILENAME = "Codestral-22B-v0.1-Q4_K_M.gguf"
MODEL_PATH = f"{MODEL_DIR}/{MODEL_FILENAME}"

# HuggingFace repo/file for Codestral 22B Q4_K_M
HF_REPO = "bartowski/Codestral-22B-v0.1-GGUF"
HF_FILE = MODEL_FILENAME

# Image: CUDA runtime + llama-cpp-python CUDA wheels + FastAPI
llm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.2.2-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install("libgomp1")
    .pip_install(
        "llama-cpp-python",
        extra_index_url="https://abetlen.github.io/llama-cpp-python/whl/cu122",
        pre=False,
    )
    .pip_install("fastapi", "uvicorn[standard]", "pydantic>=2", "huggingface_hub")
)


# ---------------------------------------------------------------------------
# One-shot model downloader (run manually once to seed the volume)
# ---------------------------------------------------------------------------

@app.function(
    image=llm_image,
    volumes={MODEL_DIR: llm_volume},
    timeout=3600,
)
def download_model():
    """
    Download Codestral 22B Q4 GGUF to the Modal volume.
    Run once: modal run modal/llm_service.py::download_model
    """
    from huggingface_hub import hf_hub_download

    if os.path.exists(MODEL_PATH):
        size_gb = os.path.getsize(MODEL_PATH) / 1e9
        print(f"Model already present at {MODEL_PATH} ({size_gb:.1f} GB) — skipping download.")
        return

    print(f"Downloading {HF_REPO}/{HF_FILE} to {MODEL_DIR} ...")
    hf_hub_download(
        repo_id=HF_REPO,
        filename=HF_FILE,
        local_dir=MODEL_DIR,
    )
    llm_volume.commit()
    size_gb = os.path.getsize(MODEL_PATH) / 1e9
    print(f"Done. Model saved ({size_gb:.1f} GB).")


# ---------------------------------------------------------------------------
# Request / Response schemas (identical to workers/llm-service/main.py)
# ---------------------------------------------------------------------------

class CypherRequest(BaseModel):
    question: str
    db_schema: str = Field(..., alias="schema")
    temperature: float = 0.0
    max_tokens: int = 1024
    use_thinking: bool = False
    system_prompt: Optional[str] = None

    class Config:
        populate_by_name = True


class CypherResponse(BaseModel):
    cypher: str
    raw_output: str
    tokens_generated: int
    generation_time: float


# ---------------------------------------------------------------------------
# Default system prompt (identical to workers/llm-service/main.py)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Graph Query Planner for a Telegram message analysis system.
Your task: Convert natural language questions into a structured JSON plan for Cypher queries.

## CRITICAL REQUIREMENTS

OUTPUT ONLY VALID JSON - No explanations, no Cypher code, no markdown!
STRICTLY use only the nodes, properties, and relationships defined in the schema below.
Every variable in return_fields MUST be defined in nodes.
NEVER use Python syntax like datetime.now() — use Cypher datetime() function.
NEVER use aggregate functions (count, sum) inside WHERE clauses.
Emotions and classifications are NODES connected by relationships, NOT array properties on Message.

## Available Schema

Nodes:
- Message: mid, owner_id, date, original_text, translated_text, language, media_type, media_path
- Channel: channel_id, owner_id, username, title
- User: user_id, owner_id, username, first_name, last_name
- Location: canonical_name, owner_id, latitude, longitude, country, mention_count
- Emotion: name, label_id
- Classification: label, label_id

Relationships:
- (Channel)-[:HAS_MESSAGE]->(Message)
- (User)-[:SENT]->(Message)
- (Message)-[:REPLY_TO]->(Message)
- (Message)-[:MENTIONS_LOCATION]->(Location)
- (Message)-[:HAS_EMOTION]->(Emotion)
- (Message)-[:HAS_CLASSIFICATION]->(Classification)

## JSON Output Format

{
  "nodes": [{"id": "variable_name", "label": "NodeLabel"}],
  "relationships": [{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}],
  "optional_relationships": [],
  "filters": [{"variable": "var.property", "operator": "CONTAINS|=|>|<", "value": "value"}],
  "return_fields": ["variable1", "variable2"],
  "order_by": "m.date DESC",
  "limit": 50
}

## Query Pattern Rules

Emotion filter: use relationship to Emotion node, filter on e.name CONTAINS 'Wut'
  nodes: [m:Message, e:Emotion], relationships: [{m->e, HAS_EMOTION}], filters: [{e.name, CONTAINS, Wut}]

Classification filter: use relationship to Classification node, filter on toLower(cl.name) CONTAINS 'gewalt'
  nodes: [m:Message, cl:Classification], relationships: [{m->cl, HAS_CLASSIFICATION}]

Date filter: use Cypher datetime() — example for last 30 days: {"variable": "m.date", "operator": ">=", "value": "datetime() - duration({days: 30})"}

Keyword search: search BOTH m.original_text and m.translated_text with CONTAINS

Known emotion labels (use CONTAINS for partial match):
Hass / Feindbild, Wut / Aggression, Angst / Bedrohungsempfinden,
Verzweiflung / Hoffnungslosigkeit, Misstrauen / Paranoia,
Neutral / Informationsorientiert, Ambivalent / Gemischt,
Euphorie / Begeisterung, Mobilisierende Hoffnung,
Stolz / Selbstermaechtigung, Solidaritaet / Zusammenhalt

Now convert the user's question to JSON:"""


# ---------------------------------------------------------------------------
# Modal service class
# ---------------------------------------------------------------------------

@app.cls(
    gpu="L40S",                                   # 48GB VRAM — fits Codestral 22B Q4 (~13GB)
    image=llm_image,
    volumes={MODEL_DIR: llm_volume},
    min_containers=0,                              # scale to zero when idle — set to 1 only in production
    timeout=600,
)
@modal.concurrent(max_inputs=4)
class LLMService:

    @modal.enter()
    def load_model(self):
        from llama_cpp import Llama

        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(
                f"Model not found at {MODEL_PATH}. "
                "Run: modal run modal/llm_service.py::download_model"
            )

        logger.info(f"Loading model from {MODEL_PATH} ...")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=int(os.getenv("N_CTX", "16384")),
            n_threads=int(os.getenv("N_THREADS", "8")),
            n_batch=512,
            n_gpu_layers=int(os.getenv("N_GPU_LAYERS", "-1")),
            verbose=False,
        )
        logger.info("Model loaded successfully.")

    @modal.fastapi_endpoint(method="POST", docs=True)
    async def generate_cypher(self, request: CypherRequest) -> CypherResponse:
        sys_instruction = request.system_prompt or SYSTEM_PROMPT
        user_content = (
            f"Schema:\n{request.db_schema}\n\n"
            f"Question: {request.question}\n\n"
            f"Response (JSON):"
        )

        start = time.time()
        try:
            response = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": sys_instruction},
                    {"role": "user", "content": user_content},
                ],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format={"type": "json_object"},
                stop=["<|im_end|>"],
                repeat_penalty=1.2,
            )
        except Exception as e:
            from fastapi import HTTPException
            logger.error(f"Generation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        generation_time = time.time() - start
        raw_output = response["choices"][0]["message"]["content"]
        tokens = response["usage"]["completion_tokens"]

        logger.info(f"Generated plan in {generation_time:.2f}s: {raw_output[:80]}")

        return CypherResponse(
            cypher=raw_output,
            raw_output=raw_output,
            tokens_generated=tokens,
            generation_time=generation_time,
        )

    @modal.fastapi_endpoint(method="GET")
    async def health(self):
        return {
            "status": "healthy" if hasattr(self, "llm") else "loading",
            "model": MODEL_FILENAME,
        }
