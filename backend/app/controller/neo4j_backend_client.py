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