from datetime import datetime
from typing import List, Dict
from collections import OrderedDict
from repository.neo4j.base import get_session

async def get_case_channels_with_recommendations(channel_usernames: List[str], owner_id: str | None = None) -> Dict[str, List[str]]:
    unique = list(OrderedDict.fromkeys(channel_usernames))
    lowercase = [u.lower() for u in unique]
    try:
        async with get_session(owner_id) as session:
            cypher = """
                MATCH (c:Channel)-[:RECOMMENDS]-(rec:Channel)
                WHERE ($ownerId IS NULL OR c.owner_id = $ownerId)
                AND (toLower(c.channel_id) IN $usernames OR toLower(c.username) IN $usernames)
                AND rec.username IS NOT NULL AND rec.username <> ''
                RETURN trim(replace(toLower(coalesce(c.username, c.channel_id)), '"', '')) AS input_key,
                       [r IN COLLECT(DISTINCT rec.username) | trim(replace(toLower(r), '"', ''))] AS recs
                """
            result = await session.run(cypher, usernames=lowercase, ownerId=owner_id)
            records = await result.data()
        raw_map = {r["input_key"]: r["recs"] for r in records}
        final = OrderedDict()
        for orig in unique:
            key = orig.lower()
            recs = raw_map.get(key, [])
            filtered = [r for r in recs if r.lower() != key]
            if filtered: final[orig] = filtered
        return final
    except Exception: return OrderedDict()

async def get_channel_recommendation_graph(owner_id: str | None):
    async with get_session(owner_id) as session:
        cypher = "MATCH (c1:Channel)-[:RECOMMENDS]->(c2:Channel) WHERE ($ownerId IS NULL OR c1.owner_id = $ownerId) RETURN c1.username as source, c2.username as target"
        result = await session.run(cypher, ownerId=owner_id)
        nodes, edges = set(), []
        async for r in result:
            s, t = r["source"], r["target"]
            if s and t: nodes.add(s); nodes.add(t); edges.append({"source": s, "target": t})
        return {"nodes": [{"id": n, "label": n} for n in nodes], "edges": edges}

async def get_user_interaction_graph(owner_id: str | None, limit: int = 200):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (u1:User)-[:SENT]->(m1:Message)<-[:REPLY_TO]-(m2:Message)<-[:SENT]-(u2:User)
        WHERE ($ownerId IS NULL OR m1.owner_id = $ownerId)
        RETURN u2.username as source, u1.username as target, count(*) as weight LIMIT $limit
        """
        result = await session.run(cypher, ownerId=owner_id, limit=limit)
        nodes, edges = set(), []
        async for r in result:
            s, t = r["source"] or "Unknown", r["target"] or "Unknown"
            nodes.add(s); nodes.add(t); edges.append({"source": s, "target": t, "weight": r["weight"]})
        return {"nodes": [{"id": n, "label": n} for n in nodes], "edges": edges}

async def get_top_locations(owner_id: str | None, limit: int = 10, before: datetime | None = None):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (m:Message)-[:MENTIONS_LOCATION]->(l:Location)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId) AND ($before IS NULL OR m.date < $before)
        RETURN l.canonical_name as name, count(m) as count ORDER BY count DESC LIMIT $limit
        """
        result = await session.run(cypher, {"ownerId": owner_id, "before": before, "limit": limit})
        return [{"name": r["name"], "count": r["count"]} async for r in result]

async def get_aggregated_emotions(owner_id: str | None, channel_ids: list[str] | None = None, start_date: datetime | None = None, end_date: datetime | None = None):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (ch:Channel) WHERE ($channelIds IS NULL OR ch.channel_id IN $channelIds) AND ($ownerId IS NULL OR ch.owner_id = $ownerId)
        MATCH (ch)-[:HAS_MESSAGE]->(m:Message)-[r:HAS_EMOTION]->(e:Emotion)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId) AND ($startDate IS NULL OR m.date >= $startDate) AND ($endDate IS NULL OR m.date <= $endDate)
        RETURN e.name as emotion, count(r) as count ORDER BY count DESC
        """
        result = await session.run(cypher, {"ownerId": owner_id, "channelIds": channel_ids, "startDate": start_date, "endDate": end_date})
        return [{"emotion": r["emotion"], "count": r["count"]} async for r in result]
