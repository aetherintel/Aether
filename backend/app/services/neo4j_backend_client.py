# telegram_job/neo4j_client.py
from contextlib import asynccontextmanager
import os
from datetime import datetime
from http.client import HTTPException
from typing import AsyncIterator, Dict, List, Optional, OrderedDict
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv
from model.message_model import Author, Channel, Message
from datetime import datetime
from neo4j.time import DateTime as Neo4jDateTime
from collections import OrderedDict
from typing import List, Dict


load_dotenv()

driver = AsyncGraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD"))
)

def convert_neo4j_datetime(value):
    """Convert Neo4j DateTime to Python datetime"""
    if isinstance(value, Neo4jDateTime):
        return value.to_native()
    return value

async def get_unified_timeline_messages(
    owner_id: str | None,
    selected_channels: list[str] = None,
    limit: int = 1000,
    before: datetime | None = None,
    query: str | None = None,
):
    """Get messages from selected channels, sorted globally by date (newest first)"""
    async with get_session(owner_id) as session:
        
        # Build channel filter - if no channels specified, get all user's channels
        if selected_channels:
            channel_filter = "AND ch.channel_id IN $channel_ids"
        else:
            channel_filter = ""
        
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

        params = {
            "limit": limit,
            "query": query,
            "before": before,
            "ownerId": owner_id,
        }
        
        # Add channel_ids parameter only if channels are specified
        if selected_channels:
            params["channel_ids"] = selected_channels

        result = await session.run(cypher, params)
        messages = []
        async for r in result:
            date_value = convert_neo4j_datetime(r["date"])
            
            if not date_value or not r["original_text"]:
                continue
                
            first_name = r["first_name"] or ""
            last_name = r["last_name"] or ""
            username = r["username"] or ""
            
            if username:
                author_name = username
            elif first_name or last_name:
                author_name = f"{first_name} {last_name}".strip()
            else:
                author_name = "Unknown"
                
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
                "channel": {
                    "id": r["channel_id"], 
                    "username": r["channel_username"],
                    "title": r["channel_title"]  # Extra context for timeline
                },
            })
        return messages

@asynccontextmanager
async def get_session(owner_id: str | None) -> AsyncIterator:
    """
    If owner_id is None (admin), returns the bare driver session.
    Otherwise wraps it so every .run(...) automatically receives $ownerId.
    """
    async with driver.session() as s:
        if owner_id is None:
            yield s
        else:
            yield _FilteredSession(s, owner_id)

class _FilteredSession:
    def __init__(self, sess, owner):  # no typing on purpose
        self.sess, self.owner = sess, owner

    async def run(self, cypher: str, parameters: dict | None = None, **kw):
        p = parameters.copy() if parameters else {}
        p.setdefault("ownerId", self.owner)
        return await self.sess.run(cypher, p, **kw)

    # expose execute_write / execute_read for backwards compat
    def __getattr__(self, name):
        return getattr(self.sess, name)

async def close():
    await driver.close()

# ----------------------------------------------------------------------
# Read helpers – every one now receives *owner_id*  (None ⇒ admin)
# ----------------------------------------------------------------------

async def get_messages_by_id(message_id: str, owner_id: str | None) -> Optional[Message]:
    async with get_session(owner_id) as session:
        query = """
        MATCH (m:Message {mid:$message_id})
        WHERE $ownerId IS NULL OR m.owner_id = $ownerId
        OPTIONAL MATCH (u:User  )-[:SENT]->(m)
        OPTIONAL MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        RETURN m, u AS a, ch AS c
        """

        try:
            rec = await (await session.run(
                query, {"message_id": message_id, "ownerId": owner_id})
            ).single()

            if not rec:
                return None

            m, a, c = rec["m"], rec["a"], rec["c"]
            author = Author(
                id=a["user_id"],
                name=a.get("username") or a.get("first_name") or a.get("last_name") or "Unknown",
            )
            channel = Channel(id=c["channel_id"], username=c["username"])
            return Message(
                message_id=m["mid"],
                text=m["text"],
                date=m["date"],
                media_type=m.get("media_type"),
                media_path=m.get("media_path"),
                reply_to_id=m.get("reply_to"),
                author=author,
                channel=channel,
            )

        except Exception as e:
            raise HTTPException(500, f"Datenbankfehler: {e}")


