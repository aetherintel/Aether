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
        2. Generate Query Plan (No Session, Long running)
        3. Build & Execute Cypher (Session 2)
        """
        try:
            # 1. Get Schema
            schema_text, schema_dict = await self.get_schema()
            
            # 2. Generate Plan (JSON)
            cypher_result = await self.cypher_agent.generate_cypher(
                question=question,
                schema=schema_text,
                use_thinking=False 
            )
            
            # The "cypher" field now contains the JSON plan string
            plan_str = cypher_result.get("cypher")
            try:
                plan = json.loads(plan_str)
                cypher_query = self._build_cypher_from_plan(plan, schema_dict)
            except json.JSONDecodeError:
                # Fallback if model failed to produce JSON 
                logger.error(f"Failed to parse JSON plan: {plan_str[:100]}...")
                cypher_query = None # Do NOT use raw plan_str as cypher if it looks like JSON

            if not cypher_query:
                 # If we couldn't build a query, check if the raw output happened to be a query (unlikely with JSON mode)
                 # But if the plan_str started with {, it definitely wasn't a query.
                 if plan_str and plan_str.strip().startswith("{"):
                     msg = "LLM failed to generate valid JSON plan (likely repetition loop)."
                     logger.error(msg)
                     return {
                        "summary": msg,
                        "visualization": {"type": "table", "data": []},
                        "cypher": "",
                        "error": msg
                     }
                 cypher_query = cypher_result.get("raw_output", "")
            
            # 3. Execute Query
            logger.info(f"Executing Cypher: {cypher_query}")
            data = await self._execute_query(cypher_query)
            
            # 4. Transform to Graph
            logger.info(f"Raw MCP Result Data (First 2 records): {json.dumps(data[:2], default=str) if isinstance(data, list) else str(data)}")
            graph_data = self._transform_to_graph(data)
            logger.info(f"Transformed Graph Data: {len(graph_data['nodes'])} nodes, {len(graph_data['links'])} links")
            
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
                if any(kw in k.lower() for k in first_row.keys() for kw in ['count', 'sum', 'avg', 'total']):
                    is_tabular = True
            
            # Fallback: If we failed to extract any nodes for the graph, but we have data, show as table
            if not is_tabular and not graph_data["nodes"] and data:
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

    def _build_cypher_from_plan(self, plan: Dict, schema: Dict[str, Any] = None) -> str:
        """
        Deterministically builds valid Cypher from the JSON plan.
        """
        match_clauses = []
        where_clauses = []
        
        # Build set of valid relationship types if schema provided
        valid_rel_types = set()
        if schema:
            for label, details in schema.items():
                if isinstance(details, dict) and details.get("type") == "node":
                     for rel_name in details.get("relationships", {}).keys():
                         valid_rel_types.add(rel_name)
        
        # 1. Nodes
        # Map ids to labels for reference
        node_map = {n['id']: n['label'] for n in plan.get('nodes', [])}
        
        # 2. Relationships (Primary MATCH)
        rels = plan.get('relationships', [])
        used_nodes = set()
        
        for r in rels:
            src = r['source']
            tgt = r['target']
            r_type = r['type']
            
            # SCHEMA VALIDATION & AUTO-CORRECTION
            if schema and r_type not in valid_rel_types:
                # Common hallucinations mapping
                corrections = {
                    "HAS_LOCATION": "MENTIONS_LOCATION",
                    "HAS_USER": "SENT_BY",
                    "HAS_CHANNEL": "POSTED_IN"
                }
                if r_type in corrections:
                    logger.warning(f"Auto-correcting relationship '{r_type}' to '{corrections[r_type]}'")
                    r_type = corrections[r_type]
                else:
                    logger.warning(f"Relationship '{r_type}' not found in schema. Proceeding cautiously.")

            src_label = node_map.get(src, '')
            tgt_label = node_map.get(tgt, '')
            
            # Pattern: (src:Label)-[:TYPE]->(tgt:Label)
            # Handle missing labels gracefully
            src_part = f"({src}:{src_label})" if src_label else f"({src})"
            tgt_part = f"({tgt}:{tgt_label})" if tgt_label else f"({tgt})"
            
            # Heuristic: 0.5B model often refers to the relationship as 'r' in filters
            # If there's only one relationship, alias it as 'r'.
            rel_alias = "r" if len(rels) == 1 else ""
            
            pattern = f"{src_part}-[{rel_alias}:{r_type}]->{tgt_part}"
            match_clauses.append(pattern)
            used_nodes.add(src)
            used_nodes.add(tgt)

        # 3. Orphan Nodes (if any node is not in a relationship)
        for nid, nlabel in node_map.items():
            if nid not in used_nodes:
                 match_clauses.append(f"({nid}:{nlabel})")

        # Combine MATCH
        full_match = f"MATCH {', '.join(match_clauses)}" if match_clauses else ""
        
        # 4. Filters
        valid_ops = {
            "=", "<>", ">", "<", ">=", "<=", "CONTAINS", "STARTS WITH", "ENDS WITH", "IN", "IS NOT NULL", "IS NULL"
        }
        
        for f in plan.get('filters', []):
            prop = f['variable']
            op = f['operator']
            val = f['value']
            
            # SANITIZATION: Skip evident placeholders from weak models
            if "n.prop" in prop or "val" == str(val) or "/" in op:
                 logger.warning(f"Skipping invalid filter placeholder: {prop} {op} {val}")
                 continue
                 
            if op.upper() not in valid_ops:
                 logger.warning(f"Skipping invalid operator: {op}")
                 continue

            # Handle quotes for strings
            if isinstance(val, str) and not val.startswith("'") and not val.startswith('"'):
                val = f"'{val}'"
            
            # Unary operators (ignore value)
            if op.upper() in ["IS NULL", "IS NOT NULL"]:
                where_clauses.append(f"{prop} {op}")
            else:
                where_clauses.append(f"{prop} {op} {val}")
            
        full_where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        # 5. Return
        returns = plan.get('return_fields', [])
        full_return = f"RETURN {', '.join(returns)}" if returns else "RETURN count(*)"
        
        # 6. Order/Limit
        order_by = f"ORDER BY {plan['order_by']}" if plan.get('order_by') else ""
        limit = f"LIMIT {plan['limit']}" if plan.get('limit') is not None else ""
        
        # --- AUTO-RECOVERY FOR UNDEFINED VARIABLES ---
        # 0.5B model sometimes forgets to list nodes but uses variables (e.g. m, c)
        # We scan the generated clauses for variables not in used_nodes/node_map
        known_aliases = {
            "m": "Message",
            "c": "Channel", 
            "u": "User",
            "e": "Emotion",
            "l": "Location",
            "cl": "Classification"
        }
        
        # Check return fields and filters for missing aliases
        potential_vars = set()
        
        for ret in returns:
             # simple extraction heuristic: "count(m)", "m.prop" -> "m"
             # Split by non-alphanumeric
             import re
             parts = re.split(r'[^a-zA-Z0-9_]', ret)
             for p in parts:
                 if p in known_aliases: potential_vars.add(p)
                 
        for f in plan.get('filters', []):
             var_part = f['variable'].split('.')[0]
             if var_part in known_aliases: potential_vars.add(var_part)

        # Retrieve currently defined nodes
        defined_vars = set(node_map.keys())
        
        logger.info(f"Builder Debug - Potential Vars: {potential_vars}, Defined Vars: {defined_vars}, Matches: {match_clauses}")

        # Inject missing nodes
        recovered_matches = []
        for var in potential_vars:
            if var not in defined_vars and var not in used_nodes:
                label = known_aliases[var]
                logger.warning(f"Recovering undefined variable '{var}' as '{label}'")
                recovered_matches.append(f"({var}:{label})")
                
        if recovered_matches:
            if not match_clauses:
                 full_match = f"MATCH {', '.join(recovered_matches)}"
            else:
                 full_match += f", {', '.join(recovered_matches)}"
            logger.info(f"Builder Recovered Match: {full_match}")
        
        # Assemble
        parts = [full_match, full_where, full_return, order_by, limit]
        return " ".join([p for p in parts if p])

    async def get_schema(self) -> str:
        """
        Retrieves the database schema from the MCP server and simplifies it for the LLM.
        """
        async with sse_client(self.mcp_url, headers={"Host": "localhost"}) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                tools = await session.list_tools()
                schema_tool = next((t for t in tools.tools if "schema" in t.name), None)
                
                if not schema_tool:
                    raise Exception("Could not find a schema tool in MCP server.")
                
                schema_result = await session.call_tool(schema_tool.name)
                raw_schema = schema_result.content[0].text
                
                try:
                    schema_json = json.loads(raw_schema)
                    
                    # Simplify Schema
                    lines = ["### Graph Schema"]
                    
                    if "nodes" in schema_json: # Check if it's already in a specific format, but standard Neo4j schema is usually keys=Labels
                        pass
                    
                    # Heuristic for standard Neo4j MCP Schema (Key=Label)
                    # { "User": {"properties": {...}, "relationships": {...}}, ... }
                    
                    lines.append("Nodes:")
                    for label, details in schema_json.items():
                        if not isinstance(details, dict): continue
                        if details.get("type") == "relationship": continue # Skip independent rel defs for now
                        
                        props = list(details.get("properties", {}).keys())
                        lines.append(f"- {label} ({', '.join(props)})")
                        
                    lines.append("\nRelationships:")
                    for label, details in schema_json.items():
                         if not isinstance(details, dict): continue
                         # Node definition often has 'relationships' key
                         if details.get("type") == "node":
                             src_label = label
                             for rel_name, rel_meta in details.get("relationships", {}).items():
                                 direction = rel_meta.get("direction")
                                 target_labels = rel_meta.get("labels", [])
                                 for tgt_label in target_labels:
                                     if direction == "out":
                                         lines.append(f"- (:{src_label})-[:{rel_name}]->(:{tgt_label})")
                    
                    simplified = "\n".join(lines)
                    logger.info(f"Simplified Schema: {simplified}")
                    return simplified, schema_json

                except Exception as e:
                    logger.error(f"Failed to simplify schema: {e}")
                    return raw_schema, {} # Fallback

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
                if n_props:
                    if "name" in n_props:
                        label_text = n_props["name"]
                    elif "title" in n_props:
                        label_text = n_props["title"]
                    elif "text" in n_props:
                        label_text = n_props["text"]
                        if len(label_text) > 20:
                             label_text = label_text[:20] + "..."
                
                # Check directly in props if not found (sometimes props are the node dict itself)
                if label_text == str(n_id) and isinstance(n_props, dict):
                     if "name" in n_props: label_text = n_props["name"]
                     if "title" in n_props: label_text = n_props["title"]

                nodes.append({
                    "id": str(n_id),
                    "label": n_label,
                    "name": label_text,
                    "val": 10,
                    "properties": n_props or {}
                })
                node_ids.add(n_id)

        if isinstance(data, list):
            for record in data:
                # First pass: Collect all potential nodes in this record
                record_nodes = []
                has_explicit_rel = False
                
                for key, value in record.items():
                    if isinstance(value, dict):
                        # 1. Try to detect Standard Node (Neo4j JSON format)
                        n_id = value.get("id") or value.get("identity") or value.get("elementId")
                        n_labels = value.get("labels")
                        
                        if n_id is not None and n_labels is not None:
                             # It's definitely a node in standard format
                             lbl = n_labels[0] if isinstance(n_labels, list) and n_labels else (n_labels if isinstance(n_labels, str) else "Node")
                             add_node(n_id, lbl, value.get("properties", value))
                             record_nodes.append(str(n_id))
                             continue

                        # 2. Try to detect Relationship
                        r_start = value.get("start")
                        r_end = value.get("end")
                        r_type = value.get("type")
                        
                        if r_start is not None and r_end is not None and r_type is not None:
                            s_id = str(r_start)
                            e_id = str(r_end)
                            if s_id not in node_ids: add_node(s_id, "Unknown")
                            if e_id not in node_ids: add_node(e_id, "Unknown")
                            links.append({"source": s_id, "target": e_id, "label": r_type})
                            has_explicit_rel = True
                            continue
                            
                        # 3. Permissive Node Detection (for Map/Dict results like RETURN n)
                        # The value IS the properties. The ID might be inside or we infer it.
                        # Look for common ID fields inside the dict
                        potential_id = value.get("channel_id") or value.get("mid") or value.get("message_id") or value.get("id") or value.get("label_id")
                        
                        if potential_id:
                            # Guess label from key
                            # key = "c" -> Channel? "m" -> Message? "e" -> Emotion?
                            guessed_label = "Node"
                            if key == "c": guessed_label = "Channel"
                            elif key == "m": guessed_label = "Message"
                            elif key == "e": guessed_label = "Emotion"
                            elif key == "a": guessed_label = "Author"
                            elif key == "l": guessed_label = "Location"
                            elif len(key) > 2: guessed_label = key.capitalize()
                            
                            add_node(potential_id, guessed_label, value)
                            record_nodes.append(str(potential_id))
                            continue
                            
                        # If it has specific characteristic keys, treat as node even if ID is weak
                        if "username" in value: # Channel or Author
                             uid = value.get("username")
                             add_node(uid, "Channel" if "channel_id" in value else "User", value)
                             record_nodes.append(str(uid))
                        elif "original_text" in value: # Message
                             # Fallback ID for message if mid missing?
                             mid = value.get("mid") # Should be there
                             if mid: 
                                 add_node(mid, "Message", value)
                                 record_nodes.append(str(mid))
                        elif "name" in value and "label_id" in value: # Emotion
                             lid = value.get("label_id")
                             add_node(lid, "Emotion", value)
                             record_nodes.append(str(lid))

                # Create implicit links
                if len(record_nodes) > 1 and not has_explicit_rel:
                    for i in range(len(record_nodes) - 1):
                        links.append({
                            "source": record_nodes[i],
                            "target": record_nodes[i+1],
                            "label": "RELATED"
                        })

        if not nodes:
             # Minimal info node
             pass
             
        if not nodes and data:
             # If no graph components found but data exists, it's likely tabular.
             # Transform ensures we return *something* for graph view if forced?
             # No, if empty nodes, the controller/service logic sets is_tabular=True
             pass
             
        return {"nodes": nodes, "links": links}
