from datetime import datetime
from typing import List, Optional
from repository.neo4j.base import get_session, convert_neo4j_datetime

async def get_channel_list(owner_id: str | None, usernames: List[str] | None = None):
    async with get_session(owner_id) as session:
        query = """
        WITH [u IN $usernames | toLower(u)] AS usernames_lower
        MATCH (ch:Channel)
        WHERE ($ownerId IS NULL OR ch.owner_id = $ownerId)
          AND ($usernames IS NULL OR size($usernames) = 0 OR toLower(ch.username) IN usernames_lower OR toLower(ch.channel_id) IN usernames_lower)
        OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId) AND m.date IS NOT NULL AND (m.original_text IS NOT NULL OR m.text IS NOT NULL)
        WITH ch, COUNT { (ch)-[:HAS_MESSAGE]->(m) } AS msg_count, MAX(m.date) AS latest
        WHERE msg_count > 0 OR ($usernames IS NOT NULL AND size($usernames) > 0)
        OPTIONAL MATCH (other:Channel)-[:RECOMMENDS]->(ch)
        WHERE ($ownerId IS NULL OR other.owner_id = $ownerId) AND (other.channel_id = ch.channel_id OR other.username = ch.username)
        WITH ch, msg_count, latest, COUNT(other) AS recommended_by
        RETURN ch.channel_id AS channel_id, coalesce(ch.username, '') AS username, coalesce(ch.title, '') AS title,
               msg_count AS message_count, latest AS last_message_date, recommended_by,
               coalesce(ch.scraped, false) AS is_scraped, ch.scraped_at AS scraped_at
        ORDER BY last_message_date DESC
        """
        params = {"ownerId": owner_id, "usernames": usernames or []}
        result = await session.run(query, params)
        channels = []
        async for r in result:
            channels.append({
                "channel_id": str(r["channel_id"]), "username": r["username"], "title": r["title"],
                "message_count": r["message_count"], "last_message_date": convert_neo4j_datetime(r["last_message_date"]),
                "recommended_by": r["recommended_by"], "is_scraped": r["is_scraped"],
                "scraped_at": convert_neo4j_datetime(r["scraped_at"]),
            })
        return channels

async def get_channel_by_id(channel_id: str, owner_id: str | None):
    async with get_session(owner_id) as session:
        query = """
        MATCH (ch:Channel) WHERE toLower(ch.channel_id) = toLower($channel_id) AND ($ownerId IS NULL OR ch.owner_id = $ownerId)
        OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message) WHERE ($ownerId IS NULL OR m.owner_id = $ownerId) AND m.date IS NOT NULL
        OPTIONAL MATCH (ch)-[:RECOMMENDS]->(rec:Channel) WHERE ($ownerId IS NULL OR rec.owner_id = $ownerId) AND (rec.channel_id = ch.channel_id OR rec.username = ch.username)
        OPTIONAL MATCH (other:Channel)-[:RECOMMENDS]->(ch) WHERE ($ownerId IS NULL OR other.owner_id = $ownerId) AND (other.channel_id = ch.channel_id OR other.username = ch.username)
        RETURN ch.channel_id AS channel_id, coalesce(ch.username, ch.channel_id) AS username, ch.title AS title,
            count(DISTINCT m) AS message_count, min(m.date) AS first_message, max(m.date) AS last_message,
            count(DISTINCT rec) AS recommends_count, count(DISTINCT other) AS recommended_by_count,
            ch.scraped AS is_scraped, ch.scraped_at AS scraped_at
        """
        rec = await (await session.run(query, {"channel_id": str(channel_id), "ownerId": owner_id})).single()
        if not rec: return None
        return {
            "channel_id": rec["channel_id"], "username": rec["username"], "title": rec["title"], "message_count": rec["message_count"],
            "first_message": convert_neo4j_datetime(rec["first_message"]), "last_message": convert_neo4j_datetime(rec["last_message"]),
            "recommends_count": rec["recommends_count"], "recommended_by_count": rec["recommended_by_count"],
            "is_scraped": rec["is_scraped"], "scraped_at": convert_neo4j_datetime(rec["scraped_at"]),
        }

