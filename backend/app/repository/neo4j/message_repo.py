import os
from datetime import datetime
from typing import List, Optional
from model.message_model import Author, Channel, Message
from repository.neo4j.base import get_session, convert_neo4j_datetime

async def get_unified_timeline_messages(
    owner_id: str | None,
    selected_channels: list[str] = None,
    limit: int = 1000,
    before: datetime | None = None,
    query: str | None = None,
):
    async with get_session(owner_id) as session:
        channel_filter = "AND ch.channel_id IN $channel_ids" if selected_channels else ""
        
        cypher = f"""
        MATCH (ch:Channel)
        WHERE ($ownerId IS NULL OR ch.owner_id = $ownerId)
        {channel_filter}
        
        MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId)
          AND m.date IS NOT NULL
          AND (m.original_text IS NOT NULL OR m.text IS NOT NULL)
          MATCH (u:User)-[:SENT]->(m)
        WHERE ($ownerId IS NULL OR u.owner_id = $ownerId)
        AND (
            $query IS NULL OR $query = '' OR
            toLower(m.text) CONTAINS toLower($query)
        )
        AND ($before IS NULL OR m.date < $before)

        WITH m, ch, u
        ORDER BY (CASE WHEN u.username = ch.username THEN 1 ELSE 0 END)
        WITH m, ch, head(collect(u)) as u

        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        
        RETURN m.original_text      AS original_text,
                m.translated_text    AS translated_text,
                m.original_language  AS original_language,
                m.translation_status AS translation_status,
               m.date        AS date,
               m.media_type  AS media_type,
               m.media_path  AS media_path,
               m.mid         AS message_id,
               u.user_id     AS user_id,
               coalesce(u.username, '')    AS username,
               coalesce(u.first_name, '')  AS first_name,
               coalesce(u.last_name, '')   AS last_name,
               ch.channel_id AS channel_id,
               ch.username   AS channel_username,
               ch.title      AS channel_title,
               reply.mid     AS reply_to_id
        ORDER BY m.date DESC
        LIMIT $limit
        """

        params = {"limit": limit, "query": query, "before": before, "ownerId": owner_id}
        if selected_channels: params["channel_ids"] = selected_channels

        result = await session.run(cypher, params)
        messages = []
        async for r in result:
            date_value = convert_neo4j_datetime(r["date"])
            if not date_value or not r["original_text"]: continue
            
            author_name = r["username"] or f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or "Unknown"
            messages.append({
                "message_id": r["message_id"],
                "original_text": r.get("original_text") or r.get("text") or "",
                "translated_text": r.get("translated_text"),
                "original_language": r.get("original_language") or "unknown",
                "translation_status": r.get("translation_status") or "none",
                "date": date_value,
                "media_type": r["media_type"],
                "media_path": r["media_path"],
                "reply_to_id": r["reply_to_id"],
                "author": {"id": r["user_id"], "name": author_name},
                "channel": {"id": r["channel_id"], "username": r["channel_username"], "title": r["channel_title"]},
            })
        return messages

async def get_messages_by_id(message_id: str, owner_id: str | None) -> Optional[Message]:
    async with get_session(owner_id) as session:
        query = """
        MATCH (m:Message {mid:$message_id})
        WHERE $ownerId IS NULL OR m.owner_id = $ownerId
        OPTIONAL MATCH (u:User  )-[:SENT]->(m)
        OPTIONAL MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        RETURN m, u AS a, ch AS c
        """
        rec = await (await session.run(query, {"message_id": message_id, "ownerId": owner_id})).single()
        if not rec: return None
        m, a, c = rec["m"], rec["a"], rec["c"]
        author = Author(id=a["user_id"], name=a.get("username") or a.get("first_name") or a.get("last_name") or "Unknown")
        channel = Channel(id=c["channel_id"], username=c["username"])
        return Message(message_id=m["mid"], text=m["text"], date=m["date"], media_type=m.get("media_type"),
                       media_path=m.get("media_path"), reply_to_id=m.get("reply_to"), author=author, channel=channel)

