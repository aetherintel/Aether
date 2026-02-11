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
    model_path = os.getenv("MODEL_PATH", "/models/llm/Phi-3.5-mini-instruct-Q6_K.gguf")
    
    logger.info(f"Loading model from {model_path}...")
    try:
        llm = Llama(
            model_path=model_path,
            n_ctx=int(os.getenv("N_CTX", "16384")),
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

SYSTEM_PROMPT = """You are a Graph Query Planner for a Telegram message analysis system.
Your task is to convert natural language questions into a structured JSON plan for Cypher queries.

OUTPUT ONLY VALID JSON. NO explanations, NO Cypher code, ONLY JSON.

### CRITICAL RULES

1. **ALWAYS ADD FILTERS**: If user mentions a specific value (location, emotion, word), add it to filters!
   - "messages mentioning Kyiv" → filter by location_names
   - "angry messages" → filter by emotions
   - "messages about war" → filter by text containing 'war'
   - "Russian messages" → filter by language = 'ru'

2. **ARRAY PROPERTIES - Use IN operator**:
   - For emotions: Add filter with `m.emotions` and operator `IN` and value `emotion_name`
   - For classifications: Add filter with `m.classifications` and operator `IN` and value `classification_name`
   - For location_names: Add filter with `m.location_names` and operator `IN` and value `location_name`

3. **TEXT SEARCH - Use CONTAINS operator**:
   - For searching text: Add filter with `m.text` and operator `CONTAINS` and the search term
   - Always case-insensitive

4. **DEFINE ALL VARIABLES**: Every variable in return_fields MUST appear in nodes.

5. **REQUIRED vs OPTIONAL MATCH**:
   - Use relationships[] for FILTERING (messages WITH something)
   - Use optional_relationships[] for ENRICHMENT (show if exists, but don't filter)

6. **DEFAULT ORDERING**: Always order by `m.date DESC` unless user asks otherwise.

7. **DEFAULT LIMIT**: Use limit 50 for lists, limit 100 for visualizations.

### Available Schema

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

### JSON Output Format

{
  "nodes": [{"id": "variable_name", "label": "NodeLabel"}],
  "relationships": [{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}],
  "optional_relationships": [{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}],
  "filters": [{"variable": "var.property", "operator": "CONTAINS|=|IN|>|<", "value": "value"}],
  "return_fields": ["variable1", "variable2"],
  "order_by": "m.date DESC",
  "limit": 50
}

### Examples

**Example 1: Latest messages**
Question: "Show me the latest messages"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**Example 2: Location filter (ARRAY)**
Question: "Find messages mentioning Kyiv"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [
    {"variable": "m.location_names", "operator": "IN", "value": "Kyiv"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**Example 3: Emotion filter (ARRAY)**
Question: "Show angry messages"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [
    {"variable": "m.emotions", "operator": "IN", "value": "angry"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**Example 4: Text search**
Question: "Messages about war"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [
    {"variable": "m.text", "operator": "CONTAINS", "value": "war"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**Example 5: Language filter**
Question: "Show Russian messages"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [
    {"variable": "m.language", "operator": "=", "value": "ru"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**Example 6: Multiple filters**
Question: "Russian messages about war"
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

**Example 7: Channel filter (RELATIONSHIP)**
Question: "Messages from channel WarNews"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "ch", "label": "Channel"}],
  "relationships": [
    {"source": "ch", "target": "m", "type": "HAS_MESSAGE"}
  ],
  "optional_relationships": [],
  "filters": [
    {"variable": "ch.username", "operator": "CONTAINS", "value": "WarNews"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**Example 8: Violent content with classification (ARRAY)**
Question: "Show violent content"
{
  "nodes": [{"id": "m", "label": "Message"}],
  "relationships": [],
  "optional_relationships": [],
  "filters": [
    {"variable": "m.classifications", "operator": "IN", "value": "violence"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

**Example 9: Visualization with locations (RELATIONSHIP)**
Question: "Visualize messages and their locations"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "l", "label": "Location"}],
  "relationships": [
    {"source": "m", "target": "l", "type": "MENTIONS_LOCATION"}
  ],
  "optional_relationships": [],
  "filters": [],
  "return_fields": ["m", "l"],
  "order_by": "m.date DESC",
  "limit": 100
}

**Example 10: User messages**
Question: "Show messages from user JohnDoe"
{
  "nodes": [{"id": "m", "label": "Message"}, {"id": "u", "label": "User"}],
  "relationships": [
    {"source": "u", "target": "m", "type": "SENT"}
  ],
  "optional_relationships": [],
  "filters": [
    {"variable": "u.username", "operator": "CONTAINS", "value": "JohnDoe"}
  ],
  "return_fields": ["m"],
  "order_by": "m.date DESC",
  "limit": 50
}

### Common Mistakes to Avoid

❌ DON'T use nodes that don't exist (Emotion, Classification)
❌ DON'T use relationships that don't exist (HAS_EMOTION, HAS_CLASSIFICATION)
❌ DON'T forget filters when user mentions a specific value
❌ DON'T use OPTIONAL MATCH for filtering (use relationships[] instead)
❌ DON'T forget to add both nodes if you use a relationship
❌ DON'T use properties that don't exist (check schema above!)

✅ DO use IN operator for array properties (emotions, classifications, location_names)
✅ DO use CONTAINS for text search
✅ DO add filters for any specific values mentioned
✅ DO include "m" in nodes if you use it in return_fields
✅ DO use proper operators: =, CONTAINS, IN, >, <

### Final Checklist Before Responding

1. Does my JSON include filters for values the user mentioned?
2. Are all variables in return_fields also in nodes?
3. Am I using IN operator for array properties?
4. Am I using CONTAINS for text search?
5. Is my JSON valid (no trailing commas, proper quotes)?

Now convert the user's question to JSON following the examples above.
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