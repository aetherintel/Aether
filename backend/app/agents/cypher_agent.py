# backend/app/agents/cypher_agent.py
import httpx
from typing import Optional, List, Dict
import logging
import json

logger = logging.getLogger(__name__)

VALID_RELATIONSHIPS = {"HAS_MESSAGE", "SENT", "REPLY_TO", "MENTIONS_LOCATION", "PART_OF", "HAS_EMOTION", "HAS_CLASSIFICATION", "RECOMMENDS"}
VALID_NODES = {"Message", "Channel", "User", "Location", "Emotion", "Classification"}

class CypherAgent:
    def __init__(self, llm_service_url: str = "http://llm-service:8001"):
        self.llm_service_url = llm_service_url
        # Modal token auth (no-op when headers are None — local dev path)
        import os
        modal_key = os.getenv("MODAL_TOKEN_ID")
        modal_secret = os.getenv("MODAL_TOKEN_SECRET")
        headers = {}
        if modal_key and modal_secret:
            headers = {"Modal-Key": modal_key, "Modal-Secret": modal_secret}
        self.client = httpx.AsyncClient(timeout=600.0, headers=headers)
    
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
    
    def _validate_plan(self, plan_str: str, valid_relationships: set = None) -> tuple[bool, str, dict]:
        """
        Validates the generated JSON plan before returning.
        Returns (is_valid, error_message, parsed_plan).
        valid_relationships: if provided, overrides the module-level constant (used when schema is known).
        """
        allowed_rels = valid_relationships if valid_relationships else VALID_RELATIONSHIPS

        try:
            plan = json.loads(plan_str)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}", {}

        if "nodes" not in plan:
            return False, "Missing 'nodes' key in plan", plan
        if "relationships" not in plan:
            return False, "Missing 'relationships' key in plan", plan

        node_ids = {n.get("id") for n in plan.get("nodes", []) if isinstance(n, dict)}

        for rel in plan.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            rel_type = rel.get("type", "")
            if rel_type not in allowed_rels:
                return False, f"Invalid relationship type: {rel_type}. Valid: {allowed_rels}", plan
            if rel.get("source") not in node_ids or rel.get("target") not in node_ids:
                return False, f"Relationship references undefined node: {rel}", plan

        for ret in plan.get("return_fields", []):
            if isinstance(ret, str):
                var = ret.split(".")[0].split("(")[0].strip()
                if var not in node_ids and var.lower() not in ["count", "sum", "avg", "collect", "distinct"]:
                    logger.warning(f"Return field references undefined variable: {ret}")

        return True, "", plan
        
    async def generate_cypher(
        self,
        question: str,
        schema: str,
        use_thinking: bool = False,
        system_prompt_override: Optional[str] = None,
        examples: List[Dict] = []
    ) -> dict:
        examples_text = ""
        if examples:
            lines = ["### Similar successful queries:"]
            for i, ex in enumerate(examples[:3], 1):
                lines.append(f"\n{i}. Q: {ex['question']}")
                lines.append(f"   A: {ex['cypher']}")
            examples_text = "\n".join(lines)

        persona_instruction = ""
        if system_prompt_override:
            persona_instruction = f"\n\n## Persona: {system_prompt_override}"

        system_prompt = f"""Act as an expert Neo4j developer for a Telegram message analysis system.
Convert natural language questions into structured JSON plans for Cypher queries.

## CRITICAL RULES
🚨 OUTPUT ONLY VALID JSON - No explanations, no Cypher code!
🚨 Use ONLY node labels and relationship types defined in the schema below
🚨 Array properties (emotions, classifications, location_names) use IN operator
🚨 Text search uses CONTAINS operator
🚨 Every return_fields variable must be defined in nodes
🚨 Do NOT include owner_id filters — these are injected automatically

## GRAPH-FIRST PRINCIPLE (VERY IMPORTANT)
✅ ALWAYS return full node variables in return_fields (e.g. "u", "c", "m") — NOT properties like "u.username"
✅ This produces a graph visualization. Only return properties (e.g. "count(m)") when the question explicitly asks for counts/statistics.
✅ Example: "who is in which group" → return_fields: ["u", "c"] (full nodes, shows graph)
✅ Example: "how many messages per channel" → return_fields: ["c.username", "count(m)"] (stats, shows table)

## Database Schema (use ONLY these nodes and relationships):
{schema}

## JSON Format:
{{
  "nodes": [{{"id": "variable_name", "label": "NodeLabel"}}],
  "relationships": [{{"source": "var_a", "target": "var_b", "type": "REL_TYPE"}}],
  "optional_relationships": [],
  "filters": [{{"variable": "var.property", "operator": "CONTAINS|=|IN", "value": "value"}}],
  "return_fields": ["u", "c"],
  "order_by": "m.date DESC",
  "limit": 50
}}

{examples_text}
{persona_instruction}

Now convert to JSON:"""

        try:
            response = await self.client.post(
                f"{self.llm_service_url}",
                json={
                    "question": question,
                    "system_prompt": system_prompt,
                    "schema": schema,
                    "temperature": 0.0,
                    "max_tokens": 1024,
                    "use_thinking": use_thinking
                }
            )
            response.raise_for_status()
            
            result = response.json()
            raw_output = result.get("raw_output", "")

            # Extract valid relationship types from the schema text dynamically
            import re
            schema_rels = set(re.findall(r'\[:(\w+)\]', schema))
            valid_rels = schema_rels if schema_rels else VALID_RELATIONSHIPS
            logger.info(f"Schema-derived valid relationships: {valid_rels}")

            is_valid, error_msg, parsed_plan = self._validate_plan(raw_output, valid_rels)

            if not is_valid:
                logger.warning(f"Plan validation failed: {error_msg}. Attempting to extract valid JSON...")
                json_matches = re.findall(r'\{[^{}]*\}', raw_output)
                for match in json_matches:
                    is_valid, error_msg, parsed_plan = self._validate_plan(match, valid_rels)
                    if is_valid:
                        raw_output = match
                        logger.info(f"Successfully extracted valid JSON: {raw_output[:100]}...")
                        break
            
            logger.info(f"Cypher generated in {result['generation_time']:.2f}s")
            
            return {
                "cypher": raw_output,
                "generation_time": result["generation_time"],
                "tokens": result["tokens_generated"],
                "raw_output": raw_output
            }
            
        except httpx.HTTPError as e:
            logger.error(f"LLM service error: {e}")
            raise RuntimeError(f"Failed to generate Cypher: {e}")
    
    async def generate_summary(self, prompt: str) -> str:
        """Reuse für Summarization"""
        try:
            response = await self.client.post(
                f"{self.llm_service_url}",
                json={
                    "question": prompt,
                    "schema": "",
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