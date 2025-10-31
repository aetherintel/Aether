# telegram_job/neo4j_client.py
import os, asyncio
from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ConstraintError
from dotenv import load_dotenv
load_dotenv()

OWNER_ID = os.getenv("OWNER_ID") or "unknown"

# --------------------------------------------------------------------------
#  1. lazy driver – one per event-loop
# --------------------------------------------------------------------------
_driver: AsyncDriver | None = None                # module-global, loop-local


def _get_driver() -> AsyncDriver:
    """
    Create (or reuse) the Neo4j driver in the *current* event-loop.
    """
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
        )
    return _driver


async def close() -> None:
    """
    Call once at shutdown.
    """
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


# --------------------------------------------------------------------------
#  2. ensure constraints – run once in the same loop that uses the driver
# --------------------------------------------------------------------------
_CONSTRAINTS_DONE = asyncio.Event()


async def _ensure_constraints_once() -> None:
    if _CONSTRAINTS_DONE.is_set():
        return
    async with _get_driver().session() as s:
        try:
            await s.run("""
              CREATE CONSTRAINT channel_owner_unique IF NOT EXISTS
              FOR (c:Channel)
              REQUIRE (c.channel_id, c.owner_id) IS UNIQUE
            """)
            await s.run("""
              CREATE CONSTRAINT message_owner_unique IF NOT EXISTS
              FOR (m:Message)
              REQUIRE (m.mid, m.owner_id) IS UNIQUE
            """)
            await s.run("""
              CREATE CONSTRAINT user_owner_unique IF NOT EXISTS
              FOR (u:User)
              REQUIRE (u.user_id, u.owner_id) IS UNIQUE
            """)
        except ConstraintError as e:
            # parallel start-up; someone else is creating them – fine
            print("[WARN] constraint creation race:", e)
    _CONSTRAINTS_DONE.set()


# helper decorator to make sure constraints exist before any write/read
def _with_constraints(fn):
    async def wrapper(*a, **kw):
        await _ensure_constraints_once()
        return await fn(*a, **kw)
    return wrapper


# --------------------------------------------------------------------------
#  3.  all public helper functions – SIMPLIFIED (no owner_id on relationships)
# --------------------------------------------------------------------------

@_with_constraints
async def save_message(channel_id, username, message, sender, media_path=None):
    async with _get_driver().session() as session:
        await session.execute_write(
            _save_message, channel_id, username, message, sender, media_path
        )


async def _save_message(tx, channel_id, username, message, sender, media_path):
    cypher = """
    MERGE (ch:Channel {channel_id:$cid, owner_id:$owner})
    ON CREATE SET ch.username = $uname
    
    // Create message first
    MERGE (m:Message {mid:$mid, owner_id:$owner})
    ON CREATE SET m.date=datetime($date), m.original_text=$text,
                  m.media_type=$mtype, m.media_path=$mpath
    
    // Always create channel-message relationship
    MERGE (ch)-[:HAS_MESSAGE]->(m)
    
    // Only create user and relationships if sender exists
    FOREACH (_ IN CASE WHEN $uid IS NOT NULL THEN [1] ELSE [] END |
        MERGE (u:User {user_id:$uid, owner_id:$owner})
        ON CREATE SET u.first_name=$fname, u.last_name=$lname, u.username=$uusername
        MERGE (u)-[:SENT]->(m)
        MERGE (u)-[:PART_OF]->(ch)
    )
    
    // Handle reply relationships
    FOREACH (_ IN CASE WHEN $reply_to IS NOT NULL THEN [1] ELSE [] END |
        MERGE (rm:Message {mid:$reply_to_mid, owner_id:$owner})
        MERGE (m)-[:REPLY_TO]->(rm)
    )
    """
    
    # Safely extract sender information
    sender_id = None
    first_name = None
    last_name = None
    sender_username = None
    
    if sender is not None:
        sender_id = getattr(sender, 'id', None)
        first_name = getattr(sender, 'first_name', None)
        last_name = getattr(sender, 'last_name', None)
        sender_username = getattr(sender, 'username', None)
    
    # Handle reply_to_msg_id
    reply_to_mid = None
    if message.reply_to_msg_id:
        reply_to_mid = f"{channel_id}-{message.reply_to_msg_id}"
    
    await tx.run(
        cypher,
        owner=OWNER_ID,
        cid=str(channel_id),
        uname=username,
        uid=sender_id,
        fname=first_name,
        lname=last_name,
        uusername=sender_username,
        mid=f"{channel_id}-{message.id}",
        date=message.date.isoformat(),
        text=message.message or "",  # Handle None message text
        mtype=message.media.__class__.__name__ if message.media else None,
        mpath=media_path,
        reply_to=message.reply_to_msg_id,
        reply_to_mid=reply_to_mid,
    )


