# telegram_job/neo4j_client.py
import os
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv
from utils import download_media
load_dotenv()

driver = AsyncGraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD"))
)

async def close():
    await driver.close()

async def save_message(channel_id, username, message, sender,  media_path=None):
    async with driver.session() as session:
        await session.execute_write(_save_message, channel_id, username, message, sender, media_path)
async def _save_message(tx, channel_id, username, message, sender,  media_path):
    cypher = """
    MERGE (ch:Channel {channel_id: $cid})
    ON CREATE SET ch.username = $uname

    MERGE (u:User {user_id: $uid})
    ON CREATE SET u.first_name=$fname, u.last_name=$lname, u.username=$uusername

    MERGE (m:Message {mid: $cid + "-" + $mid})
    ON CREATE SET m.date=$date, m.text=$text, m.media_type=$mtype, m.media_path=$mpath

    MERGE (ch)-[:HAS_MESSAGE]->(m)
    MERGE (u)-[:SENT]->(m)
    MERGE (u)-[:PART_OF]->(ch)

    FOREACH (_ IN CASE WHEN $reply_to IS NOT NULL THEN [1] ELSE [] END |
        MERGE (rm:Message {mid: $cid + "-" + $reply_to})
        MERGE (m)-[:REPLY_TO]->(rm)
        )

    """
    await tx.run(
        cypher,
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
        reply_to=message.reply_to_msg_id
    )


async def write_recommendations(root, recs):
    async with driver.session() as s:
        print(f"Writing recommendations for {root}...")
        print(f"Recommendations: {recs}")
        for r in recs:
            await s.run("""
                MERGE (root:Channel {channel_id: $root_id})
                ON CREATE SET root.username = $root_username,
                              root.title = $root_title

                MERGE (rec:Channel {channel_id: $rec_id})
                SET rec.username = $rec_username,
                              rec.title = $rec_title

                MERGE (root)-[:RECOMMENDS]->(rec)
            """, 
            root_id=root,
            root_username=None,       # Optionally fetch via get_entity() if needed
            root_title=None,          # Optionally fetch via get_entity() if needed
            rec_id=r["id"],
            rec_username=r.get("username"),
            rec_title=r.get("title"))

async def is_scraped(username: str) -> bool:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (c:Channel {username: $username})-[:HAS_MESSAGE]->(:Message)
            RETURN count(*) > 0 AS scraped
            """,
            username=username
        )
        record = await result.single()
        return record and record["scraped"]



async def mark_scraped(username: str):
    async with driver.session() as session:
        await session.run(
            """
            MERGE (c:Channel {username: $username})
            SET c.scraped = true, c.scraped_at = timestamp()
            """,
            username=username
        )

async def message_exists(channel_id, message_id):
    full_mid = f"{channel_id}-{message_id}"
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:Message {mid: $mid})
            RETURN count(m) > 0 AS exists
            """,
            mid=full_mid
        )
        record = await result.single()
        return record and record["exists"]

async def save_message_if_new(channel_id, username, message, sender, media_path=None):
    if await message_exists(channel_id, message.id):
        print(f"[SKIP] Message {message.id} already exists in Neo4j")
        return
    await save_message(channel_id, username, message, sender, media_path)
