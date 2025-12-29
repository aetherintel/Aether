import os
from contextlib import asynccontextmanager
from typing import AsyncIterator
from neo4j import AsyncGraphDatabase
from neo4j.time import DateTime as Neo4jDateTime
from dotenv import load_dotenv

load_dotenv()

driver = AsyncGraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD"))
)

def convert_neo4j_datetime(value):
    """Convert Neo4j DateTime to Python datetime"""
    if isinstance(value, Neo4jDateTime):
        return value.to_native()
    return value

@asynccontextmanager
async def get_session(owner_id: str | None) -> AsyncIterator:
    """
    If owner_id is None (admin), returns the bare driver session.
    Otherwise wraps it so every .run(...) automatically receives $ownerId.
    """
    async with driver.session() as s:
        if owner_id is None:
            yield s
        else:
            yield _FilteredSession(s, owner_id)

class _FilteredSession:
    def __init__(self, sess, owner):
        self.sess, self.owner = sess, owner

    async def run(self, cypher: str, parameters: dict | None = None, **kw):
        p = parameters.copy() if parameters else {}
        p.setdefault("ownerId", self.owner)
        return await self.sess.run(cypher, p, **kw)

    def __getattr__(self, name):
        return getattr(self.sess, name)

async def close():
    await driver.close()
