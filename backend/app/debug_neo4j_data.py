import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.neo4j_backend_client import get_session, driver

async def debug_neo4j():
    print("--- Starting Neo4j Debug ---")
    
    async with get_session(None) as session:
        # 1. Check Total Messages
        result = await session.run("MATCH (m:Message) RETURN count(m) as count")
        total = (await result.single())["count"]
        print(f"Total Messages in DB: {total}")
        
        if total == 0:
            print("No messages found. Aborting.")
            return

        # 2. Check Date Format
        result = await session.run("MATCH (m:Message) WHERE m.date IS NOT NULL RETURN m.date as date, m.text as text LIMIT 1")
        record = await result.single()
        if record:
            date_val = record["date"]
            text_val = record.get("text", "No Text")
            print(f"Sample Message Date: {date_val} (Type: {type(date_val)})")
            if text_val:
                print(f"Sample Text: {text_val[:50]}...")
        else:
            print("No messages with date found.")
            
        # 2b. Check Min/Max Date
        result = await session.run("MATCH (m:Message) RETURN min(m.date) as min_date, max(m.date) as max_date")
        record = await result.single()
        print(f"Data Range: {record['min_date']} to {record['max_date']}")
        
        # 2c. Check Owner IDs
        print("\nChecking Owner IDs:")
        result = await session.run("MATCH (m:Message) RETURN m.owner_id as owner, count(m) as count")
        print("Messages per Owner:")
        async for r in result:
            print(f" - {r['owner']}: {r['count']}")
            
        result = await session.run("MATCH (c:Channel) RETURN c.owner_id as owner, count(c) as count")
        print("Channels per Owner:")
        async for r in result:
            print(f" - {r['owner']}: {r['count']}")
            
        # 2d. Check Channel-Message Owner Consistency
        print("\nChecking Channel-Message Owner Consistency:")
        result = await session.run("""
            MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)
            RETURN ch.owner_id as ch_owner, m.owner_id as msg_owner, count(*) as count
        """)
        async for r in result:
            print(f" - Ch: {r['ch_owner']} -> Msg: {r['msg_owner']} : {r['count']}")

        # 3. Check Messages in last 30 days (Monthly Test)
        from datetime import timezone
        now = datetime.now(timezone.utc)
        month_ago = now - timedelta(days=30)
        print(f"\nChecking for messages between {month_ago} and {now} (Monthly - UTC)")
        
        cypher = """
        MATCH (ch:Channel)-[:HAS_MESSAGE]->(m:Message)
        WHERE m.date >= $startDate AND m.date <= $endDate
        RETURN count(m) as count
        """
        params = {
            "startDate": month_ago,
            "endDate": now
        }
        
        try:
            result = await session.run(cypher, params)
            count = (await result.single())["count"]
            print(f"Query (Monthly) returned: {count}")
        except Exception as e:
            print(f"Query failed: {e}")
            
    await driver.close()

if __name__ == "__main__":
    asyncio.run(debug_neo4j())
