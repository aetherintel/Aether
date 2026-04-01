# lib/neo4j/channels.py
"""
Neo4j operations for channels
"""
import logging
from .connection import get_driver, _with_constraints, get_owner_id

logger = logging.getLogger(__name__)


@_with_constraints
async def is_scraped(username: str) -> bool:
    """Check if channel has been scraped"""
    async with get_driver().session() as session:
        owner = get_owner_id()
        rec = await (
            await session.run(
                """
                MATCH (c:Channel {username:$username, owner_id:$owner})
                      -[:HAS_MESSAGE]->(:Message)
                RETURN count(*) > 0 AS scraped
                """,
                username=username,
                owner=owner,
            )
        ).single()
        return rec and rec["scraped"]


@_with_constraints
async def mark_scraped(username: str):
    """Mark channel as scraped"""
    async with get_driver().session() as session:
        owner = get_owner_id()
        await session.run(
            """
            MERGE (c:Channel {username:$username, owner_id:$owner})
            SET   c.scraped=true, c.scraped_at=timestamp()
            """,
            username=username,
            owner=owner,
        )


@_with_constraints
async def write_recommendations(root, recs):
    """Write channel recommendations"""
    async with get_driver().session() as s:
        owner = get_owner_id()
        for r in recs:
            await s.run(
                """
                MATCH (root:Channel {username:$root_id, owner_id:$owner})
                
                MERGE (rec:Channel {username:$rec_username, owner_id:$owner})
                ON CREATE SET rec.title=$rec_title

                MERGE (root)-[:RECOMMENDS]->(rec)
                """,
                owner=owner,
                root_id=root,
                rec_username=r.get("username"),
                rec_title=r.get("title"),
            )


@_with_constraints
async def get_latest_message_id(username: str) -> int | None:
    """Get the highest message ID (mid) for a channel"""
    async with get_driver().session() as session:
        owner = get_owner_id()
        rec = await (
            await session.run(
                """
                MATCH (c:Channel {username:$username, owner_id:$owner})
                      -[:HAS_MESSAGE]->(m:Message)
                RETURN max(m.mid) as last_id
                """,
                username=username,
                owner=owner,
            )
        ).single()
        return rec["last_id"] if rec and rec["last_id"] is not None else None


@_with_constraints
async def find_scraped_channel_owner(username: str) -> str | None:
    """
    Find any other owner who has fully scraped this channel.
    Returns their owner_id, or None if no one has scraped it yet.
    """
    async with get_driver().session() as session:
        rec = await (
            await session.run(
                """
                MATCH (c:Channel {username: $username, scraped: true})
                      -[:HAS_MESSAGE]->(m:Message)
                WHERE c.owner_id IS NOT NULL
                RETURN c.owner_id AS owner_id, count(m) AS msg_count
                ORDER BY msg_count DESC
                LIMIT 1
                """,
                username=username,
            )
        ).single()
        return rec["owner_id"] if rec else None


