import os
import httpx
import logging
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from agents.cypher_agent import CypherAgent
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Text2CypherService:
    def __init__(self):
        # MCP Server Config
        self.mcp_url = os.getenv("MCP_NEO4J_URL", "http://mcp-neo4j-cypher-server:8000/api/mcp/")
        
        # Local LLM Agent
        self.llm_service_url = os.getenv("LLM_SERVICE_URL", "http://aether-llm-service:8001")
        self.cypher_agent = CypherAgent(llm_service_url=self.llm_service_url)

    async def run_text2cypher(self, question: str, history: List[str] = []) -> Dict[str, Any]:
        """
        Orchestrates the Text2Cypher flow with separated sessions to avoid timeouts.
        1. Get Schema (Session 1)
        2. Generate Cypher (No Session, Long running)
        3. Execute Cypher (Session 2)
        """
        try:
            # 1. Get Schema
            schema_text = await self.get_schema()
            
            # 2. Generate Cypher
            cypher_result = await self.cypher_agent.generate_cypher(
                question=question,
                schema=schema_text,
                use_thinking=False 
            )
            cypher_query = cypher_result.get("cypher")
            if not cypher_query:
                 cypher_query = cypher_result.get("raw_output", "")
            
            # 3. Execute Query
            logger.info(f"Executing Cypher: {cypher_query}")
            data = await self._execute_query(cypher_query)
            
            # 4. Transform to Graph
            graph_data = self._transform_to_graph(data)
            
            # 5. Determine visualization type
            # If graph has no nodes (or just 1 info node) or data is flat tabular, prefer table
            viz_type = "graph"
            viz_data = graph_data
            
            # Heuristic: If we converted it to just "Result" nodes or "Info" nodes, it's likely tabular
            is_tabular = False
            
            # Check if all nodes are "Result" or "Info"
            if graph_data["nodes"] and all(n.get("label") in ["Result", "Info", "Unknown"] for n in graph_data["nodes"]):
                is_tabular = True
            
            # If explicit "count" or "sum" in keys, it's tabular
            if data and isinstance(data, list) and len(data) > 0:
                first_row = data[0]
                # If keys contain 'count', 'sum', 'avg', or doesn't look like graph components
                if any(k.lower() in ['count', 'sum', 'avg', 'total'] for k in first_row.keys()):
                    is_tabular = True
            
            if is_tabular:
                viz_type = "table"
                viz_data = data # Send raw list of dicts for table
            
            
            # Format Text Summary
            try:
                data_str = json.dumps(data, indent=2)
            except:
                data_str = str(data)
            
            if len(data_str) > 2000:
                data_str = data_str[:2000] + "... (truncated)"

            return {
                "summary": f"**Generated Cypher:**\n`{cypher_query}`", 
                # Removed appended JSON from summary since we have Table now
                # Or keep it? User said "text box as a ugly json :D". Table is better.
                # I'll keep summary concise now.
                "visualization": {
                    "type": viz_type,
                    "data": viz_data
                },
                "cypher": cypher_query,
                "question": question
            }

        except Exception as e:
            logger.error(f"Text2Cypher Orchestration Failed: {e}")
            return {
                "summary": f"Error: {str(e)}",
                "visualization": {
                    "type": "table",
                    "data": []
                },
                "cypher": "",
                "error": str(e)
            }

    async def get_schema(self) -> str:
        """
        Retrieves the database schema from the MCP server.
        """
        async with sse_client(self.mcp_url, headers={"Host": "localhost"}) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                tools = await session.list_tools()
                schema_tool = next((t for t in tools.tools if "schema" in t.name), None)
                
                if not schema_tool:
                    raise Exception("Could not find a schema tool in MCP server.")
                
                schema_result = await session.call_tool(schema_tool.name)
                return schema_result.content[0].text

    async def _execute_query(self, cypher_query: str) -> List[Dict]:
        """
        Executes the Cypher query via MCP in a separate session.
        """
        async with sse_client(self.mcp_url, headers={"Host": "localhost"}) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                tools = await session.list_tools()
                # Look for execution tool, usually 'read-cypher' or 'cypher-read'
                exec_tool = next((t for t in tools.tools if "read" in t.name and "cypher" in t.name), None)
                if not exec_tool:
                     # Fallback check
                     exec_tool = next((t for t in tools.tools if "execute" in t.name), None)
                
                if not exec_tool:
                     raise Exception("Could not find a cypher execution tool in MCP server.")

                execution_result = await session.call_tool(exec_tool.name, arguments={"query": cypher_query})
                results_text = execution_result.content[0].text
                
                # Try to parse as JSON
                try:
                    data = json.loads(results_text)
                    return data
                except json.JSONDecodeError:
                    # Return as wrapped text object
                    return [{"result": results_text}]

    def _transform_to_graph(self, data: List[Dict]) -> Dict[str, List]:
        nodes = []
        links = []
        node_ids = set()

        def add_node(n_id, n_label, n_props=None):
            if n_id not in node_ids:
                label_text = str(n_id)
                if n_props and "name" in n_props:
                    label_text = n_props["name"]
                elif n_props and "title" in n_props:
                    label_text = n_props["title"]
                
                nodes.append({
                    "id": str(n_id),
                    "label": n_label,
                    "name": label_text,
                    "val": 10 
                })
                node_ids.add(n_id)

        if isinstance(data, list):
            for record in data:
                for key, value in record.items():
                    if isinstance(value, dict):
                        if "labels" in value and "id" in value: 
                            add_node(value["id"], value["labels"][0] if value["labels"] else "Node", value.get("properties"))
                        elif "start" in value and "end" in value and "type" in value:
                            s_id = str(value["start"])
                            e_id = str(value["end"])
                            add_node(s_id, "Unknown")
                            add_node(e_id, "Unknown")
                            links.append({
                                "source": s_id,
                                "target": e_id,
                                "label": value["type"]
                            })
                    elif isinstance(value, (str, int)) and "id" in key.lower():
                         add_node(value, "Result")

        if not nodes:
             nodes.append({"id": "info", "label": "Info", "name": "No Graph Elements Found", "val": 1})
             
        return {"nodes": nodes, "links": links}