async def get_messages_for_channel(
    channel_id: str,
    owner_id: str | None,
    limit: int = 1000,
    before: datetime | None = None,
    query: str | None = None,
):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (ch:Channel)
        WHERE ($ownerId IS NULL OR ch.owner_id = $ownerId)
          AND (toLower(ch.channel_id) = toLower($channel_id)
               OR toLower(ch.username) = toLower($channel_id))
        MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId)
          AND m.date IS NOT NULL
          AND (m.original_text IS NOT NULL OR m.text IS NOT NULL)
        MATCH (u:User)-[:SENT]->(m)
        WHERE ($ownerId IS NULL OR u.owner_id = $ownerId)
          AND (
            $query IS NULL OR $query = '' OR
            toLower(coalesce(m.original_text, m.text, '')) CONTAINS toLower($query)
          )
          AND ($before IS NULL OR m.date < $before)
        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        RETURN
            m.original_text          AS original_text,
            m.translated_text        AS translated_text,
            m.original_language      AS original_language,
            m.translation_status     AS translation_status,
            m.date                   AS date,
            m.media_type             AS media_type,
            m.media_path             AS media_path,
            m.mid                    AS message_id,
            u.user_id                AS user_id,
            coalesce(u.username, '') AS username,
            coalesce(u.first_name, '') AS first_name,
            coalesce(u.last_name, '') AS last_name,
            ch.channel_id            AS channel_id,
            ch.username              AS channel_username,
            reply.mid                AS reply_to_id
        ORDER BY m.date DESC
        LIMIT $limit
        """

        params = {
            "channel_id": str(channel_id),
            "limit": limit,
            "query": query,
            "before": before,
            "ownerId": owner_id,
        }

        try:
            result = await session.run(cypher, params)
            messages = []
            async for r in result:
                date_value = convert_neo4j_datetime(r["date"])
                if not date_value:
                    continue

                author_name = (
                    r["username"]
                    or f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
                    or "Unknown"
                )

                messages.append({
                    "message_id": r["message_id"],
                    "original_text": r.get("original_text") or "",
                    "translated_text": r.get("translated_text"),
                    "original_language": r.get("original_language") or "unknown",
                    "translation_status": r.get("translation_status") or "none",
                    "date": date_value,
                    "media_type": r.get("media_type"),
                    "media_path": r.get("media_path"),
                    "reply_to_id": r.get("reply_to_id"),
                    "author": {"id": r["user_id"], "name": author_name},
                    "channel": {"id": r["channel_id"], "username": r["channel_username"]},
                })
            return messages
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Fehler beim Abrufen der Nachrichten: {str(e)}"
            )

async def get_channel_list(owner_id: str | None, usernames: list[str] | None = None):
    """
    Fetch all channels for the given owner, optionally filtered by username list.
    Returns channels with message count, last activity, recommendation count,
    and scraped status. Compatible with Neo4j 6+.
    """
    async with get_session(owner_id) as session:
        query = """
        // Normalize usernames for case-insensitive matching
        WITH [u IN $usernames | toLower(u)] AS usernames_lower

        // Base match: channels belonging to this owner
        MATCH (ch:Channel)
        WHERE ($ownerId IS NULL OR ch.owner_id = $ownerId)
          AND (
            $usernames IS NULL OR size($usernames) = 0 OR
            toLower(ch.username) IN usernames_lower OR
            toLower(ch.channel_id) IN usernames_lower
          )

        // Count messages
        OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId)
          AND m.date IS NOT NULL
          AND (m.original_text IS NOT NULL OR m.text IS NOT NULL)
        WITH ch, COUNT { (ch)-[:HAS_MESSAGE]->(m) } AS msg_count, MAX(m.date) AS latest
        WHERE msg_count > 0

        // Count recommendations (who points to this channel)
        OPTIONAL MATCH (other:Channel)-[:RECOMMENDS]->(ch)
        WHERE ($ownerId IS NULL OR other.owner_id = $ownerId)
          AND (other.channel_id = ch.channel_id OR other.username = ch.username)
        WITH ch, msg_count, latest, COUNT(other) AS recommended_by

        RETURN
            ch.channel_id              AS channel_id,
            coalesce(ch.username, '')  AS username,
            coalesce(ch.title, '')     AS title,
            msg_count                  AS message_count,
            latest                     AS last_message_date,
            recommended_by,
            coalesce(ch.scraped, false)     AS is_scraped,
            ch.scraped_at              AS scraped_at
        ORDER BY last_message_date DESC
        """

        # ✅ Always include both params to avoid ParameterMissing
        params = {
            "ownerId": owner_id,
            "usernames": usernames or []
        }

        result = await session.run(query, params)
        channels = []

        async for r in result:
            channels.append({
                "channel_id": str(r["channel_id"]),
                "username": r["username"],
                "title": r["title"],
                "message_count": r["message_count"],
                "last_message_date": convert_neo4j_datetime(r["last_message_date"]),  # ✅ renamed here
                "recommended_by": r["recommended_by"],
                "is_scraped": r["is_scraped"],
                "scraped_at": convert_neo4j_datetime(r["scraped_at"]),
            })


        return channels

async def get_channel_by_id(channel_id: str, owner_id: str | None):
    async with get_session(owner_id) as session:
        query = """
        MATCH (ch:Channel)