async def get_messages_for_channel(channel_id: str, owner_id: str | None, limit: int = 1000,
                                 before: datetime | None = None, query: str | None = None):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (ch:Channel)
        WHERE ($ownerId IS NULL OR ch.owner_id = $ownerId)
          AND (toLower(ch.channel_id) = toLower($channel_id) OR toLower(ch.username) = toLower($channel_id))
        MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId)
          AND m.date IS NOT NULL AND (m.original_text IS NOT NULL OR m.text IS NOT NULL)
        MATCH (u:User)-[:SENT]->(m)
        WHERE ($ownerId IS NULL OR u.owner_id = $ownerId)
          AND ($query IS NULL OR $query = '' OR toLower(coalesce(m.original_text, m.text, '')) CONTAINS toLower($query))
          AND ($before IS NULL OR m.date < $before)
        WITH m, ch, u ORDER BY (CASE WHEN u.username = ch.username THEN 1 ELSE 0 END)
        WITH m, ch, head(collect(u)) as u
        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        RETURN m.original_text AS original_text, m.translated_text AS translated_text,
               m.original_language AS original_language, m.translation_status AS translation_status,
               m.image_text AS image_text, m.image_text_translated AS image_text_translated,
               m.audio_text AS audio_text, m.audio_text_translated AS audio_text_translated,
               m.image_analysis_status AS image_analysis_status,
               m.audio_transcription_status AS audio_transcription_status,
               m.classification_status AS classification_status,
               m.emotion_status AS emotion_status,
               m.geolocation_status AS geolocation_status,
               m.date AS date, m.media_type AS media_type, m.media_path AS media_path,
               m.mid AS message_id, u.user_id AS user_id, coalesce(u.username, '') AS username,
               coalesce(u.first_name, '') AS first_name, coalesce(u.last_name, '') AS last_name,
               ch.channel_id AS channel_id, ch.username AS channel_username, reply.mid AS reply_to_id
        ORDER BY m.date DESC LIMIT $limit
        """
        params = {"channel_id": str(channel_id), "limit": limit, "query": query, "before": before, "ownerId": owner_id}
        result = await session.run(cypher, params)
        messages = []
        async for r in result:
            date_value = convert_neo4j_datetime(r["date"])
            if not date_value: continue
            author_name = r["username"] or f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or "Unknown"
            messages.append({
                "message_id": r["message_id"], "original_text": r.get("original_text") or "",
                "translated_text": r.get("translated_text"), "image_text": r.get("image_text") or "",
                "image_text_translated": r.get("image_text_translated") or "",
                "audio_text": r.get("audio_text") or "", "audio_text_translated": r.get("audio_text_translated") or "",
                "original_language": r.get("original_language") or "unknown",
                "translation_status": r.get("translation_status") or "none",
                "image_analysis_status": r.get("image_analysis_status") or "none",
                "audio_transcription_status": r.get("audio_transcription_status") or "none",
                "classification_status": r.get("classification_status") or "none",
                "emotion_status": r.get("emotion_status") or "none",
                "geolocation_status": r.get("geolocation_status") or "none",
                "date": date_value,
                "media_type": r.get("media_type"), "media_path": r.get("media_path"),
                "reply_to_id": r.get("reply_to_id"), "author": {"id": r["user_id"], "name": author_name},
                "channel": {"id": r["channel_id"], "username": r["channel_username"]},
            })
        return messages

async def get_user_messages(user_id: int, owner_id: str | None, limit: int = 100,
                          before: datetime | None = None, query: str | None = None):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (u:User {user_id:$user_id, owner_id:$ownerId})-[:SENT]->(m:Message)
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        WHERE ($query IS NULL OR $query = '' OR (m.original_text IS NOT NULL AND toLower(m.original_text) CONTAINS toLower($query)))
          AND ($before IS NULL OR m.date < $before)
        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        RETURN m.original_text AS original_text, m.translated_text AS translated_text,
               m.original_language AS original_language, m.translation_status AS translation_status,
               m.date AS date, m.media_type AS media_type, m.media_path AS media_path,
               m.mid AS message_id, u.user_id AS user_id, u.username AS username,
               u.first_name AS first_name, u.last_name AS last_name,
               ch.channel_id AS channel_id, ch.username AS channel_username, reply.mid AS reply_to_id
        ORDER BY m.date DESC LIMIT $limit
        """
        params = {"user_id": user_id, "limit": limit, "query": query, "before": before.isoformat() if before else None, "ownerId": owner_id}
        result = await session.run(cypher, params)
        messages = []
        async for r in result:
            author_name = r["username"] or f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or "Unknown"
            messages.append({
                "message_id": r["message_id"], "original_text": r.get("original_text") or r.get("text") or "",
                "translated_text": r.get("translated_text"), "original_language": r.get("original_language") or "unknown",
                "translation_status": r.get("translation_status") or "none", "date": r["date"],
                "media_type": r["media_type"], "media_path": r["media_path"], "reply_to_id": r["reply_to_id"],
                "author": {"id": r["user_id"], "name": author_name}, "channel": {"id": r["channel_id"], "username": r["channel_username"]},
            })
        return messages