@_with_constraints
async def write_recommendations(root, recs):
    async with _get_driver().session() as s:
        for r in recs:
            await s.run(
                """
                MERGE (root:Channel {channel_id:$root_id, owner_id:$owner})
                  SET root.username=$root_username, root.title=$root_title

                MERGE (rec:Channel {channel_id:$rec_id, owner_id:$owner})
                  SET rec.username=$rec_username, rec.title=$rec_title

                // Simplified relationship - NO owner_id property
                MERGE (root)-[:RECOMMENDS]->(rec)
                """,
                owner=OWNER_ID,
                root_id=root,
                root_username=None,
                root_title=None,
                rec_id=r["id"],
                rec_username=r.get("username"),
                rec_title=r.get("title"),
            )


@_with_constraints
async def is_scraped(username: str) -> bool:
    async with _get_driver().session() as session:
        rec = await (
            await session.run(
                """
                MATCH (c:Channel {username:$username, owner_id:$owner})
                      -[:HAS_MESSAGE]->(:Message)
                RETURN count(*) > 0 AS scraped
                """,
                username=username,
                owner=OWNER_ID,
            )
        ).single()
        return rec and rec["scraped"]


@_with_constraints
async def mark_scraped(username: str):
    async with _get_driver().session() as session:
        await session.run(
            """
            MERGE (c:Channel {username:$username, owner_id:$owner})
            SET   c.scraped=true, c.scraped_at=timestamp()
            """,
            username=username,
            owner=OWNER_ID,
        )


@_with_constraints
async def message_exists(channel_id, message_id):
    full_mid = f"{channel_id}-{message_id}"
    async with _get_driver().session() as session:
        rec = await (
            await session.run(
                """
                MATCH (m:Message {mid:$mid, owner_id:$owner})
                RETURN count(m) > 0 AS exists
                """,
                mid=full_mid,
                owner=OWNER_ID,
            )
        ).single()
        return rec and rec["exists"]


@_with_constraints
async def save_message_if_new(channel_id, username, message, sender, media_path=None):
    if await message_exists(channel_id, message.id):
        print(f"[SKIP] Message {message.id} already exists in Neo4j")
        return
    await save_message(channel_id, username, message, sender, media_path)

# telegram_job/neo4j_client.py
# ADD THESE FUNCTIONS to your existing neo4j_client.py

@_with_constraints
async def save_message_with_translation(
    channel_id, 
    username, 
    message, 
    sender, 
    media_path=None,
    original_language=None,
    translation_status='none'
):
    """
    Save message with translation fields
    Stores original_text and sets up for later translation
    """
    async with _get_driver().session() as session:
        await session.execute_write(
            _save_message_with_translation,
            channel_id,
            username,
            message,
            sender,
            media_path,
            original_language,
            translation_status
        )


