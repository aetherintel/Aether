# backend/app/agents/cypher_agent.py
import httpx
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

class CypherAgent:
    def __init__(self, llm_service_url: str = "http://llm-service:8001"):
        self.llm_service_url = llm_service_url
        self.client = httpx.AsyncClient(timeout=600.0)
    
    async def _embed_text(self, text: str) -> List[float]:
        """Lokales Embedding vom LLM Service"""
        try:
            response = await self.client.post(
                f"{self.llm_service_url}/embed",
                json={"text": text}
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []
    
    async def generate_cypher(
        self,
        question: str,
        schema: str,
        use_thinking: bool = False,
        system_prompt_override: Optional[str] = None,
        examples: List[Dict] = []  # NEU: Examples direkt übergeben
    ) -> dict:
        # Examples formatieren
        examples_text = ""
        if examples:
            lines = ["### Similar successful queries:"]
            for i, ex in enumerate(examples[:3], 1):
                lines.append(f"\n{i}. Q: {ex['question']}")
                lines.append(f"   A: {ex['cypher']}")
            examples_text = "\n".join(lines)
        
        system_prompt = f"""Act as an expert Neo4j developer.
You are a Graph Query Planner for a Telegram message analysis system.
Your task is to convert natural language questions into a structured JSON plan for Cypher queries.

OUTPUT ONLY VALID JSON. NO explanations, NO Cypher code, ONLY JSON.

### JSON Output Format

{{
  "nodes": [{{"id": "variable_name", "label": "NodeLabel"}}],
  "relationships": [{{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}}],
  "optional_relationships": [{{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}}],
  "filters": [{{"variable": "var.property", "operator": "CONTAINS|=|IN|>|<", "value": "value"}}],
  "return_fields": ["variable1", "variable2"],
  "order_by": "m.date DESC",
  "limit": 50
}}

{examples_text}

Instructions:
1. Act as an expert Neo4j developer.
2. Fuzzy Match: Use toLower(n.prop) CONTAINS toLower('val') for strings.
3. Visualization: If asked to "visualize" or "show connections", RETURN the nodes and relationships (e.g. MATCH (c:Channel)-[r:POSTED]->(m:Message) RETURN c, r, m).
4. Freedom: Use the schema to infer relationships. Do NOT be afraid to traverse multiple hops (e.g. Channel -> Message -> Location).
5. Schema: Use ONLY provided Node Labels and Relationship Types.
6. Location Names: The property is 'canonical_name' (e.g. l.canonical_name).
{f'7. custom_instruction: {system_prompt_override}' if system_prompt_override else ''}"""

        try:
            response = await self.client.post(
                f"{self.llm_service_url}/generate-cypher",
                json={
                    "question": question, # Send just the question
                    "system_prompt": system_prompt, # Send instructions as system prompt
                    "schema": schema,
                    "temperature": 0.0,
                    "max_tokens": 1024,
                    "use_thinking": use_thinking
                }
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Cypher generated in {result['generation_time']:.2f}s")
            
            return {
                "cypher": result["cypher"],
                "generation_time": result["generation_time"],
                "tokens": result["tokens_generated"],
                "raw_output": result["raw_output"]
            }
            
        except httpx.HTTPError as e:
            logger.error(f"LLM service error: {e}")
            raise RuntimeError(f"Failed to generate Cypher: {e}")
    
    async def generate_summary(self, prompt: str) -> str:
        """Reuse für Summarization"""
        try:
            response = await self.client.post(
                f"{self.llm_service_url}/generate-cypher",
                json={
                    "question": prompt,
                    "db_schema": "",
                    "temperature": 0.7,
                    "max_tokens": 1024,
                    "use_thinking": False
                }
            )
            response.raise_for_status()
            result = response.json()
            
            import json
            try:
                parsed = json.loads(result.get("raw_output", ""))
                if isinstance(parsed, dict) and "summary" in parsed:
                    return parsed["summary"]
            except:
                pass
            
            return result.get("raw_output", "No summary generated.")
        except Exception as e:
            logger.error(f"Summary failed: {e}")
            return f"Error: {e}"
    
    async def close(self):
        await self.client.aclose()