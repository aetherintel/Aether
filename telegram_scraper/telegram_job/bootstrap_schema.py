# telegram_job/bootstrap_schema.py
from pathlib import Path
from neo4j_client import driver

SCHEMA_FILE = Path(__file__).parents[1] / "neo4j" / "schema.cypher"

async def ensure_schema():
    statements = [
        stmt.strip() for stmt in SCHEMA_FILE.read_text().split(";") if stmt.strip()
    ]
    async with driver.session() as s:
        for stmt in statements:
            await s.run(stmt)