async def get_user_channels(user_id: int, owner_id: str | None):
    async with get_session(owner_id) as session:
        result = await session.run(
            """
            MATCH (u:User {user_id:$user_id, owner_id:$ownerId})-[:PART_OF]->(ch:Channel)
            OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
            WITH ch, count(m) AS msg_count, max(m.date) AS latest
            OPTIONAL MATCH (other:Channel)-[:RECOMMENDS]->(ch)
            WHERE ($ownerId IS NULL OR other.owner_id = $ownerId) AND (other.channel_id = ch.channel_id OR other.username = ch.username)
            RETURN ch.channel_id AS channel_id, ch.username AS username, ch.title AS title, msg_count AS message_count,
                   latest AS last_message_date, count(other) AS recommended_by, ch.scraped AS is_scraped,
                   coalesce(ch.scraped_at, null) AS scraped_at
            ORDER BY last_message_date DESC
            """,
            {"user_id": user_id, "ownerId": owner_id},
        )
        return [{"channel_id": r["channel_id"], "username": r["username"], "title": r["title"], "message_count": r["message_count"],
                 "last_active": r["last_message_date"], "recommended_by": r["recommended_by"], "is_scraped": r["is_scraped"],
                 "scraped_at": r["scraped_at"]} async for r in result]

async def get_channel_locations_data(channel_id: str, owner_id: str | None, limit: int):
    async with get_session(owner_id) as session:
        query = """
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)-[:MENTIONS_LOCATION]->(l:Location)
        WHERE toLower(ch.channel_id) = toLower($channel_id) AND ($ownerId IS NULL OR m.owner_id = $ownerId) AND l.location IS NOT NULL
        RETURN m.id as message_id, l.location as location, l['canonical_name'] as canonical_name, l['latitude'] as latitude,
               l['longitude'] as longitude, l['country'] as country, l['mention_count'] as mention_count, coalesce(m.translated_text, m.original_text, m['text'], '') as text
        LIMIT $limit
        """
        result = await session.run(query, {"channel_id": str(channel_id), "ownerId": owner_id, "limit": limit})
        data = []
        async for r in result:
            loc = r["location"]
            data.append({
                "message_id": r["message_id"],
                "location": {"lat": loc.y if hasattr(loc, 'y') else r["latitude"], "lng": loc.x if hasattr(loc, 'x') else r["longitude"]},
                "canonical_name": r.get("canonical_name"), "country": r.get("country"), "mention_count": r.get("mention_count", 1), "text": r.get("text")
            })
        return data

async def get_channel_emotions(channel_id: str, owner_id: str | None):
    async with get_session(owner_id) as session:
        query = """
        MATCH (ch:Channel) WHERE toLower(ch.channel_id) = toLower($channel_id) AND ($ownerId IS NULL OR ch.owner_id = $ownerId)
        MATCH (ch)-[:HAS_MESSAGE]->(m:Message)-[r:HAS_EMOTION]->(e:Emotion) WHERE ($ownerId IS NULL OR m.owner_id = $ownerId)
        RETURN e.name as emotion, count(r) as count ORDER BY count DESC
        """
        result = await session.run(query, {"channel_id": str(channel_id), "ownerId": owner_id})
        return [{"emotion": r["emotion"], "count": r["count"]} async for r in result]

async def get_active_channels_in_period(owner_id: str | None, start_date: datetime, end_date: datetime):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR ch.owner_id = $ownerId) AND m.date >= $startDate AND m.date <= $endDate
        WITH ch, count(m) as msg_count RETURN ch.channel_id as channel_id, ch.username as username, ch.title as title, msg_count
        ORDER BY msg_count DESC
        """
        result = await session.run(cypher, {"ownerId": owner_id, "startDate": start_date, "endDate": end_date})
        return [{"channel_id": r["channel_id"], "username": r["username"], "title": r["title"], "message_count": r["msg_count"]} async for r in result]