WHERE toLower(ch.channel_id) = toLower($channel_id)
        WHERE $ownerId IS NULL OR ch.owner_id = $ownerId

        OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WHERE ($ownerId IS NULL OR m.owner_id = $ownerId)
          AND m.date IS NOT NULL

          OPTIONAL MATCH (ch)-[:RECOMMENDS]->(rec:Channel)
  WHERE ($ownerId IS NULL OR rec.owner_id = $ownerId)
    AND (rec.channel_id = ch.channel_id OR rec.username = ch.username)

  OPTIONAL MATCH (other:Channel)-[:RECOMMENDS]->(ch)
  WHERE ($ownerId IS NULL OR other.owner_id = $ownerId)
    AND (other.channel_id = ch.channel_id OR other.username = ch.username)

        RETURN
            ch.channel_id             AS channel_id,
            coalesce(ch.username, '') AS username,
            ch.title                  AS title,
            count(DISTINCT m)         AS message_count,
            min(m.date)               AS first_message,
            max(m.date)               AS last_message,
            count(DISTINCT rec)       AS recommends_count,
            count(DISTINCT other)     AS recommended_by_count,
            ch.scraped                AS is_scraped,
            ch.scraped_at             AS scraped_at
        """
        rec = await (await session.run(
            query,
            {"channel_id": str(channel_id), "ownerId": owner_id},
        )).single()

        if not rec:
            return None

        return {
            "channel_id": rec["channel_id"],
            "username": rec["username"],
            "title": rec["title"],
            "message_count": rec["message_count"],
            "first_message": convert_neo4j_datetime(rec["first_message"]),
            "last_message": convert_neo4j_datetime(rec["last_message"]),
            "recommends_count": rec["recommends_count"],
            "recommended_by_count": rec["recommended_by_count"],
            "is_scraped": rec["is_scraped"],
            "scraped_at": convert_neo4j_datetime(rec["scraped_at"]),
        }
async def get_user_channels(user_id: int, owner_id: str | None):
    async with get_session(owner_id) as session:
        result = await session.run(
            """
            MATCH (u:User {user_id:$user_id, owner_id:$ownerId})-[:PART_OF]->(ch:Channel)
            OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
            WITH ch, count(m) AS msg_count, max(m.date) AS latest
              OPTIONAL MATCH (other:Channel)-[:RECOMMENDS]->(ch)
  WHERE ($ownerId IS NULL OR other.owner_id = $ownerId)
    AND (other.channel_id = ch.channel_id OR other.username = ch.username)

            RETURN ch.channel_id  AS channel_id,
                   ch.username    AS username,
                   ch.title       AS title,
                   msg_count      AS message_count,
                   latest         AS last_message_date,
                   count(other)   AS recommended_by,
                   ch.scraped     AS is_scraped,
                   coalesce(ch.scraped_at, null) AS scraped_at
            ORDER BY last_message_date DESC
            """,
            {"user_id": user_id, "ownerId": owner_id},
        )
        channels = []
        async for r in result:
            channels.append(
                {
                    "channel_id": r["channel_id"],
                    "username": r["username"],
                    "title": r["title"],
                    "message_count": r["message_count"],
                    "last_active": r["last_message_date"],
                    "recommended_by": r["recommended_by"],
                    "is_scraped": r["is_scraped"],
                    "scraped_at": r["scraped_at"],
                }
            )
        return channels


async def get_user_messages(
    user_id: int,
    owner_id: str | None,
    limit: int = 100,
    before: datetime | None = None,
    query: str | None = None,
):
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (u:User {user_id:$user_id, owner_id:$ownerId})-[:SENT]->(m:Message)
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        WHERE (
            $query IS NULL OR $query = '' OR
            (m.original_text IS NOT NULL AND toLower(m.original_text) CONTAINS toLower($query))
        )
        AND ($before IS NULL OR m.date < $before)
        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        RETURN m.original_text AS original_text,
               m.translated_text AS translated_text,
               m.original_language AS original_language,
               m.translation_status AS translation_status,
               m.date        AS date,
               m.media_type  AS media_type,
               m.media_path  AS media_path,
               m.mid         AS message_id,
               u.user_id     AS user_id,
               u.username    AS username,
               u.first_name  AS first_name,
               u.last_name   AS last_name,
               ch.channel_id AS channel_id,
               ch.username   AS channel_username,
               reply.mid     AS reply_to_id
        ORDER BY m.date DESC
        LIMIT $limit
        """

        params = {
            "user_id": user_id,
            "limit": limit,
            "query": query,
            "before": before.isoformat() if before else None,
            "ownerId": owner_id,
        }

        result = await session.run(cypher, params)
        messages = []
        async for r in result:
            author_name = (
                r["username"]
                or f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
                or "Unknown"
            )
            messages.append(
                {
                    "message_id": r["message_id"],
                    "original_text": r.get("original_text") or r.get("text") or "",
                    "translated_text": r.get("translated_text"),
                    "original_language": r.get("original_language") or "unknown",
                    "translation_status": r.get("translation_status") or "none",
                    "date": r["date"],
                    "media_type": r["media_type"],
                    "media_path": r["media_path"],
                    "reply_to_id": r["reply_to_id"],
                    "author": {"id": r["user_id"], "name": author_name},
                    "channel": {"id": r["channel_id"], "username": r["channel_username"]},
                }
            )
        return messages
    
