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
    # Default to the path expected in the container, but allow override
    model_path = os.getenv("MODEL_PATH", "/models/llm/codestral-22b-v0.1-q4_k_m.gguf")
    
    logger.info(f"Loading model from {model_path}...")
    try:
        llm = Llama(
            model_path=model_path,
            n_ctx=int(os.getenv("N_CTX", "16384")),
            n_threads=int(os.getenv("N_THREADS", "8")),
            n_batch=512,
            n_gpu_layers=int(os.getenv("N_GPU_LAYERS", "-1")), # Offload all layers to GPU
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
    system_prompt: Optional[str] = None

    class Config:
        populate_by_name = True

class CypherResponse(BaseModel):
    cypher: str
    raw_output: str
    tokens_generated: int
    generation_time: float

SYSTEM_PROMPT = """You are a Graph Query Planner for a Telegram message analysis system.
Your task: Convert natural language questions into a structured JSON plan for Cypher queries.

## CRITICAL REQUIREMENTS

🚨 OUTPUT ONLY VALID JSON - No explanations, no Cypher code, no markdown!
🚨 STRICTLY use only the nodes, properties, and relationships defined in the schema below.
🚨 Every variable in return_fields MUST be defined in nodes.

## Available Schema

**Nodes:**
- Message: mid, owner_id, date, text, language, media_type, media_path, emotions, classifications, location_names
- Channel: channel_id, owner_id, username, title
- User: user_id, owner_id, username, first_name, last_name
- Location: name, owner_id, latitude, longitude, country, mention_count

**Relationships:**
- (Channel)-[:HAS_MESSAGE]->(Message)
- (User)-[:SENT]->(Message)
- (Message)-[:REPLY_TO]->(Message)
- (Message)-[:MENTIONS_LOCATION]->(Location)

## JSON Output Format

{
  "nodes": [{"id": "variable_name", "label": "NodeLabel"}],
  "relationships": [{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}],
  "optional_relationships": [{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}],
  "filters": [{"variable": "var.property", "operator": "CONTAINS|=|IN|>|<", "value": "value"}],
  "return_fields": ["variable1", "variable2"],
  "order_by": "m.date DESC",
  "limit": 50
}

## Operator Rules

- **ARRAY properties (emotions, classifications, location_names)**: Use `IN` operator
  - Example: {"variable": "m.emotions", "operator": "IN", "value": "angry"}
  - NOTE: Cypher syntax is "'value' IN variable", NOT "variable IN ['value']"
  
- **Text search**: Use `CONTAINS` operator (case-insensitive in Neo4j)
  - Example: {"variable": "m.text", "operator": "CONTAINS", "value": "war"}
  
- **Exact match**: Use `=`
  - Example: {"variable": "m.language", "operator": "=", "value": "ru"}

## Examples

**1. Latest messages**
Q: "Show me the latest messages"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**2. Location filter**
Q: "Find messages mentioning Kyiv"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "l", "label": "Location"}],
  "relationships": [{"source": "m", "target": "l", "type": "MENTIONS_LOCATION"}],
  "optional_relationships": [],
  "filters": [{"variable": "l.canonical_name", "operator": "CONTAINS", "value": "Kyiv"}],
  "return_fields": ["m", "l"],
  "order_by": "m.date DESC",
  "limit": 50
}

**3. Emotion filter**
Q: "Show angry messages"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [{"variable": "m.emotions", "operator": "IN", "value": "angry"}],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**4. Text search**
Q: "Messages about war"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [{"variable": "m.text", "operator": "CONTAINS", "value": "war"}],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**5. Language filter**
Q: "Show Russian messages"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [{"variable": "m.language", "operator": "=", "value": "ru"}],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**6. Multiple filters**
Q: "Russian messages about war"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [
    {"variable": "m.language", "operator": "=", "value": "ru"},
    {"variable": "m.text", "operator": "CONTAINS", "value": "war"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**7. Channel filter**
Q: "Messages from channel WarNews"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "ch", "label": "Channel"}],
  "relationships": [{"source": "ch", "target": "m", "type": "HAS_MESSAGE"}],
  "optional_relationships": [],
  "filters": [{"variable": "ch.username", "operator": "CONTAINS", "value": "WarNews"}],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**8. Classification filter**
Q: "Show violent content"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [{"variable": "m.classifications", "operator": "IN", "value": "violence"}],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**9. Visualization**
Q: "Visualize messages and their locations"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "l", "label": "Location"}],
  "relationships": [{"source": "m", "target": "l", "type": "MENTIONS_LOCATION"}],
  "optional_relationships": [],
  "filters": [],
  "return_fields": ["m", "l"],
  "order_by": "m.date DESC",
  "limit": 100
}

**10. User messages**
Q: "Show messages from user JohnDoe"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "u", "label": "User"}],
  "relationships": [{"source": "u", "target": "m", "type": "SENT"}],
  "optional_relationships": [],
  "filters": [{"variable": "u.username", "operator": "CONTAINS", "value": "JohnDoe"}],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**11. Reply threads**
Q: "Show message threads"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "r", "label": "Message"}],
  "relationships": [{"source": "m", "target": "r", "type": "REPLY_TO"}],
  "optional_relationships": [],
  "filters": [],
  "return_fields": ["m", "r"],
  "order_by": "m.date DESC",
  "limit": 50
}

**12. Count aggregation**
Q: "How many messages per channel"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "ch", "label": "Channel"}],
  "relationships": [{"source": "ch", "target": "m", "type": "HAS_MESSAGE"}],
  "optional_relationships": [],
  "filters": [],
  "return_fields": ["ch", "count(m) as message_count"],
  "order_by": "message_count DESC",
  "limit": 20
}

## Forbidden Patterns (会导致 Cypher 错误!)

❌ NEVER use relationship types that don't exist: HAS_EMOTION, HAS_CLASSIFICATION, CONTAINS_LOCATION, POSTED_IN
❌ NEVER use nodes that don't exist: Emotion, Classification (they are PROPERTIES, not nodes!)
❌ NEVER use properties that don't exist on nodes
❌ NEVER use "variable IN ['value']" - Cypher requires "'value' IN variable"
❌ DON'T use OPTIONAL MATCH for required filters (use relationships[] instead)
❌ DON'T create nodes without matching them in relationships first

## Valid Relationship Types (ONLY USE THESE):
- HAS_MESSAGE (Channel -> Message)
- SENT (User -> Message)
- REPLY_TO (Message -> Message)
- MENTIONS_LOCATION (Message -> Location)

## Pre-Response Validation Checklist

Before outputting your JSON, verify:
1. [ ] All relationship types are from the valid list above
2. [ ] All nodes use valid labels: Message, Channel, User, Location
3. [ ] All properties exist on the referenced nodes
4. [ ] Every variable in return_fields is defined in nodes
5. [ ] Array filters use IN operator correctly
6. [ ] JSON is valid (no trailing commas, proper quotes)

Now convert the user's question to JSON:"""

@app.post("/generate-cypher", response_model=CypherResponse)
async def generate_cypher(request: CypherRequest):
    if llm is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    sys_instruction = request.system_prompt if request.system_prompt else SYSTEM_PROMPT

    user_content = f"Schema:\n{request.db_schema}\n\nQuestion: {request.question}\n\nResponse (JSON):"
    
    start = time.time()
    
    try:
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": sys_instruction},
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