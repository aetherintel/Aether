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

SYSTEM_PROMPT = """You are a Neo4j Cypher Expert.
Convert the user's question into a Cypher query based on the provided Schema.

Schema Information:
1. Nodes & Properties:
   - Message {mid, original_text, date}
   - Channel {title, channel_id}
   - Emotion {name}
   - User {username}

2. Relationships (Direction is CRITICAL):
   - (Channel)-[:HAS_MESSAGE]->(Message)
   - (Message)-[:HAS_EMOTION {confidence: float}]->(Emotion)
   - (User)-[:SENT]->(Message)

Format:
1. You may think before answering. Wrap thoughts in <think> tags.
2. Value consistency: If you guess property values, use `CONTAINS`.
3. FINAL OUTPUT must be a markdown code block:
```cypher
MATCH ...
```

Examples:
1. Question: "How many users?"
   Response:
   ```cypher
   MATCH (n:User) RETURN count(n)
   ```

2. Question: "Messages in General?"
   Response:
   <think>User wants messages in channel with title General. Path: Channel -> Message</think>
   ```cypher
   MATCH (c:Channel)-[:HAS_MESSAGE]->(m:Message) WHERE c.title CONTAINS 'General' RETURN m LIMIT 10
   ```

3. Question: "What is the most common emotion?"
   Response:
   <think>Count messages per emotion. Path: Message -> Emotion. Confidence is on relationship.</think>
   ```cypher
   MATCH (m:Message)-[r:HAS_EMOTION]->(e:Emotion) RETURN e.name, count(m) AS freq, avg(r.confidence) as avg_conf ORDER BY freq DESC LIMIT 5
   ```
"""

def clean_cypher(output: str) -> str:
    # 1. Regex extract markdown code block with cypher language
    match = re.search(r'```cypher\s*(.*?)\s*```', output, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 2. Extract generic markdown code block
    match = re.search(r'```\s*(.*?)\s*```', output, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    # 3. Fallback: Remove <think> and return trimmed
    output = re.sub(r'<think>.*?(?:</think>|$)', '', output, flags=re.DOTALL)
    if output.lower().startswith("cypher:"):
        output = output[7:]
    
    return output.strip()

@app.post("/generate-cypher", response_model=CypherResponse)
async def generate_cypher(request: CypherRequest):
    if llm is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    user_content = f"""Schema:
{request.db_schema}

Question: {request.question}

Response:"""

    if request.use_thinking:
        user_content = "/think " + user_content

    start = time.time()
    
    try:
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop=["<|im_end|>"],
        )
        
        generation_time = time.time() - start
        
        raw_output = response["choices"][0]["message"]["content"]
        cypher = clean_cypher(raw_output)
        tokens = response["usage"]["completion_tokens"]

        logger.info(f"Generated Cypher in {generation_time:.2f}s: {cypher[:100]}")
        logger.info(f"Raw Output: {raw_output[:100]}...") 
        
        return CypherResponse(
            cypher=cypher,
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