async def get_messages_with_media(
    owner_id: str | None,
    channel_ids: list[str] | None = None,
    limit: int = 100,
    before: datetime | None = None,
    query: str | None = None,
):
    IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
        '.webp', '.svg', '.ico', '.heic', '.heif', '.avif'
    }

    async with get_session(owner_id) as session:
        cypher = """
        MATCH (u:User {owner_id:$ownerId})-[:SENT]->(m:Message)
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m)
        WHERE m.media_path IS NOT NULL
          AND ($channelIds IS NULL OR ch.channel_id IN $channelIds)
          AND (
            $query IS NULL OR $query = '' OR
            (m.original_text IS NOT NULL AND toLower(m.original_text) CONTAINS toLower($query))
          )
          AND ($before IS NULL OR m.date < $before)
        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        RETURN m.original_text AS text,
               m.date        AS date,
               m.translated_text    AS translated_text,
                m.original_language  AS original_language,
                m.translation_status AS translation_status,
               m.media_type  AS media_type,
               m.media_path  AS media_path,
               m.mid         AS message_id,
               u.user_id     AS user_id,
               u.username    AS username,
               u.first_name  AS first_name,
               u.last_name   AS last_name,
               ch.channel_id AS channel_id,
               ch.username   AS channel_username,
               reply.mid     AS reply_to_id
        ORDER BY m.date ASC
        LIMIT $limit
        """

        params = {
            "limit": limit,
            "query": query,
            "before": before.isoformat() if before else None,
            "ownerId": owner_id,
            "channelIds": channel_ids if channel_ids else None,
        }

        result = await session.run(cypher, params)
        messages = []
        async for r in result:
            author_name = (
                r["username"]
                or f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
                or "Unknown"
            )

            media_path = r["media_path"]
            is_image = False
            is_downloaded = False
            if media_path:
                file_extension = media_path.lower().split('.')[-1] if '.' in media_path else ''
                is_image = f'.{file_extension}' in IMAGE_EXTENSIONS
                if is_image:
                    print(f"[CHECK DIR] {os.getcwd()}shared/media/{media_path.split('/media/')[-1]} exists {os.path.exists(os.getcwd() + 'shared/media/' + media_path.split('/media/')[-1])} ")
                    is_downloaded = os.path.exists(os.getcwd() + 'shared/media/' + media_path.split('/media/')[-1])

            if is_downloaded:
                messages.append(
                    {
                        "message_id": r["message_id"],
                        "original_text": r.get("original_text") or r.get("text") or "",
                        "translated_text": r.get("translated_text"),
                        "original_language": r.get("original_language") or "unknown",
                        "translation_status": r.get("translation_status") or "none",
                        "date": r["date"],
                        "media_type": r["media_type"],
                        "media_path": media_path,
                        "is_image": is_image,
                        "reply_to_id": r["reply_to_id"],
                        "author": {"id": r["user_id"], "name": author_name},
                        "channel": {"id": r["channel_id"], "username": r["channel_username"]},
                    }
                )
        return messages


