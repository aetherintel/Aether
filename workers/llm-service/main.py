# workers/llm-service/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from llama_cpp import Llama
import os
from typing import Optional
import logging
import time
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Qwen3-0.6B Cypher Service")

llm = None

@app.on_event("startup")
async def load_model():
    global llm
    model_path = os.getenv("MODEL_PATH", "/models/llm/qwen3-0.6b-q4.gguf")
    
    logger.info(f"Loading model from {model_path}...")
    try:
        llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=int(os.getenv("N_THREADS", "8")),
            n_batch=512,
            verbose=False,
            # chat_format="chatml" # Removed to allow auto-detection (Llama 3 needs different format)
        )
        logger.info("Model loaded successfully")
    except Exception as e:
         logger.error(f"Failed to load model: {e}")

class CypherRequest(BaseModel):
    question: str
    db_schema: str = Field(..., alias="schema")
    temperature: float = 0.0
    max_tokens: int = 1024
    use_thinking: bool = False

    class Config:
        populate_by_name = True

class CypherResponse(BaseModel):
    cypher: str
    raw_output: str
    tokens_generated: int
    generation_time: float

SYSTEM_PROMPT = """You are a Graph Query Planner.
Your task is to map the user's question to a structured JSON plan for a Cypher query.
DO NOT write Cypher code. Output ONLY valid JSON matching the schema below.

### CRITICAL RULES
1. **NO HALLUCINATIONS**: Use ONLY Nodes and Relationships from the provided schema.
2. **Properties vs Nodes**: If a user asks for "Language", "Country", or "Date", these are usually **PROPERTIES** of a Message/Channel, NOT nodes. 
   - CORRECT: `{"nodes": [{"id": "m", "label": "Message"}], "return_fields": ["m.original_language", "count(m)"]}`
   - WRONG: `{"nodes": [{"id": "l", "label": "Language"}]}` (Language node does not exist)
3. **DEFINE ALL VARIABLES**: If you use 'm' in return_fields, you MUST define it in "nodes".
   - WRONG: `{"nodes": [], "return_fields": ["count(m)"]}`
   - CORRECT: `{"nodes": [{"id": "m", "label": "Message"}], "return_fields": ["count(m)"]}`
4. **NO PLACEHOLDERS**: Never use `/`, `n.prop`, or `val`. Use ACTUAL properties from schema.
   - WRONG: `{"variable": "n.prop", "operator": "CONTAINS/=", "value": "val"}`
   - CORRECT: `{"variable": "m.original_text", "operator": "CONTAINS", "value": "berlin"}`

### JSON Output Schema
{
  "nodes": [{"id": "var_name", "label": "NodeLabel"}],
  "relationships": [{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}],
  "filters": [{"variable": "var.prop", "operator": "CONTAINS/=/</>", "value": "value"}],
  "return_fields": ["var.prop", "count(var)"],
  "order_by": "count(var) DESC", 
  "limit": null
}

### Examples
1. "How many messages?"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "filters": [],
  "return_fields": ["count(m)"],
  "order_by": null,
  "limit": null
}

2. "Most common emotions?" (Emotion IS a Node)
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "e", "label": "Emotion"}],
  "relationships": [{"source": "m", "target": "e", "type": "HAS_EMOTION"}],
  "filters": [],
  "return_fields": ["e.name", "count(m)"],
  "order_by": "count(m) DESC",
  "limit": 5
}

3. "Most common language?" (Language is a PROPERTY)
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "filters": [],
  "return_fields": ["m.original_language", "count(m)"],
  "order_by": "count(m) DESC",
  "limit": 5
}
"""

@app.post("/generate-cypher", response_model=CypherResponse)
async def generate_cypher(request: CypherRequest):
    if llm is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    user_content = f"""Schema:
{request.db_schema}

Question: {request.question}

Response (JSON):"""

    start = time.time()
    
    try:
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_format={"type": "json_object"}, # Enforce JSON output
            stop=["<|im_end|>"],
            repeat_penalty=1.2 # Prevent repetition loops for small models
        )
        
        generation_time = time.time() - start
        
        raw_output = response["choices"][0]["message"]["content"]
        tokens = response["usage"]["completion_tokens"]

        logger.info(f"Generated Plan in {generation_time:.2f}s: {raw_output[:100]}")
        
        return CypherResponse(
            cypher=raw_output, # Return JSON plan as "cypher" for now, agent will parse it
            raw_output=raw_output,
            tokens_generated=tokens,
            generation_time=generation_time
        )
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {
        "status": "healthy" if llm is not None else "loading",
        "model": "Qwen3-0.6B-Instruct-Q4_K_M"
    }