# lib/neo4j/channels.py
"""
Neo4j operations for channels
"""
from .connection import get_driver, _with_constraints, get_owner_id


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
                MERGE (root:Channel {channel_id:$root_id, owner_id:$owner})
                  SET root.username=$root_username, root.title=$root_title

                MERGE (rec:Channel {channel_id:$rec_id, owner_id:$owner})
                  SET rec.username=$rec_username, rec.title=$rec_title

                MERGE (root)-[:RECOMMENDS]->(rec)
                """,
                owner=owner,
                root_id=root,
                root_username=None,
                root_title=None,
                rec_id=r["id"],
                rec_username=r.get("username"),
                rec_title=r.get("title"),
            )