@_with_constraints
async def copy_channel_for_owner(username: str, source_owner: str, target_owner: str) -> int:
    """
    Clone an already-scraped channel (and all its messages, users, enrichments)
    from source_owner to target_owner without hitting Telegram at all.

    Strategy: for each Message node owned by source_owner in this channel, create
    a new Message node (with target_owner) that is a full property copy.  Then
    re-attach Channel, User, reply chains, and all enrichment relationships
    (HAS_EMOTION, HAS_CLASSIFICATION, MENTIONS_LOCATION).

    Returns the number of messages copied.
    """
    async with get_driver().session() as session:
        # Step 1 – copy / merge Channel node for target owner
        await session.run(
            """
            MATCH (src:Channel {username: $username, owner_id: $source_owner})
            MERGE (tgt:Channel {channel_id: src.channel_id, owner_id: $target_owner})
            ON CREATE SET
                tgt.username      = src.username,
                tgt.title         = src.title,
                tgt.scraped       = src.scraped,
                tgt.scraped_at    = src.scraped_at
            ON MATCH SET
                tgt.title         = src.title,
                tgt.scraped       = src.scraped,
                tgt.scraped_at    = src.scraped_at
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )
        logger.info(f"[COPY] Channel node ready for {target_owner}")

        # Step 2 – copy User nodes
        await session.run(
            """
            MATCH (src_ch:Channel {username: $username, owner_id: $source_owner})
                  <-[:PART_OF]-(u_src:User {owner_id: $source_owner})
            MATCH (tgt_ch:Channel {username: $username, owner_id: $target_owner})
            MERGE (u_tgt:User {user_id: u_src.user_id, owner_id: $target_owner})
            ON CREATE SET
                u_tgt.first_name = u_src.first_name,
                u_tgt.last_name  = u_src.last_name,
                u_tgt.username   = u_src.username
            MERGE (u_tgt)-[:PART_OF]->(tgt_ch)
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )
        logger.info(f"[COPY] User nodes copied for {target_owner}")

        # Step 3 – copy Message nodes (bulk, no FOREACH workaround needed in Neo4j 5+)
        await session.run(
            """
            MATCH (src_ch:Channel {username: $username, owner_id: $source_owner})
                  -[:HAS_MESSAGE]->(m_src:Message {owner_id: $source_owner})
            MATCH (tgt_ch:Channel {username: $username, owner_id: $target_owner})
            MERGE (m_tgt:Message {mid: m_src.mid, owner_id: $target_owner})
            ON CREATE SET
                m_tgt.date                       = m_src.date,
                m_tgt.original_text              = m_src.original_text,
                m_tgt.original_language          = m_src.original_language,
                m_tgt.translated_text            = m_src.translated_text,
                m_tgt.translation_status         = m_src.translation_status,
                m_tgt.media_type                 = m_src.media_type,
                m_tgt.media_path                 = m_src.media_path,
                m_tgt.image_text                 = m_src.image_text,
                m_tgt.image_text_translated      = m_src.image_text_translated,
                m_tgt.image_analysis_status      = m_src.image_analysis_status,
                m_tgt.image_detected_language    = m_src.image_detected_language,
                m_tgt.audio_text                 = m_src.audio_text,
                m_tgt.audio_text_translated      = m_src.audio_text_translated,
                m_tgt.audio_transcription_status = m_src.audio_transcription_status,
                m_tgt.audio_language             = m_src.audio_language,
                m_tgt.geolocation_status         = m_src.geolocation_status,
                m_tgt.emotion_status             = m_src.emotion_status,
                m_tgt.classification_status      = m_src.classification_status
            MERGE (tgt_ch)-[:HAS_MESSAGE]->(m_tgt)
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )
        logger.info(f"[COPY] Message nodes copied for {target_owner}")

        # Step 4 – attach sender (User→Message SENT relationship)
        await session.run(
            """
            MATCH (src_ch:Channel {username: $username, owner_id: $source_owner})
                  -[:HAS_MESSAGE]->(m_src:Message {owner_id: $source_owner})
            OPTIONAL MATCH (u_src:User {owner_id: $source_owner})-[:SENT]->(m_src)
            MATCH (m_tgt:Message {mid: m_src.mid, owner_id: $target_owner})
            WITH m_tgt, u_src
            WHERE u_src IS NOT NULL
            MATCH (u_tgt:User {user_id: u_src.user_id, owner_id: $target_owner})
            MERGE (u_tgt)-[:SENT]->(m_tgt)
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )

        # Step 5 – copy REPLY_TO chains (both endpoints already exist at this point)
        await session.run(
            """
            MATCH (src_ch:Channel {username: $username, owner_id: $source_owner})
                  -[:HAS_MESSAGE]->(m_src:Message {owner_id: $source_owner})
                  -[:REPLY_TO]->(r_src:Message {owner_id: $source_owner})
            MATCH (m_tgt:Message {mid: m_src.mid, owner_id: $target_owner})
            MATCH (r_tgt:Message {mid: r_src.mid, owner_id: $target_owner})
            MERGE (m_tgt)-[:REPLY_TO]->(r_tgt)
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )

        # Step 6 – copy enrichment relationships (Emotion / Classification / Location)
        # These nodes (Emotion, Classification, Location) are shared singletons —
        # they carry no owner_id — so we just re-attach the relationships.
        await session.run(
            """
            MATCH (src_ch:Channel {username: $username, owner_id: $source_owner})
                  -[:HAS_MESSAGE]->(m_src:Message {owner_id: $source_owner})
                  -[r_src:HAS_EMOTION]->(e:Emotion)
            MATCH (m_tgt:Message {mid: m_src.mid, owner_id: $target_owner})
            MERGE (m_tgt)-[r_tgt:HAS_EMOTION]->(e)
            ON CREATE SET r_tgt = r_src
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )
        await session.run(
            """
            MATCH (src_ch:Channel {username: $username, owner_id: $source_owner})
                  -[:HAS_MESSAGE]->(m_src:Message {owner_id: $source_owner})
                  -[r_src:HAS_CLASSIFICATION]->(cl)
            MATCH (m_tgt:Message {mid: m_src.mid, owner_id: $target_owner})
            MERGE (m_tgt)-[r_tgt:HAS_CLASSIFICATION]->(cl)
            ON CREATE SET r_tgt = r_src
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )
        await session.run(
            """
            MATCH (src_ch:Channel {username: $username, owner_id: $source_owner})
                  -[:HAS_MESSAGE]->(m_src:Message {owner_id: $source_owner})
                  -[:MENTIONS_LOCATION]->(l:Location)
            MATCH (m_tgt:Message {mid: m_src.mid, owner_id: $target_owner})
            MERGE (m_tgt)-[:MENTIONS_LOCATION]->(l)
            """,
            username=username,
            source_owner=source_owner,
            target_owner=target_owner,
        )
        logger.info(f"[COPY] Enrichment relationships copied for {target_owner}")

        # Return count of messages that now exist for target_owner in this channel
        count_rec = await (
            await session.run(
                """
                MATCH (c:Channel {username: $username, owner_id: $target_owner})
                      -[:HAS_MESSAGE]->(m:Message {owner_id: $target_owner})
                RETURN count(m) AS n
                """,
                username=username,
                target_owner=target_owner,
            )
        ).single()
        return count_rec["n"] if count_rec else 0


@_with_constraints
async def get_scraped_recommended_channels(root_username: str, source_owner: str) -> list[str]:
    """
    Walk the RECOMMENDS graph from root_username (owned by source_owner) and
    return the usernames of all channels that have been fully scraped by that owner.
    Only follows channels that have scraped=true so we don't waste time on stubs.
    """
    async with get_driver().session() as session:
        result = await session.run(
            """
            MATCH (root:Channel {username: $username, owner_id: $source_owner, scraped: true})
                  -[:RECOMMENDS*1..]->(rec:Channel {owner_id: $source_owner, scraped: true})
            WHERE rec.username IS NOT NULL
            RETURN DISTINCT rec.username AS username
            """,
            username=root_username,
            source_owner=source_owner,
        )
        return [r["username"] async for r in result]


@_with_constraints
async def copy_recommended_channels_for_owner(
    root_username: str, source_owner: str, target_owner: str
) -> dict:
    """
    Copy all scraped channels reachable via RECOMMENDS from root_username
    (source_owner) to target_owner, then replicate the RECOMMENDS edges.

    Returns a dict {username: message_count} for each channel copied.
    """
    child_usernames = await get_scraped_recommended_channels(root_username, source_owner)
    results = {}
    for username in child_usernames:
        try:
            n = await copy_channel_for_owner(username, source_owner, target_owner)
            results[username] = n
            logger.info(f"[COPY-REC] {username}: {n} messages copied to {target_owner}")
        except Exception as e:
            logger.warning(f"[COPY-REC] Failed to copy {username}: {e}")
            results[username] = 0

    # Replicate RECOMMENDS edges for all copied channels
    if child_usernames:
        async with get_driver().session() as session:
            await session.run(
                """
                MATCH (src:Channel {owner_id: $source_owner})-[:RECOMMENDS]->(rec:Channel {owner_id: $source_owner})
                WHERE src.username IN $all_usernames AND rec.username IN $all_usernames
                MATCH (tgt_src:Channel {username: src.username, owner_id: $target_owner})
                MATCH (tgt_rec:Channel {username: rec.username, owner_id: $target_owner})
                MERGE (tgt_src)-[:RECOMMENDS]->(tgt_rec)
                """,
                source_owner=source_owner,
                target_owner=target_owner,
                all_usernames=[root_username] + child_usernames,
            )
    return results