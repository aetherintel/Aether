"""
Neo4j 6.x async connection helper for Aether
Compatible with asyncio + neo4j>=6.0
"""

import asyncio
import os
import logging
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ConstraintError
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment and globals
# ---------------------------------------------------------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

_owner_id: ContextVar[str] = ContextVar('owner_id', default='default_owner')

def set_owner_id(owner_id: str):
    """Set owner_id for current context"""
    _owner_id.set(owner_id)

def get_owner_id() -> str:
    """Get owner_id from current context"""
    return _owner_id.get()

_driver = None
_CONSTRAINTS_DONE = None # Initialized lazily

# ---------------------------------------------------------------------------
# Driver lifecycle
# ---------------------------------------------------------------------------
async def init_driver():
    """
    Initialize the global Neo4j async driver.
    This should be awaited once on startup.
    """
    global _driver, _CONSTRAINTS_DONE
    
    # Initialize implementation of Event lazily 
    if _CONSTRAINTS_DONE is None:
        _CONSTRAINTS_DONE = asyncio.Event()
    if _driver is not None:
        return _driver

    try:
        _driver = AsyncGraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        await _driver.verify_connectivity()
        logger.info(f"✅ Connected to Neo4j at {NEO4J_URI}")
        print(f"[NEO4J] ✅ Connected to Neo4j at {NEO4J_URI}", flush=True)
        return _driver
    except Exception as e:
        logger.error(f"❌ Could not connect to Neo4j: {e}")
        print(f"[NEO4J] ❌ Could not connect to Neo4j: {e}", flush=True)
        raise

def get_driver():
    """Return the global async driver. Must have been initialized already."""
    global _driver
    if _driver is None:
        raise RuntimeError("Neo4j driver not initialized. Call await init_driver() first.")
    return _driver


async def close_driver():
    """Cleanly close the global driver."""
    global _driver
    if _driver:
        await _driver.close()
        logger.info("🔌 Neo4j driver closed")
        _driver = None

# ---------------------------------------------------------------------------
# Constraint management
# ---------------------------------------------------------------------------
def _with_constraints(fn):
    """Decorator: ensure constraints exist before running the wrapped function."""
    async def wrapper(*a, **kw):
        await _ensure_constraints_once()
        return await fn(*a, **kw)
    return wrapper

async def _ensure_constraints_once() -> None:
    """Create uniqueness constraints exactly once per process."""
    if _CONSTRAINTS_DONE.is_set():
        return

    driver = get_driver()
    async with driver.session() as s:
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
            logger.warning(f"[WARN] Constraint creation race: {e}")

    _CONSTRAINTS_DONE.set()
    logger.info("✅ Neo4j constraints ensured.")


def run_in_neo4j_loop(coro_func, *args, owner_id: str = None, **kwargs):
    """
    Simple helper to run async Neo4j operations from sync context.
    """
    logger.info(f"🔍 [NEO4J] Entering run_in_neo4j_loop with {coro_func.__name__}")
    
    async def _execute():
        # Set owner_id in context if provided
        if owner_id:
            set_owner_id(owner_id)
        
        logger.info(f"🔍 [NEO4J] Creating driver connection...")
        driver = AsyncGraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        logger.info(f"✅ [NEO4J] Driver created, owner_id={get_owner_id()}")
        
        try:
            result = await coro_func(driver, *args, **kwargs)
            logger.info(f"✅ [NEO4J] Operation completed, result: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ [NEO4J] Exception: {e}")
            raise
        finally:
            await driver.close()
    
    return asyncio.run(_execute())