async def get_case_channels_with_recommendations(
    channel_usernames: List[str],
    owner_id: str | None = None
) -> Dict[str, List[str]]:
    """
    Returns an OrderedDict mapping each input channel (de-duplicated) to the
    list of OTHER channels it recommends.  Channels with zero recommendations
    are omitted entirely.
    """
    # 1) collapse duplicates while preserving order
    unique = list(OrderedDict.fromkeys(channel_usernames))
    lowercase = [u.lower() for u in unique]

    try:
        async with get_session(owner_id) as session:
            cypher = """
                MATCH (c:Channel)-[:RECOMMENDS]-(rec:Channel)
                WHERE ($ownerId IS NULL OR c.owner_id = $ownerId)
                AND (
                    toLower(c.channel_id) IN $usernames OR
                    toLower(c.username)   IN $usernames
                )
                AND rec.username IS NOT NULL AND rec.username <> ''
                RETURN
                trim(replace(toLower(c.username), '"', '')) AS input_key,
                [r IN COLLECT(DISTINCT rec.username) | trim(replace(toLower(r), '"', ''))] AS recs
                """

            result = await session.run(
                cypher,
                usernames=lowercase,
                ownerId=owner_id
            )
            records = await result.data()

        # 2) build a map from lowercase key → raw rec list
        raw_map = {r["input_key"]: r["recs"] for r in records}

        # 3) build final OrderedDict, filtering out self and empty lists
        final = OrderedDict()
        for orig in unique:
            key = orig.lower()
            recs = raw_map.get(key, [])
            # drop any rec equal to the channel itself
            filtered = [r for r in recs if r.lower() != key]
            if filtered:
                final[orig] = filtered

        return final

    except Exception:
        # on error, just return empty (no menu entries)
        return OrderedDict()

async def get_total_message_count_for_channels(
    channel_ids: list[str],
    owner_id: str | None,
    before: datetime | None = None,
    query: str | None = None,
):
    """
    Get the total message count for multiple channels combined.
    
    Args:
        channel_ids: List of channel IDs to count messages for
        owner_id: Owner ID filter (None for all owners)
        before: Optional datetime to filter messages before this date
        query: Optional text query to filter messages
        
    Returns:
        int: Total count of messages across all specified channels
    """
    if not channel_ids:
        return 0
        
    async with get_session(owner_id) as session:
        cypher = """
        MATCH (ch:Channel)
        WHERE ch.channel_id IN $channel_ids
          AND ($ownerId IS NULL OR ch.owner_id = $ownerId)
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
        RETURN count(m) AS total_count
        """

        params = {
            "channel_ids": [str(channel_id) for channel_id in channel_ids],
            "query": query,
            "before": before,
            "ownerId": owner_id,
        }

        result = await session.run(cypher, params)
        record = await result.single()
        return record["total_count"] if record else 0