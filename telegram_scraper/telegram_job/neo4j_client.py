# telegram_job/neo4j_client.py
import os
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

driver = AsyncGraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD"))
)

async def close():
    await driver.close()

async def _save_message(tx, channel_id, message, sender):
    cypher = """
    MERGE (ch:Channel {channel_id:$cid})
    MERGE (u:User {user_id:$uid})
      ON CREATE SET u.first_name=$fname, u.last_name=$lname, u.username=$uusername
    MERGE (m:Message {message_id:$mid})
      ON CREATE SET m.date=$date, m.text=$text,
                    m.media_type=$mtype
    MERGE (ch)-[:HAS_MESSAGE]->(m)
    MERGE (u)-[:SENT]->(m)
    FOREACH (_ IN CASE WHEN $reply_to IS NOT NULL THEN [1] ELSE [] END |
      MERGE (rm:Message {message_id:$reply_to})
      MERGE (m)-[:REPLY_TO]->(rm)
    )
    """
    await tx.run(
        cypher,
        cid=str(channel_id),
        uid=sender.id,
        fname=getattr(sender, "first_name", None),
        lname=getattr(sender, "last_name", None),
        uusername=getattr(sender, "username", None),
        mid=message.id,
        date=message.date.isoformat(),
        text=message.message,
        mtype=message.media.__class__.__name__ if message.media else None,
        reply_to=message.reply_to_msg_id
    )

async def save_message(channel_id, message, sender):
    async with driver.session() as session:
        await session.execute_write(_save_message, channel_id, message, sender)

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