async def get_messages_with_media(owner_id: str | None, channel_ids: list[str] | None = None, limit: int = 100,
                                before: datetime | None = None, query: str | None = None):
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico', '.heic', '.heif', '.avif'}
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (u:User {owner_id:$ownerId})-[:SENT]->(m:Message)
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        WHERE m.media_path IS NOT NULL AND ($channelIds IS NULL OR ch.channel_id IN $channelIds)
          AND ($query IS NULL OR $query = '' OR (m.original_text IS NOT NULL AND toLower(m.original_text) CONTAINS toLower($query)))
          AND ($before IS NULL OR m.date < $before)
        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        RETURN m.original_text AS text, m.date AS date, m.translated_text AS translated_text,
               m.original_language AS original_language, m.translation_status AS translation_status,
               m.media_type AS media_type, m.media_path AS media_path, m.mid AS message_id,
               u.user_id AS user_id, u.username AS username, u.first_name AS first_name,
               u.last_name AS last_name, ch.channel_id AS channel_id, ch.username AS channel_username,
               reply.mid AS reply_to_id
        ORDER BY m.date ASC LIMIT $limit
        """
        params = {"limit": limit, "query": query, "before": before.isoformat() if before else None, "ownerId": owner_id, "channelIds": channel_ids}
        result = await session.run(cypher, params)
        messages = []
        async for r in result:
            author_name = r["username"] or f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or "Unknown"
            media_path = r["media_path"]
            if media_path:
                file_ext = media_path.lower().split('.')[-1] if '.' in media_path else ''
                is_image = f'.{file_ext}' in IMAGE_EXTENSIONS
                # Simple check for exists in shared/media
                check_path = os.path.join(os.getcwd(), 'shared/media', media_path.split('/media/')[-1])
                if is_image and os.path.exists(check_path):
                    messages.append({
                        "message_id": r["message_id"], "original_text": r.get("original_text") or r.get("text") or "",
                        "translated_text": r.get("translated_text"), "original_language": r.get("original_language") or "unknown",
                        "translation_status": r.get("translation_status") or "none", "date": r["date"],
                        "media_type": r["media_type"], "media_path": media_path, "is_image": True,
                        "reply_to_id": r["reply_to_id"], "author": {"id": r["user_id"], "name": author_name},
                        "channel": {"id": r["channel_id"], "username": r["channel_username"]},
                    })
        return messages

async def get_total_message_count_for_channels(channel_ids: list[str], owner_id: str | None,
                                             before: datetime | None = None, query: str | None = None):
    if not channel_ids: return 0
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (ch:Channel) WHERE ch.channel_id IN $channel_ids AND ($ownerId IS NULL OR ch.owner_id = $ownerId)
        MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId) AND m.date IS NOT NULL
          AND (m.original_text IS NOT NULL OR m.text IS NOT NULL)        
          MATCH (u:User)-[:SENT]->(m)
        WHERE ($ownerId IS NULL OR u.owner_id = $ownerId)
        AND ($query IS NULL OR $query = '' OR toLower(m.text) CONTAINS toLower($query))
        AND ($before IS NULL OR m.date < $before)
        RETURN count(m) AS total_count
        """
        params = {"channel_ids": [str(cid) for cid in channel_ids], "query": query, "before": before, "ownerId": owner_id}
        result = await session.run(cypher, params)
        record = await result.single()
        return record["total_count"] if record else 0

async def get_message_enrichment(message_id: str, owner_id: str | None) -> dict:
    """Fetch emotions, classifications, and locations for a single message."""
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (m:Message {mid: $mid})
        WHERE $ownerId IS NULL OR m.owner_id = $ownerId

        OPTIONAL MATCH (m)-[re:HAS_EMOTION]->(e:Emotion)
        OPTIONAL MATCH (m)-[rc:HAS_CLASSIFICATION]->(c:Classification)
        OPTIONAL MATCH (m)-[:MENTIONS_LOCATION]->(l:Location)

        RETURN
            collect(DISTINCT {label: e.name, confidence: re.confidence, source_emotions: re.source_emotions}) AS emotions,
            collect(DISTINCT {label: c.name, description: c.description, confidence: rc.confidence}) AS classifications,
            collect(DISTINCT {name: l.canonical_name, country: l.country, lat: l.lat, lng: l.lng}) AS locations
        """
        result = await session.run(cypher, {"mid": message_id, "ownerId": owner_id})
        record = await result.single()
        if not record:
            return {"emotions": [], "classifications": [], "locations": []}

        emotions = [e for e in record["emotions"] if e.get("label")]
        classifications = [c for c in record["classifications"] if c.get("label")]
        locations = [loc for loc in record["locations"] if loc.get("name") or loc.get("lat") is not None]

        return {"emotions": emotions, "classifications": classifications, "locations": locations}


async def get_message_volume_over_time(owner_id: str | None, start_date: datetime, end_date: datetime, interval: str = "day"):
    async with get_session(owner_id) as session:
        date_trunc = "date(m.date)" if interval == "day" else "date({year: m.date.year, month: m.date.month, day: 1})"
        cypher = f"""
        MATCH (m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId) AND m.date >= $startDate AND m.date <= $endDate
        WITH {date_trunc} as date_val, count(m) as count
        RETURN toString(date_val) as date, count ORDER BY date ASC
        """
        params = {"ownerId": owner_id, "startDate": start_date, "endDate": end_date}
        result = await session.run(cypher, params)
        return [{"date": r["date"], "count": r["count"]} async for r in result]
