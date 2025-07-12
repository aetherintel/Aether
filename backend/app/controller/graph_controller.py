# Add this to your FastAPI backend
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from neo4j import AsyncGraphDatabase
import json
import os

router = APIRouter(prefix="/graph", tags=["graph"])

driver = AsyncGraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD"))
)


class CypherQuery(BaseModel):
    query: str
    parameters: Optional[Dict[str, Any]] = {}

class GraphVisualizationRequest(BaseModel):
    channel_ids: Optional[List[str]] = None
    search_query: Optional[str] = None
    user: Optional[str] = None
    type: Optional[str] = None
    limit: Optional[int] = 100
    visualization_type: str = "network"  # network, timeline, etc.

@router.post("/execute")
async def execute_cypher_query(query_request: CypherQuery):
    """
    Execute a Cypher query and return results for neovis.js
    This endpoint acts as a secure proxy to Neo4j
    """
    try:
        async with driver.session() as session:
            result = await session.run(query_request.query, query_request.parameters)
            
            # Convert Neo4j result to neovis.js compatible format
            records = []
            async for record in result:
                # Convert record to dictionary
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    # Handle Neo4j types that need serialization
                    if hasattr(value, '__dict__'):
                        record_dict[key] = dict(value)
                    else:
                        record_dict[key] = value
                records.append(record_dict)
            
            return {
                "records": records,
                "summary": {
                    "query": query_request.query,
                    "parameters": query_request.parameters
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

@router.post("/visualization")
async def get_visualization_data(viz_request: GraphVisualizationRequest):
    """
    Get pre-built visualization data for common use cases
    """
    try:
        if viz_request.visualization_type == "network":
            return await get_network_visualization(viz_request)
        else:
            raise HTTPException(status_code=400, detail="Unsupported visualization type")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visualization failed: {str(e)}")

async def get_network_visualization(viz_request: GraphVisualizationRequest):
    """Generate network visualization data for user or channel types"""
    async with driver.session() as session:
        type_mode = viz_request.type
        params = {"limit": viz_request.limit}

        nodes = []
        relationships = []
        node_ids = set()

        if type_mode == "user" and viz_request.user:
            params["username"] = viz_request.user

            query = """
            MATCH (u:User {username: $username})-[:SENT]->(m:Message)
            RETURN u, m
            LIMIT $limit
            """
            result = await session.run(query, params)

            async for record in result:
                user = record["u"]
                message = record["m"]

                user_id = f"u_{user.id}"
                message_id = f"m_{message.id}"

                if user_id not in node_ids:
                    nodes.append({
                        "id": user_id,
                        "label": user.get("username") or "Unknown User",
                        "type": "User",
                        "properties": dict(user)
                    })
                    node_ids.add(user_id)

                if message_id not in node_ids:
                    nodes.append({
                        "id": message_id,
                        "label": message.get("text", "")[:30] + "...",
                        "type": "Message",
                        "properties": dict(message)
                    })
                    node_ids.add(message_id)

                relationships.append({
                    "id": f"{user_id}_created_{message_id}",
                    "from": user_id,
                    "to": message_id,
                    "type": "CREATED",
                    "properties": {}
                })

        elif type_mode == "channel" and viz_request.user:
            params["channel_ids"] = [viz_request.user]

            query = """
            MATCH (c1:Channel)-[r:RECOMMENDS]->(c2:Channel)
            WHERE c1.channel_id IN $channel_ids
            RETURN c1, c2, r
            LIMIT $limit
            """
            result = await session.run(query, params)

            async for record in result:
                c1 = record["c1"]
                c2 = record["c2"]
                r = record["r"]

                c1_id = f"ch_{c1['channel_id']}"
                c2_id = f"ch_{c2['channel_id']}"

                if c1_id not in node_ids:
                    nodes.append({
                        "id": c1_id,
                        "label": c1.get("username") or c1.get("title") or "Channel",
                        "type": "Channel",
                        "properties": dict(c1)
                    })
                    node_ids.add(c1_id)

                if c2_id not in node_ids:
                    nodes.append({
                        "id": c2_id,
                        "label": c2.get("username") or c2.get("title") or "Channel",
                        "type": "Channel",
                        "properties": dict(c2)
                    })
                    node_ids.add(c2_id)

                relationships.append({
                    "id": f"{c1_id}_recommends_{c2_id}",
                    "from": c1_id,
                    "to": c2_id,
                    "type": "RECOMMENDS",
                    "properties": dict(r)
                })

        else:
            return {
                "nodes": [],
                "relationships": [],
                "summary": {
                    "node_count": 0,
                    "relationship_count": 0,
                    "error": "Invalid or missing 'type', 'user', or 'channel_ids'."
                }
            }

        return {
            "nodes": nodes,
            "relationships": relationships,
            "summary": {
                "node_count": len(nodes),
                "relationship_count": len(relationships)
            }
        }

# Add allowed queries for security (whitelist approach)
ALLOWED_QUERIES = {
    "channel_network": """
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)<-[:SENT]-(u:User)
        WHERE ch.channel_id IN $channel_ids
        RETURN ch, u, count(m) as message_count
        LIMIT $limit
    """,
    "user_interactions": """
        MATCH (u1:User)-[:SENT]->(m1:Message)-[:REPLY_TO]->(m2:Message)<-[:SENT]-(u2:User)
        WHERE m1.date >= $start_date AND m1.date <= $end_date
        RETURN u1, u2, count(*) as interaction_count
        LIMIT $limit
    """,
    "message_flow": """
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)
        WHERE ch.channel_id IN $channel_ids AND m.date >= $start_date
        RETURN m.date, count(m) as message_count
        ORDER BY m.date
    """
}

@router.post("/predefined/{query_name}")
async def execute_predefined_query(query_name: str, parameters: Dict[str, Any]):
    """
    Execute a predefined, safe query
    This provides additional security by limiting what queries can be executed
    """
    if query_name not in ALLOWED_QUERIES:
        raise HTTPException(status_code=400, detail="Query not allowed")
    
    try:
        async with driver.session() as session:
            result = await session.run(ALLOWED_QUERIES[query_name], parameters)
            
            records = []
            async for record in result:
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    if hasattr(value, '__dict__'):
                        record_dict[key] = dict(value)
                    else:
                        record_dict[key] = value
                records.append(record_dict)
            
            return {
                "records": records,
                "query_name": query_name,
                "parameters": parameters
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")