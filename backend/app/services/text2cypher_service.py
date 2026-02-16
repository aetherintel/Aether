import os
import httpx
import logging
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from agents.cypher_agent import CypherAgent
import json
import redis
import hashlib
import asyncio
from agents.query_templates import QueryTemplates
from agents.static_examples import get_examples

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

        # Redis Cache
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
            logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    async def run_text2cypher(self, question: str, history: List[str] = [], system_prompt_key: str = "default") -> Dict[str, Any]:
        """
        Orchestrates the Text2Cypher flow with separated sessions to avoid timeouts.
        1. Get Schema (Session 1)
        2. Generate Query Plan (No Session, Long running)
        3. Build & Execute Cypher (Session 2)
        4. (Optional) Summarize Results (No Session)
        """
        try:
            # 1. Get Schema
            schema_text, schema_dict = await self.get_schema()
            
            cypher_query = None
            
            # --- PHASE 3: TEMPLATE CHECK ---
            template_plan = QueryTemplates.match(question)
            if template_plan:
                logger.info("⚡ Using Template Plan (Bypassing LLM)")
                cypher_query = self._build_cypher_from_plan(template_plan, schema_dict)
                # Skip to execution
                # But we need to pretend we have a result for the flow?
                # Actually, we can just set plan and skip LLM generation
                plan = template_plan
                # Cache hit on template? No need to cache template results, they are fast.
            else:
                # --- PHASE 2: REDIS CACHE CHECK ---
                cache_key = self._get_cache_key(question, schema_text)
                cached_plan_str = None
                
                if self.redis:
                    try:
                        cached_plan_str = self.redis.get(cache_key)
                        if cached_plan_str:
                            logger.info("🚀 Redis Cache Hit! Using cached plan.")
                    except Exception as e:
                        logger.warning(f"Redis get failed: {e}")

                if cached_plan_str:
                     try:
                         plan = json.loads(cached_plan_str)
                         cypher_query = self._build_cypher_from_plan(plan, schema_dict)
                     except json.JSONDecodeError:
                         logger.warning("Cached plan invalid JSON. Regenerating.")
                         cached_plan_str = None

                if not cached_plan_str:
                    # 2. Generate Plan (LLM)
                    system_prompt_override = None
                    if system_prompt_key and system_prompt_key != "default":
                         # Pass the persona as a hint
                         system_prompt_override = f"Persona: {system_prompt_key}. "
                         if system_prompt_key in ["storyteller", "data_analyst"]:
                             system_prompt_override += "Focus on extracting data properties (text, names, dates) AND related node names (e.g. Emotion.name, Location.name) that allow for rich narrative summarization."
        
                    # Get few-shot examples
                    examples = get_examples(question)
                    if examples:
                        logger.info(f"Injecting {len(examples)} examples into prompt")

                    plan_str = None
                    try:
                        cypher_result = await asyncio.wait_for(
                            self.cypher_agent.generate_cypher(
                                question=question,
                                schema=schema_text,
                                use_thinking=False,
                                system_prompt_override=system_prompt_override,
                                examples=examples
                            ),
                            timeout=120.0
                        )
                    except asyncio.TimeoutError:
                        logger.error("LLM Generation Timed Out (45s). Using fallback.")
                        # FALLBACK: Use "Latest messages" template
                        plan = QueryTemplates.match("latest messages")
                        cypher_query = self._build_cypher_from_plan(plan, schema_dict)
                        # Do NOT cache fallback as the specific question result
                        cypher_result = {} # To avoid unpacking error below if referenced
                        plan_str = None
                    except Exception as e:
                         logger.error(f"LLM Generation Failed: {e}")
                         cypher_result = {}
                         plan_str = None
                    
                    if not plan_str and 'cypher_result' in locals() and cypher_result:
                        # The "cypher" field now contains the JSON plan string
                        plan_str = cypher_result.get("cypher")
                        try:
                            plan = json.loads(plan_str)
                            cypher_query = self._build_cypher_from_plan(plan, schema_dict)
                            
                            # Disable Caching as per user request
                            # if self.redis and cypher_query:
                            #     try:
                            #         self.redis.setex(cache_key, 3600, plan_str)
                            #         logger.info("💾 Plan cached in Redis (TTL 1h)")
                            #     except Exception as e:
                            #         logger.warning(f"Redis set failed: {e}")
                                    
                        except json.JSONDecodeError:
                            # Fallback if model failed to produce JSON 
                            logger.error(f"Failed to parse JSON plan: {plan_str[:100]}...")
                            cypher_query = None

            # ROBUSTNESS: Check if plan has 'query' key (Text2Cypher format) instead of 'nodes'
            if isinstance(plan, dict) and 'nodes' not in plan and 'query' in plan:
                 logger.warning("LLM returned 'query' format instead of Graph Plan. Attempting to extraction.")
                 # Does query have cypher directly?
                 # e.g. {"query": "MATCH ..."} or {"query": {"match_pattern": ...}}
                 q_val = plan.get('query')
                 if isinstance(q_val, str) and "MATCH" in q_val.upper():
                      cypher_query = q_val
                      logger.info(f"Extracted Cypher from 'query' key: {cypher_query}")
                 elif isinstance(q_val, dict) and 'match_pattern' in q_val:
                      # Reconstruct from match_pattern / where_clause / return_clause
                      mp = q_val.get('match_pattern', '')
                      wc = q_val.get('where_clause', '')
                      rc = q_val.get('return_clause', '')
                      cypher_query = f"MATCH {mp} {wc} RETURN {rc} LIMIT 50"
                      logger.info(f"Reconstructed Cypher from structured query: {cypher_query}")
            

 

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
                 # If plan_str was not JSON and not a valid query, cypher_query remains None, leading to error below.
                 # cypher_query = cypher_result.get("raw_output", "") # Removed as per instruction

            if not cypher_query:
                raise ValueError("Failed to generate a valid Cypher query from the plan.")
            
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

            # Heuristic: If there are NO relationships (links), a table is usually better than disconnected nodes
            if not graph_data["links"]:
                is_tabular = True
            
            if is_tabular:
                viz_type = "table"
                viz_data = data # Send raw list of dicts for table

                # Enhanced Visualization: Check for Pie/Bar candidates
                if data and isinstance(data, list) and len(data) > 0:
                    first_row = data[0]
                    keys = list(first_row.keys())
                    
                    # Candidate: 2 columns, one is number, one is string
                    if len(keys) == 1 and isinstance(first_row[keys[0]], (int, float)):
                        # Single value -> KPI Card
                        viz_type = "kpi"
                    
                    elif len(keys) == 2:
                        val1 = first_row[keys[0]]
                        val2 = first_row[keys[1]]
                        
                        col1_num = isinstance(val1, (int, float))
                        col2_num = isinstance(val2, (int, float))
                        
                        # One numeric, one categorical
                        if col1_num != col2_num:
                             # Pie for small number of categories
                             if len(data) <= 10:
                                 viz_type = "pie"
                             else:
                                 viz_type = "bar"
            
            
            # 6. Generate Summary (if needed)
            summary_text = f"**Generated Cypher:**\n`{cypher_query}`"
            
            # If specifically asked to summarize OR using a persona that implies it
            if system_prompt_key != "default" or "summarize" in question.lower():
                 try:
                     generated_summary = await self._summarize_data(question, data, system_prompt_key)
                     summary_text = f"{generated_summary}\n\n" + summary_text
                 except Exception as sum_err:
                     logger.error(f"Summarization failed: {sum_err}")

            return {
                "summary": summary_text, 
                "visualization": {
                    "type": viz_type,
                    "data": viz_data
                },
                "cypher": cypher_query,
                "question": question
            }

        except Exception as e:
            import traceback
            logger.error(f"Text2Cypher Orchestration Failed: {e}")
            logger.error(traceback.format_exc())
            return {
                "summary": f"Error: {str(e)}",
                "visualization": {
                    "type": "table",
                    "data": []
                },
                "cypher": "",
                "error": str(e)
            }

    async def _summarize_data(self, question: str, data: Any, persona: str) -> str:
        """
        Uses the LLM to summarize the data based on the persona.
        """
        # Truncate data if too large
        data_str = json.dumps(data, indent=2, default=str)
        if len(data_str) > 10000:
             data_str = data_str[:10000] + "... (truncated)"
             
        prompt = f"""
        Act as a {persona}.
        User Question: {question}
        
        Data Retrieved:
        {data_str}
        
        Provide a concise, engaging summary of this data. Do not mention "Cypher" or technical details. 
        Focus on answering the question directly using the data provided.

        OUTPUT FORMAT:
        You MUST return a JSON object with a "summary" key and a "cypher" key set to "SKIP".
        Example:
        {{
            "cypher": "SKIP",
            "summary": "Your natural language summary here."
        }}
        """
        
        # We reuse the CypherAgent's client/infrastructure but for a text task.
        # Ideally we'd have a separate TextAgent, but for now we cheat and use the same endpoint with a different instruction.
        # However, generate_cypher enforces JSON output. We might need a raw completion endpoint or just use generate_cypher with a text-only prompt and ignore the code.
        
        # Actually, let's use the simplest approach: A specialized method in CypherAgent to do generic chat completition?
        # Or just use the existing one and ask for a JSON with a "summary" field.
        
        # Let's add a helper to CypherAgent for this.
        return await self.cypher_agent.generate_summary(prompt)

    def _sanitize_id(self, raw_id: str) -> str:
        """Sanitizes strings to be valid Cypher identifiers."""
        import re
        # Remove non-alphanumeric chars (keep underscores)
        safe = re.sub(r'[^a-zA-Z0-9_]', '_', raw_id)
        # Ensure it doesn't start with a number
        if safe and safe[0].isdigit():
             safe = "v_" + safe
        return safe

    def _get_cache_key(self, question: str, schema_text: str) -> str:
        """Generates a stable cache key."""
        # Normalize question
        q = question.strip().lower()
        # Hash schema (it changes rarely, but good to incl)
        s_hash = hashlib.md5(schema_text.encode()).hexdigest()
        q_hash = hashlib.md5(q.encode()).hexdigest()
        return f"cypher_plan:{q_hash}:{s_hash}"

    def _build_cypher_from_plan(self, plan: Dict, schema: Dict[str, Any] = None) -> str:
        """
        Deterministically builds valid Cypher from the JSON plan.
        """
        if not isinstance(plan, dict):
            logger.error(f"Plan is not a dict: {type(plan)} - {plan}")
            return ""

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
        # 1. Nodes
        # Map ids to labels for reference
        node_map = {}
        original_to_safe = {}
        for n in plan.get('nodes', []):
             if not isinstance(n, dict):
                 logger.warning(f"Skipping malformed node entry (expected dict, got {type(n)}): {n}")
                 continue
             
             raw = n.get('id')
             if not raw: continue
             
             safe = self._sanitize_id(raw)
             original_to_safe[raw] = safe
             node_map[safe] = n.get('label', 'Node')
        
        # 2. Relationships (Primary MATCH)
        rels = plan.get('relationships', [])
        used_nodes = set()
        
        for r in rels:
            if not isinstance(r, dict):
                 logger.warning(f"Skipping malformed rel entry: {r}")
                 continue
                 
            src_raw = r.get('source')
            tgt_raw = r.get('target')
            if not src_raw or not tgt_raw: continue
            
            src = self._sanitize_id(src_raw)
            tgt = self._sanitize_id(tgt_raw)
            # Correction: if strict matching needed, check original_to_safe, but often models hallucinate new IDs here too.
            # Best to just sanitize what we get.
            r_type = r['type']
            
            # SCHEMA VALIDATION & AUTO-CORRECTION
            if schema and r_type not in valid_rel_types:
                # Common hallucinations mapping
                corrections = {
                    "HAS_LOCATION": "MENTIONS_LOCATION",
                    "HAS_USER": "SENT_BY",
                    "HAS_CHANNEL": "POSTED_IN",
                    "LOCATION": "MENTIONS_LOCATION"
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
            used_nodes.add(tgt)
            
        # --- ASSEMBLE QUERY PARTS ---
        # Correct Pattern: MATCH (a)-[:R]->(b) OPTIONAL MATCH (a)-[:R2]->(c)
        # We must NOT join them with commas.

        parts = []
        
        # 1. Primary Filters (MATCH) - These are strict requirements
        if match_clauses:
            parts.append(f"MATCH {', '.join(match_clauses)}")

        # 2. Optional Relationships (OPTIONAL MATCH)
        for rel in plan.get('optional_relationships', []):
            if not isinstance(rel, dict): continue
            
            src_raw = rel.get('source')
            tgt_raw = rel.get('target')
            if not src_raw or not tgt_raw: continue
            
            src = self._sanitize_id(src_raw)
            tgt = self._sanitize_id(tgt_raw)
            r_type = rel.get('type')
            
            # SCHEMA CORRECTION (Also for optional)
            if schema and r_type not in valid_rel_types:
                corrections = {
                    "HAS_LOCATION": "MENTIONS_LOCATION",
                    "HAS_USER": "SENT_BY",
                    "HAS_CHANNEL": "POSTED_IN",
                    "LOCATION": "MENTIONS_LOCATION"
                }
                if r_type in corrections:
                     r_type = corrections[r_type]

            src_label = node_map.get(src, '')
            tgt_label = node_map.get(tgt, '')
            
            src_part = f"({src}:{src_label})" if src_label else f"({src})"
            tgt_part = f"({tgt}:{tgt_label})" if tgt_label else f"({tgt})"
            
            parts.append(f"OPTIONAL MATCH {src_part}-[:{r_type}]->{tgt_part}")
            used_nodes.add(src)
            used_nodes.add(tgt)

        # 3. Orphan Nodes (if any node is not in a relationship)
        # If no relationships at all, we must match the nodes
        # BUT: If we have match_clauses (relationships), we don't need to match nodes again unless they are disconnected
        # The logic below matches ANY node not used in match_clauses.
        orphan_parts = []
        for nid, nlabel in node_map.items():
            if nid not in used_nodes:
                 orphan_parts.append(f"({nid}:{nlabel})")
        
        if orphan_parts:
            # If we already have a MATCH, we can append to it with comma IF valid
            # But orphan nodes are usually just MATCH (n)
            # Safe to add as a separate MATCH clause if parts exist, or inside the first MATCH?
            # MATCH (a)-->(b), (c) IS VALID.
            # So if parts[0] starts with MATCH, we can append?
            # Or just add a new MATCH line.
            if parts and parts[0].startswith("MATCH"):
                 parts[0] += f", {', '.join(orphan_parts)}"
            else:
                 parts.insert(0, f"MATCH {', '.join(orphan_parts)}")

        full_match = " ".join(parts)
        
        # 4. Filters
        valid_ops = {
            "=", "<>", ">", "<", ">=", "<=", "CONTAINS", "STARTS WITH", "ENDS WITH", "IN", "IS NOT NULL", "IS NULL"
        }

        for f in plan.get('filters', []):
            if not isinstance(f, dict): continue

            prop = f.get('variable')
            # Fix deprecated lower() syntax which breaks Neo4j v5+
            if prop and 'lower(' in prop:
                 prop = prop.replace('lower(', 'toLower(')

            op = f.get('operator')
            val = f.get('value')

            if not prop or not op: continue

            # SANITIZATION: Skip evident placeholders from weak models
            if "n.prop" in prop or "val" == str(val) or "/" in op:
                 logger.warning(f"Skipping invalid filter placeholder: {prop} {op} {val}")
                 continue

            if op.upper() not in valid_ops:
                 logger.warning(f"Skipping invalid operator: {op}")
                 continue

            # AUTO-FIX: Correct common variable mistakes
            # If filter uses undefined variable, try to map to defined ones
            if '.' in prop:
                var_name = prop.split('.')[0]
                prop_name = prop.split('.', 1)[1]

                # If variable not defined, try to find correct one
                if var_name not in node_map and var_name not in used_nodes:
                    # Common mistakes: 'n' instead of 'm', 'c' instead of 'ch', etc.
                    corrections = {
                        'n': 'm',  # Generic node → Message
                        'node': 'm',
                        'msg': 'm',
                        'message': 'm'
                    }

                    if var_name in corrections:
                        corrected_var = corrections[var_name]
                        if corrected_var in node_map or corrected_var in used_nodes:
                            logger.warning(f"Auto-correcting filter variable '{var_name}' → '{corrected_var}'")
                            prop = f"{corrected_var}.{prop_name}"
                    else:
                        # If still undefined, try to infer from property name
                        # e.g., "location_names" → likely Message node
                        if prop_name in ['text', 'language', 'emotions', 'classifications', 'location_names', 'date']:
                            if 'm' in node_map or 'm' in used_nodes:
                                logger.warning(f"Auto-correcting undefined variable '{var_name}' → 'm' based on property '{prop_name}'")
                                prop = f"m.{prop_name}"

            # Handle quotes for strings
            if isinstance(val, str) and not val.startswith("'") and not val.startswith('"'):
                # Check if it looks like a list or number or boolean
                if val.startswith('[') and val.endswith(']'):
                    pass # It's a list string
                elif val.lower() in ['true', 'false', 'null']:
                    pass
                elif val.replace('.', '', 1).isdigit():
                    pass
                else:
                    val = f"'{val}'"
            
            # Handle list objects (if parsed from JSON as list)
            if isinstance(val, list):
                val = str(val) # Convert ['a'] to "['a']" for Cypher

            # Special handling for IN operator with arrays
            # LLM might generate: "m.emotions IN ['angry']"
            # But Cypher wants: "'angry' IN m.emotions"
            if op.upper() == "IN":
                # Check if value is already a list
                if isinstance(f.get('value'), list):
                    # LLM sent: {"variable": "m.emotions", "operator": "IN", "value": ["angry"]}
                    # This is backwards! Should be: "'angry' IN m.emotions"
                    # Swap them
                    logger.warning(f"Reversing IN operator: {val} IN {prop} → {val[0] if len(eval(val))==1 else val} IN {prop}")
                    # For single value in list, extract it
                    val_list = f.get('value')
                    if len(val_list) == 1:
                        val = f"'{val_list[0]}'"
                        where_clauses.append(f"{val} IN {prop}")
                    else:
                        # Multiple values: convert to OR
                        for v in val_list:
                            where_clauses.append(f"'{v}' IN {prop}")
                    continue
                elif val.startswith('[') and val.endswith(']'):
                    # LLM sent: {"variable": "m.emotions", "operator": "IN", "value": "['angry']"}
                    # Also backwards - swap
                    logger.warning(f"Reversing IN operator with array syntax: {prop} IN {val}")
                    # Parse the array
                    import ast
                    try:
                        val_list = ast.literal_eval(val)
                        if len(val_list) == 1:
                            where_clauses.append(f"'{val_list[0]}' IN {prop}")
                        else:
                            for v in val_list:
                                where_clauses.append(f"'{v}' IN {prop}")
                    except:
                        # Fallback: just reverse as-is
                        where_clauses.append(f"{val} IN {prop}")
                    continue

            # Unary operators (ignore value)
            if op.upper() in ["IS NULL", "IS NOT NULL"]:
                where_clauses.append(f"{prop} {op}")
            else:
                where_clauses.append(f"{prop} {op} {val}")
            
        full_where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
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
        
        for ret in plan.get('return_fields', []):
             if not isinstance(ret, str): continue
             # simple extraction heuristic: "count(m)", "m.prop" -> "m"
             # Split by non-alphanumeric
             import re
             parts_re = re.split(r'[^a-zA-Z0-9_]', ret)
             for p in parts_re:
                 if p in known_aliases: potential_vars.add(p)
                 
        for f in plan.get('filters', []):
             if not isinstance(f, dict): continue
             var_part = f.get('variable', '').split('.')[0]
             if var_part in known_aliases: potential_vars.add(var_part)

        # Retrieve currently defined nodes
        defined_vars = set(node_map.keys())
        
        logger.info(f"Builder Debug - Potential Vars: {potential_vars}, Defined Vars: {defined_vars}")

        # Inject missing nodes if they weren't matched above
        recovered_matches = []
        for var in potential_vars:
            if var not in defined_vars and var not in used_nodes:
                label = known_aliases[var]
                logger.warning(f"Recovering undefined variable '{var}' as '{label}'")
                recovered_matches.append(f"({var}:{label})")
                defined_vars.add(var) # Add to defined vars for validation later
                
        if recovered_matches:
            # If we already have a MATCH, can we append?
            # MATCH ..., (new) IS VALID.
            # But if we have OPTIONAL MATCH at the end, checks break.
            # Safer to prepend a new MATCH clause or append to the first MATCH if possible.
            # Simplified: Just add a new MATCH clause at the start? No, variables must be bound?
            # Actually, `MATCH (m:Message)` is independent.
            
            # If full_match is empty, just make it the match
            if not full_match:
                 full_match = f"MATCH {', '.join(recovered_matches)}"
            else:
                 # Check if full_match starts with MATCH
                 if full_match.startswith("MATCH"):
                     # We can append to the first MATCH clause? 
                     # Only if no OPTIONAL MATCH follows immediately with comma...
                     # But we built full_match as "MATCH ... OPTIONAL MATCH ..."
                     # So we can't easily inject into the string.
                     
                     # Just prepend a separate MATCH?
                     # MATCH (m:Message) MATCH ...
                     # Valid in Cypher.
                     full_match = f"MATCH {', '.join(recovered_matches)} {full_match}"
                 else:
                     # e.g. starts with OPTIONAL MATCH (unlikely if match_clauses was empty)
                     full_match = f"MATCH {', '.join(recovered_matches)} {full_match}"
            
            logger.info(f"Builder Recovered Match: {full_match}")

        # 5. Return (Moved after recovery to encompass recovered vars)
        returns = plan.get('return_fields', [])
        valid_returns = []
        available_vars = defined_vars | used_nodes 
        
        import re
        for ret in returns:
            match = re.match(r'^([a-zA-Z0-9_]+)', ret.strip())
            if match:
                var = match.group(1)
                # Allow functions, known vars, or if "n" is used but not defined (maybe we want to alias one?? No, drop it)
                if var in available_vars or var.lower() in ["count", "sum", "avg", "min", "max", "collect", "distinct"]:
                     valid_returns.append(ret)
                else:
                     logger.warning(f"Dropping return field with undefined variable: {ret}")
            else:
                 valid_returns.append(ret)

        if not valid_returns:
            if available_vars:
                valid_returns = list(available_vars)
            else:
                valid_returns = ["count(*)"]

        full_return = f"RETURN {', '.join(valid_returns)}"

        # 6. Order/Limit
        # Ensure we don't duplicate keywords if the model put them in the string
        
        # 6. Order/Limit
        # Ensure we don't duplicate keywords if the model put them in the string
        
        order_by_val = plan.get('order_by')
        limit_val = plan.get('limit')
        
        order_by_clause = ""
        if order_by_val:
            order_by_str = str(order_by_val).strip()
            
            # FIX 1: Strip trailing "LIMIT <n>" from order_by if present
            # The LLM often puts "LIMIT 100" inside order_by
            import re
            
            # AGGRESSIVE SANITIZATION: Truncate at any major Cypher keyword implies leakage
            # We use a regex that matches the keyword surrounded by whitespace or at boundaries
            leak_keywords = ["MATCH", "WHERE", "RETURN", "WITH", "OPTIONAL", "UNION", "UNWIND", "LIMIT"]
            
            for kw in leak_keywords:
                # Regex: (\s|^)KEYWORD(\s|$) to ensure we don't match substrings like 'unlimited' (contains limit)
                # But for 'MATCH', 'WHERE', etc, they are reserved words.
                # We want to catch "recommends MATCH" or "recommends\nMATCH"
                pattern = re.compile(r'(\s+|^)' + kw + r'(\s+|$)', re.IGNORECASE)
                match = pattern.search(order_by_str)
                if match:
                    logger.warning(f"Sanitizing order_by: Truncated at '{match.group(0)}' in '{order_by_str}'")
                    # We cut at the start of the match (which includes the leading whitespace)
                    order_by_str = order_by_str[:match.start()].strip()
            
            # Additional cleanup: if order_by contains parentheses (function calls ok, but pattern matching NOT)
            # e.g. "recommends (u)" -> suspicious if not a known function
            # But "date(m.created)" is valid. "m.grade > 5" is valid (boolean sort).
            # "MATCH (n)" has parens.
            # If we stripped keywords, hopefully we are fine.
            
            # FIX 2: "ORDER BY Label.prop" -> "ORDER BY var.prop"
            # e.g. "Message.date" -> "m.date"
            # We look for CapitalizedWord.Property
            label_prop_match = re.match(r'^([A-Z][a-zA-Z0-9_]*)\.([a-zA-Z0-9_]+)', order_by_str)
            if label_prop_match:
                label = label_prop_match.group(1)
                prop = label_prop_match.group(2)
                
                # Try to find variable for this label
                found_var = None
                for var, l in node_map.items():
                    if l == label:
                        found_var = var
                        break
                
                # If not in node_map, check if we can infer from used_nodes (heuristic)
                
                if found_var:
                     # Replace the Label part with Var
                     order_by_str = f"{found_var}.{prop}{order_by_str[len(label)+1+len(prop):]}"
                     logger.warning(f"Auto-corrected ORDER BY Label: {label}.{prop} -> {found_var}.{prop}")
            
            # AUTO-CORRECT: "ORDER BY date" -> "ORDER BY m.date" if valid (Generic fallback)
            if "date" in order_by_str and "." not in order_by_str:
                 # Find main variable
                 main_var = "m" if "m" in node_map or "m" in used_nodes else list(node_map.keys())[0] if node_map else "n"
                 order_by_str = order_by_str.replace("date", f"{main_var}.date")
                 logger.warning(f"Auto-corrected ORDER BY: {order_by_val} -> {order_by_str}")

            if order_by_str and order_by_str.upper().startswith("ORDER BY"):
                order_by_clause = order_by_str
            elif order_by_str:
                order_by_clause = f"ORDER BY {order_by_str}"
            else:
                order_by_clause = "" # Empty if we stripped everything

        limit_clause = ""
        if limit_val is not None:
             limit_str = str(limit_val).strip()
             # If model output "LIMIT 50", don't add "LIMIT" again
             if limit_str.upper().startswith("LIMIT"):
                 limit_clause = limit_str
             else:
                 limit_clause = f"LIMIT {limit_str}"

        # Assemble
        parts_final = [full_match, full_where, full_return, order_by_clause, limit_clause]
        return " ".join([p for p in parts_final if p])

    async def get_schema(self) -> str:
        """
        Retrieves the database schema from the MCP server and simplifies it for the LLM.

        IMPORTANT: Filters out legacy complex properties to only show simplified schema.
        """

        # Define simplified property whitelist for each node type
        SIMPLIFIED_PROPERTIES = {
            "Message": ["mid", "owner_id", "date", "text", "language", "media_type", "media_path",
                       "emotions", "classifications", "location_names"],
            "Channel": ["channel_id", "owner_id", "username", "title"],
            "User": ["user_id", "owner_id", "username", "first_name", "last_name"],
            "Location": ["canonical_name", "owner_id", "latitude", "longitude", "country", "mention_count"],
            "Emotion": ["name", "score"],  
            "Classification": ["label", "confidence"]
        }

        # Relationships to hide (deprecated)
        HIDDEN_RELATIONSHIPS = []

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

                    # Simplify Schema - FILTER OUT OLD PROPERTIES
                    lines = ["### Graph Schema"]

                    lines.append("Nodes:")
                    for label, details in schema_json.items():
                        if not isinstance(details, dict): continue
                        if details.get("type") == "relationship": continue

                        # Skip deprecated nodes
                        if label in ["Emotion", "Classification"]:
                            logger.info(f"Hiding deprecated node: {label}")
                            continue

                        # Filter properties based on whitelist
                        all_props = list(details.get("properties", {}).keys())
                        if label in SIMPLIFIED_PROPERTIES:
                            # Use whitelist
                            filtered_props = [p for p in all_props if p in SIMPLIFIED_PROPERTIES[label]]
                            logger.info(f"{label}: Filtered {len(all_props)} → {len(filtered_props)} properties")
                        else:
                            # Unknown node type, keep all properties
                            filtered_props = all_props

                        if filtered_props:
                            lines.append(f"- {label} ({', '.join(filtered_props)})")

                    lines.append("\nRelationships:")
                    for label, details in schema_json.items():
                         if not isinstance(details, dict): continue
                         if details.get("type") == "node":
                             src_label = label

                             # Skip relationships from deprecated nodes
                             if src_label in ["Emotion", "Classification"]:
                                 continue

                             for rel_name, rel_meta in details.get("relationships", {}).items():
                                 # Skip deprecated relationships
                                 if rel_name in HIDDEN_RELATIONSHIPS:
                                     logger.info(f"Hiding deprecated relationship: {rel_name}")
                                     continue

                                 direction = rel_meta.get("direction")
                                 target_labels = rel_meta.get("labels", [])
                                 for tgt_label in target_labels:
                                     # Skip relationships to deprecated nodes
                                     if tgt_label in ["Emotion", "Classification"]:
                                         continue

                                     if direction == "out":
                                         lines.append(f"- (:{src_label})-[:{rel_name}]->(:{tgt_label})")

                    simplified = "\n".join(lines)
                    logger.info(f"\n{'='*60}")
                    logger.info("SIMPLIFIED SCHEMA FOR LLM:")
                    logger.info(f"{'='*60}")
                    logger.info(simplified)
                    logger.info(f"{'='*60}\n")
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
            logger.info(f"Transforming data (list of {len(data)} items)")
            for i, record in enumerate(data):
                if not isinstance(record, dict):
                     logger.warning(f"Record {i} is not a dict: {type(record)} - {record}")
                     continue
                
                # First pass: Collect all potential nodes in this record
                record_nodes = []
                has_explicit_rel = False
                
                for key, value in record.items():
                    if isinstance(value, dict):
                        # 1. Try to detect Standard Node (Neo4j JSON format)
                        # Switch to LEGACY IDs (Integers) to ensure consistency with Relationship start/end,
                        # which often lack elementId references in some driver versions/MCP setups.
                        n_id = value.get("id") or value.get("identity")
                        # Fallback to elementId only if legacy ID matches nothing
                        if n_id is None: n_id = value.get("elementId")

                        n_labels = value.get("labels")
                        
                        if n_id is not None and n_labels is not None:
                             # It's definitely a node in standard format
                             lbl = n_labels[0] if isinstance(n_labels, list) and n_labels else (n_labels if isinstance(n_labels, str) else "Node")
                             add_node(n_id, lbl, value.get("properties", value))
                             record_nodes.append(str(n_id))
                             continue

                        # 2. Try to detect Relationship
                        # Always use 'start' and 'end' (Legacy Integers) as primary keys
                        r_start = value.get("start")
                        if r_start is None: r_start = value.get("startNodeElementId")
                        
                        r_end = value.get("end")
                        if r_end is None: r_end = value.get("endNodeElementId")
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
                # If we have multiple nodes in a row but no explicit relationship object,
                # we assume they are connected (e.g. Message -> Location)
                if len(record_nodes) > 1 and not has_explicit_rel:
                    # Connect the first node to all others? Or chain them?
                    # Usually the first node is the 'center' (Message).
                    center_node = record_nodes[0]
                    for other_node in record_nodes[1:]:
                        links.append({
                            "source": center_node,
                            "target": other_node,
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
