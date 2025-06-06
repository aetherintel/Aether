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

async def get_channel_list():
    async with driver.session() as session:
        query = """
        MATCH (ch:Channel)
        OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        WITH ch, count(m) as msg_count, max(m.date) as latest
        OPTIONAL MATCH (other)-[:RECOMMENDS]->(ch)
        RETURN 
            ch.channel_id as channel_id,
            ch.username as username,
            ch.title as title,
            msg_count as message_count,
            latest as last_message_date,
            count(other) as recommended_by,
            ch.scraped as is_scraped,
            ch.scraped_at as scraped_at
        ORDER BY last_message_date DESC
        """
        result = await session.run(query)
        channels = []
        async for record in result:
            channels.append({
                "channel_id": record["channel_id"],
                "username": record["username"],
                "title": record["title"],
                "message_count": record["message_count"],
                "last_active": record["last_message_date"],
                "recommended_by": record["recommended_by"],
                "is_scraped": record["is_scraped"],
                "scraped_at": record["scraped_at"]
            })
        return channels

async def get_messages_for_channel(channel_id: str, limit: int = 100):
    async with driver.session() as session:
        query = """
        MATCH (ch:Channel {channel_id: $channel_id})-[:HAS_MESSAGE]->(m:Message)<-[:SENT]-(u:User)
        OPTIONAL MATCH (m)-[:REPLY_TO]->(reply:Message)
        RETURN 
            m.text as text,
            m.date as date,
            m.media_type as media_type,
            m.mid as message_id,
            u.user_id as user_id,
            u.username as username,
            u.first_name as first_name,
            u.last_name as last_name,
            ch.channel_id as channel_id,
            ch.username as channel_username,
            reply.mid as reply_to_id
        ORDER BY m.date DESC
        LIMIT $limit
        """
        result = await session.run(query,
                                 channel_id=str(channel_id),
                                 limit=limit)
        messages = []
        async for record in result:
            author_name = record["username"] or f"{record['first_name'] or ''} {record['last_name'] or ''}".strip() or "Unknown"
            messages.append({
                "message_id": record["message_id"],
                "text": record["text"],
                "date": record["date"],
                "media_type": record["media_type"],
                "reply_to_id": record["reply_to_id"],
                "author": {
                    "id": record["user_id"],
                    "name": author_name
                },
                "channel": {
                    "id": record["channel_id"],
                    "username": record["channel_username"]
                }
            })
        return messages

async def get_channel_by_id(channel_id: str):
    async with driver.session() as session:
        query = """
        MATCH (ch:Channel {channel_id: $channel_id})
        OPTIONAL MATCH (ch)-[:HAS_MESSAGE]->(m:Message)
        OPTIONAL MATCH (ch)-[:RECOMMENDS]->(rec:Channel)
        OPTIONAL MATCH (other:Channel)-[:RECOMMENDS]->(ch)
        RETURN 
            ch.channel_id as channel_id,
            ch.username as username,
            ch.title as title,
            count(DISTINCT m) as message_count,
            min(m.date) as first_message,
            max(m.date) as last_message,
            count(DISTINCT rec) as recommends_count,
            count(DISTINCT other) as recommended_by_count,
            ch.scraped as is_scraped,
            ch.scraped_at as scraped_at
        """
        result = await session.run(query, channel_id=str(channel_id))
        record = await result.single()
        if record:
            return {
                "channel_id": record["channel_id"],
                "username": record["username"],
                "title": record["title"],
                "message_count": record["message_count"],
                "first_message": record["first_message"],
                "last_message": record["last_message"]
            }
        return None