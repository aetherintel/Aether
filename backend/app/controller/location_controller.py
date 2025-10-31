# backend/app/controller/location_controller.py
from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from services.auth_ctx import user_ctx, UserCtx
from services.neo4j_backend_client import get_session

router = APIRouter(prefix="/locations", tags=["locations"])

@router.get("/map")
async def get_map_locations(
    case_id: Optional[int] = None,
    channel_ids: Optional[List[str]] = Query(None),
    user: UserCtx = Depends(user_ctx)
):
    """Get all locations with coordinates for map display"""
    async with get_session(user["id"]) as session:
        cypher = """
        MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location)
        WHERE l.owner_id = $owner_id
          AND l.latitude IS NOT NULL
          AND l.longitude IS NOT NULL
          AND ($case_id IS NULL OR m.case_id = $case_id)
          AND ($channel_ids IS NULL OR m.channel_id IN $channel_ids)
        RETURN 
            l.latitude AS lat,
            l.longitude AS lng,
            l.display_name AS name,
            l.raw AS address,
            count(m) AS message_count,
            collect(DISTINCT m.mid)[0..5] AS sample_message_ids
        ORDER BY message_count DESC
        """
        
        result = await session.run(
            cypher,
            owner_id=user["id"],
            case_id=case_id,
            channel_ids=channel_ids
        )
        
        locations = []
        async for record in result:
            locations.append({
                "lat": record["lat"],
                "lng": record["lng"],
                "name": record["name"],
                "address": record["address"],
                "message_count": record["message_count"],
                "sample_message_ids": record["sample_message_ids"]
            })
        
        return {"locations": locations, "total": len(locations)}