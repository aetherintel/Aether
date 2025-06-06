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
        RETURN 
            ch.username as username,
            ch.title as title,
            count(m) as message_count,  
            max(m.date) as last_message_date
        ORDER BY last_message_date DESC
        """
        result = await session.run(query)
        channels = []
        async for record in result:
            channels.append({
                "username": record["username"],
                "title": record["title"],
                "message_count": record["message_count"],
                "last_message": record["last_message_date"]
            })
        return channels

async def get_messages_for_channel(channel_id: str, limit: int = 100):
    async with driver.session() as session:
        query = """
        MATCH (ch:Channel {channel_id: $channel_id})-[:HAS_MESSAGE]->(m:Message)<-[:SENT]-(u:User)
        RETURN 
            m.text as text,
            m.date as date,
            m.media_type as media_type,
            u.username as username,
            u.first_name as first_name,
            u.last_name as last_name,
            ch.username as channel_name
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
                "text": record["text"],
                "date": record["date"],
                "media_type": record["media_type"],
                "author": author_name,
                "channel": record["channel_name"]
            })
        return messages