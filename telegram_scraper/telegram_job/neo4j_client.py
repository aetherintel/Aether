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

    MERGE (u:User {user_id:$uid, owner_id:$owner})
      ON CREATE SET u.first_name=$fname, u.last_name=$lname, u.username=$uusername

    MERGE (m:Message {mid:$mid, owner_id:$owner})
      ON CREATE SET m.date=datetime($date), m.text=$text,
                    m.media_type=$mtype, m.media_path=$mpath

    // Simplified relationships - NO owner_id properties
    MERGE (ch)-[:HAS_MESSAGE]->(m)
    MERGE (u)-[:SENT]->(m)
    MERGE (u)-[:PART_OF]->(ch)

    FOREACH (_ IN CASE WHEN $reply_to IS NOT NULL THEN [1] ELSE [] END |
        MERGE (rm:Message {mid:$cid + "-" + $reply_to, owner_id:$owner})
        MERGE (m)-[:REPLY_TO]->(rm)
    )
    """
    await tx.run(
        cypher,
        owner=OWNER_ID,
        cid=str(channel_id),
        uname=username,
        uid=sender.id or None,
        fname=getattr(sender, "first_name", None),
        lname=getattr(sender, "last_name", None),
        uusername=getattr(sender, "username", None),
        mid=f"{channel_id}-{message.id}",
        date=message.date.isoformat(),
        text=message.message,
        mtype=message.media.__class__.__name__ if message.media else None,
        mpath=media_path,
        reply_to=message.reply_to_msg_id,
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