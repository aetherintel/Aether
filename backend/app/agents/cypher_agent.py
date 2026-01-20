# backend/app/agents/cypher_agent.py
import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class CypherAgent:
    """Agent der LLM Service für Text-to-Cypher nutzt"""
    
    def __init__(self, llm_service_url: str = "http://llm-service:8001"):
        self.llm_service_url = llm_service_url
        self.client = httpx.AsyncClient(timeout=600.0) # Increased to 10m for larger models (Phi-3.5) on CPU
    
    async def generate_cypher(
        self,
        question: str,
        schema: str,
        use_thinking: bool = False
    ) -> dict:
        try:
            # Note: llm-service expects "db_schema" but aliases "schema"
            # We use 1024 tokens to allow for thinking blocks
            response = await self.client.post(
                f"{self.llm_service_url}/generate-cypher",
                json={
                    "question": question,
                    "db_schema": schema, 
                    "temperature": 0.0,
                    "max_tokens": 1024,
                    "use_thinking": use_thinking
                }
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                f"Cypher generated in {result['generation_time']:.2f}s "
                f"({result['tokens_generated']} tokens)"
            )
            
            return {
                "cypher": result["cypher"],
                "generation_time": result["generation_time"],
                "tokens": result["tokens_generated"],
                "raw_output": result["raw_output"]
            }
            
        except httpx.HTTPError as e:
            logger.error(f"LLM service error: {e}")
            raise RuntimeError(f"Failed to generate Cypher: {e}")
    
    async def validate_and_execute(
        self,
        cypher: str,
        neo4j_driver
    ) -> dict:
        with neo4j_driver.session() as session:
            try:
                # Validation logic would go here
                
                # Execution
                # Use EXPLAIN to verify checks? Optional.
                
                result = session.run(cypher)
                records = [record.data() for record in result]
                
                return {
                    "success": True,
                    "records": records,
                    "count": len(records)
                }
                
            except Exception as e:
                logger.error(f"Cypher execution failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "cypher": cypher
                }
    
    async def close(self):
        await self.client.aclose()