async def _save_message_with_translation(
    tx, 
    channel_id, 
    username, 
    message, 
    sender, 
    media_path,
    original_language,
    translation_status
):
    """Internal transaction for saving message with translation metadata"""
    cypher = """
    MERGE (ch:Channel {channel_id:$cid, owner_id:$owner})
    ON CREATE SET ch.username = $uname
    
    // Create message with translation fields
    MERGE (m:Message {mid:$mid, owner_id:$owner})
    ON CREATE SET 
        m.date = datetime($date),
        m.original_text = $original_text,
        m.translated_text = $translated_text,
        m.original_language = $original_language,
        m.translation_status = $translation_status,
        m.media_type = $mtype,
        m.media_path = $mpath
    
    // Always create channel-message relationship
    MERGE (ch)-[:HAS_MESSAGE]->(m)
    
    // Handle sender if exists
    FOREACH (_ IN CASE WHEN $uid IS NOT NULL THEN [1] ELSE [] END |
        MERGE (u:User {user_id:$uid, owner_id:$owner})
        ON CREATE SET 
            u.first_name = $fname,
            u.last_name = $lname,
            u.username = $uusername
        MERGE (u)-[:SENT]->(m)
        MERGE (u)-[:PART_OF]->(ch)
    )
    
    // Handle reply relationships
    FOREACH (_ IN CASE WHEN $reply_to IS NOT NULL THEN [1] ELSE [] END |
        MERGE (rm:Message {mid:$reply_to_mid, owner_id:$owner})
        MERGE (m)-[:REPLY_TO]->(rm)
    )
    """
    
    # Extract text
    text = message.message or ""
    
    # Determine translated_text (if already German, it's the same)
    translated_text = text if original_language == 'de' else None
    
    # Extract sender info safely
    sender_id = getattr(sender, 'id', None) if sender else None
    first_name = getattr(sender, 'first_name', None) if sender else None
    last_name = getattr(sender, 'last_name', None) if sender else None
    sender_username = getattr(sender, 'username', None) if sender else None
    
    # Handle reply
    reply_to_mid = None
    if message.reply_to_msg_id:
        reply_to_mid = f"{channel_id}-{message.reply_to_msg_id}"
    
    await tx.run(
        cypher,
        owner=OWNER_ID,
        cid=str(channel_id),
        uname=username,
        uid=sender_id,
        fname=first_name,
        lname=last_name,
        uusername=sender_username,
        mid=f"{channel_id}-{message.id}",
        date=message.date.isoformat(),
        original_text=text,
        translated_text=translated_text,
        original_language=original_language or 'unknown',
        translation_status=translation_status,
        mtype=message.media.__class__.__name__ if message.media else None,
        mpath=media_path,
        reply_to=message.reply_to_msg_id,
        reply_to_mid=reply_to_mid,
    )


@_with_constraints
async def update_message_translation(message_id: str, translated_text: str):
    """
    Update message with translated text
    Called by translation worker after translation completes
    
    Args:
        message_id: Full message ID (e.g., "123456-789")
        translated_text: German translation
    """
    async with _get_driver().session() as session:
        result = await session.run(
            """
            MATCH (m:Message {mid: $mid, owner_id: $owner})
            SET m.translated_text = $translated_text,
                m.translation_status = 'completed',
                m.translated_at = datetime()
            RETURN m.mid as mid
            """,
            mid=message_id,
            translated_text=translated_text,
            owner=OWNER_ID,
        )
        record = await result.single()
        if record:
            print(f"[Neo4j] ✓ Updated translation for message {message_id}")
            return True
        else:
            print(f"[Neo4j] ✗ Message {message_id} not found")
            return False


@_with_constraints
async def get_messages_for_translation(owner_id: str, limit: int = 100):
    """
    Get messages that need translation
    
    Returns list of (message_id, original_text, original_language)
    """
    async with _get_driver().session() as session:
        result = await session.run(
            """
            MATCH (m:Message {owner_id: $owner})
            WHERE m.original_language IN ['ru', 'ar', 'tr']
              AND (m.translation_status = 'pending' OR m.translation_status = 'none')
              AND m.original_text IS NOT NULL
            RETURN m.mid as mid, m.original_text as text, m.original_language as lang
            LIMIT $limit
            """,
            owner=owner_id,
            limit=limit,
        )
        
        messages = []
        async for record in result:
            messages.append((
                record['mid'],
                record['text'],
                record['lang']
            ))
        
        return messages


@_with_constraints
async def mark_translation_pending(message_id: str):
    """Mark message as pending translation"""
    async with _get_driver().session() as session:
        await session.run(
            """
            MATCH (m:Message {mid: $mid, owner_id: $owner})
            SET m.translation_status = 'pending'
            """,
            mid=message_id,
            owner=OWNER_ID,
        )


@_with_constraints
async def mark_translation_failed(message_id: str, error: str = None):
    """Mark message translation as failed"""
    async with _get_driver().session() as session:
        await session.run(
            """
            MATCH (m:Message {mid: $mid, owner_id: $owner})
            SET m.translation_status = 'failed',
                m.translation_error = $error
            """,
            mid=message_id,
            error=error,
            owner=OWNER_ID,
        )