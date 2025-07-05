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
        elif viz_request.visualization_type == "timeline":
            return await get_timeline_visualization(viz_request)
        else:
            raise HTTPException(status_code=400, detail="Unsupported visualization type")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visualization failed: {str(e)}")

async def get_network_visualization(viz_request: GraphVisualizationRequest):
    """Generate network visualization data"""
    async with driver.session() as session:
        # Build dynamic query based on request
        where_clauses = []
        params = {"limit": viz_request.limit}
        
        if viz_request.channel_ids:
            where_clauses.append("ch.channel_id IN $channel_ids")
            params["channel_ids"] = viz_request.channel_ids
        
        if viz_request.search_query:
            where_clauses.append("toLower(m.text) CONTAINS toLower($search_query)")
            params["search_query"] = viz_request.search_query
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = f"""
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)<-[:SENT]-(u:User)
        {where_clause}
        WITH ch, u, count(m) as message_count
        MATCH (ch)-[:HAS_MESSAGE]->(m2:Message)<-[:SENT]-(u)
        OPTIONAL MATCH (u)-[:SENT]->(reply:Message)-[:REPLY_TO]->(original:Message)<-[:SENT]-(other_user:User)
        RETURN 
            ch.channel_id as channel_id,
            ch.username as channel_name,
            ch.title as channel_title,
            u.user_id as user_id,
            u.username as username,
            u.first_name as first_name,
            u.last_name as last_name,
            message_count,
            collect(DISTINCT other_user.user_id) as replied_to_users
        LIMIT $limit
        """
        
        result = await session.run(query, params)
        
        nodes = []
        relationships = []
        node_ids = set()
        
        async for record in result:
            # Add channel node
            channel_id = f"ch_{record['channel_id']}"
            if channel_id not in node_ids:
                nodes.append({
                    "id": channel_id,
                    "label": record["channel_name"] or record["channel_title"],
                    "type": "Channel",
                    "properties": {
                        "username": record["channel_name"],
                        "title": record["channel_title"]
                    }
                })
                node_ids.add(channel_id)
            
            # Add user node
            user_name = record["username"] or f"{record['first_name'] or ''} {record['last_name'] or ''}".strip() or "Unknown"
            user_id = f"u_{record['user_id']}"
            if user_id not in node_ids:
                nodes.append({
                    "id": user_id,
                    "label": user_name,
                    "type": "User",
                    "properties": {
                        "username": record["username"],
                        "first_name": record["first_name"],
                        "last_name": record["last_name"]
                    }
                })
                node_ids.add(user_id)
            
            # Add relationship: User -> Channel
            relationships.append({
                "id": f"{user_id}_posts_in_{channel_id}",
                "from": user_id,
                "to": channel_id,
                "type": "POSTS_IN",
                "properties": {
                    "message_count": record["message_count"]
                }
            })
            
            # Add reply relationships
            for replied_user_id in record["replied_to_users"]:
                if replied_user_id:
                    replied_user_node_id = f"u_{replied_user_id}"
                    relationships.append({
                        "id": f"{user_id}_replies_to_{replied_user_node_id}",
                        "from": user_id,
                        "to": replied_user_node_id,
                        "type": "REPLIES_TO",
                        "properties": {}
                    })
        
        return {
            "nodes": nodes,
            "relationships": relationships,
            "summary": {
                "node_count": len(nodes),
                "relationship_count": len(relationships)
            }
        }

async def get_timeline_visualization(viz_request: GraphVisualizationRequest):
    """Generate timeline visualization data"""
    async with driver.session() as session:
        where_clauses = []
        params = {"limit": viz_request.limit}
        
        if viz_request.channel_ids:
            where_clauses.append("ch.channel_id IN $channel_ids")
            params["channel_ids"] = viz_request.channel_ids
        
        if viz_request.search_query:
            where_clauses.append("toLower(m.text) CONTAINS toLower($search_query)")
            params["search_query"] = viz_request.search_query
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        query = f"""
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)<-[:SENT]-(u:User)
        {where_clause}
        RETURN 
            m.date as date,
            m.text as text,
            m.mid as message_id,
            ch.username as channel,
            u.username as author,
            u.first_name as first_name,
            u.last_name as last_name
        ORDER BY m.date DESC
        LIMIT $limit
        """
        
        result = await session.run(query, params)
        
        timeline_data = []
        async for record in result:
            author_name = record["author"] or f"{record['first_name'] or ''} {record['last_name'] or ''}".strip() or "Unknown"
            timeline_data.append({
                "date": record["date"],
                "message_id": record["message_id"],
                "text": record["text"][:200] + "..." if len(record["text"]) > 200 else record["text"],
                "channel": record["channel"],
                "author": author_name
            })
        
        return {
            "timeline": timeline_data,
            "summary": {
                "message_count": len(timeline_data)
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