# backend/app/agents/cypher_examples_store.py
from typing import List, Dict
import logging
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

class CypherExamplesStore:
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
    
    async def _execute_cypher(self, query: str) -> List[Dict]:
        """Execute via MCP"""
        async with sse_client(self.mcp_url, headers={"Host": "localhost"}) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                tools = await session.list_tools()
                exec_tool = next((t for t in tools.tools if "read" in t.name and "cypher" in t.name), None)
                
                if not exec_tool:
                    raise Exception("No cypher execution tool found")
                
                result = await session.call_tool(exec_tool.name, arguments={"query": query})
                
                import json
                try:
                    return json.loads(result.content[0].text)
                except:
                    return []
    
    async def init_vector_index(self):
        """Create vector index (idempotent)"""
        query = """
        CREATE VECTOR INDEX cypherExamples IF NOT EXISTS
        FOR (n:CypherExample)
        ON (n.embedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: 384,
            `vector.similarity_function`: 'cosine'
        }}
        """
        try:
            await self._execute_cypher(query)
            logger.info("✓ Cypher examples index ready")
        except Exception as e:
            logger.warning(f"Vector index setup: {e}")
    
    async def add_example(self, question: str, cypher: str, embedding: List[float]):
        query = """
        MERGE (ex:CypherExample {question: $question})
        SET ex.cypher = $cypher,
            ex.embedding = $embedding,
            ex.updated_at = datetime()
        """
        # MCP doesn't support parameterized queries directly, so we escape
        import json
        safe_cypher = cypher.replace("'", "\\'")
        safe_question = question.replace("'", "\\'")
        embedding_str = json.dumps(embedding)
        
        query_with_params = f"""
        MERGE (ex:CypherExample {{question: '{safe_question}'}})
        SET ex.cypher = '{safe_cypher}',
            ex.embedding = {embedding_str},
            ex.updated_at = datetime()
        """
        
        await self._execute_cypher(query_with_params)
    
    async def get_relevant_examples(self, embedding: List[float], k: int = 5) -> List[Dict]:
        import json
        embedding_str = json.dumps(embedding)
        
        query = f"""
        CALL db.index.vector.queryNodes('cypherExamples', {k}, {embedding_str})
        YIELD node, score
        WHERE score > 0.7
        RETURN node.question as question, 
               node.cypher as cypher,
               score
        ORDER BY score DESC
        """
        
        return await self._execute_cypher(query)