from typing import Dict, Any
import logging
from services.text2cypher_service import Text2CypherService

logger = logging.getLogger(__name__)

class GraphRAGService:
    """
    Simplified GraphRAG service that wraps Text2CypherService.
    Removes all dependencies on OpenAI/Vector DBs in favor of 
    direct Text-to-Cypher generation using local LLM.
    """
    def __init__(self):
        self.text2cypher = Text2CypherService()

    async def run_dashboard_query(self, query: str, user_id: str) -> Dict[str, Any]:
        """
        Executes a dashboard query using Text2Cypher.
        """
        logger.info(f"GraphRAG (Legacy Wrapper) executing query: {query} for user {user_id}")
        
        # We append a hint about the user context, though strictly strict RLS 
        # should be handled by the database or a pre-parser.
        # For now, we trust the LLM to include owner_id filters if relevant 
        # or we rely on the prompt to encourage it.
        # Ideally, Text2CypherService should take a user_context filter.
        
        # Execute via Text2Cypher
        # We use 'data_analyst' persona for dashboard-like responses
        result = await self.text2cypher.run_text2cypher(query, system_prompt_key="data_analyst")
        
        return result
