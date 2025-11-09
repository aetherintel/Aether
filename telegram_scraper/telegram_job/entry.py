
import os, json, sys, asyncio

# GEÄNDERT: Relative Imports verwenden
from .similar import similar_channels_flexible as similar_channels
from .scraper import run_scraper, run_live_listener_only
from aether_lib.neo4j_client.channels import write_recommendations, is_scraped
from aether_lib.neo4j_client.connection import init_driver, close_driver
from .telegram_client import login

# ========================================
# NEU: RQ Worker Entry Point
# ========================================
def run_job(**kwargs):
    """
    Entry point für RQ Worker.
    """
    print(f"[RQ] Starting job with kwargs: {kwargs}")

    owner_id = kwargs.get('owner_id', 'unknown')
    case_id = kwargs.get('case_id')

    # Setze ENV-Variablen aus kwargs
    os.environ['MODE'] = kwargs.get('mode', 'scrape')
    os.environ['CHANNELS'] = ','.join(kwargs.get('channels', []))
    os.environ['SESSION_STRING'] = kwargs.get('session_string', '')
    os.environ['SESSION_NAME'] = kwargs.get('session_name', 'default')
    os.environ['RECURSIVE'] = '1' if kwargs.get('recursive', False) else '0'
    os.environ['NEO4J_WRITE'] = '1' if kwargs.get('neo4j_write', False) else '0'
    os.environ['SKIP_HISTORY'] = '0'
    os.environ['OWNER_ID'] = kwargs.get('owner_id', 'unknown')
    
    # Optional parameters
    if kwargs.get('parent_container_id'):
        os.environ['PARENT_CONTAINER_ID'] = kwargs['parent_container_id']
    if kwargs.get('depth') is not None:
        os.environ['RECURSION_DEPTH'] = str(kwargs['depth'])
    if kwargs.get('case_id') is not None:
        os.environ['CASE_ID'] = str(kwargs['case_id'])
    
    # Führe main() aus (ENV vars sind jetzt gesetzt)
    try:
        result = asyncio.run(main(owner_id=owner_id, case_id=case_id))
        print(f"[RQ] Job completed successfully")
        return {
            "status": "completed", 
            "mode": kwargs.get('mode'),
            "channels": kwargs.get('channels')
        }
    except Exception as e:
        print(f"[RQ] Job failed: {e}")
        import traceback
        traceback.print_exc()
        raise

# ========================================
# Globale Variablen - NUR für direkten Aufruf
# ========================================
# WICHTIG: Diese werden beim Import ausgeführt, aber nur für __main__ gebraucht

def get_env_vars():
    """Helper um ENV vars zu lesen (lazy loading)"""
    MODE = os.getenv("MODE", "similar").strip()
    CHANNELS_RAW = os.getenv("CHANNELS", "")
    CHANNELS = [c.strip() for c in CHANNELS_RAW.split(",") if c]
    SESSION_NAME = os.getenv("SESSION_NAME", "default")
    SESSION_STRING = os.getenv("SESSION_STRING")
    RECURSIVE = os.getenv("RECURSIVE", "0") == "1"
    NEO4J_WRITE = os.getenv("NEO4J_WRITE", "0") == "1"
    SKIP_HISTORY = os.getenv("SKIP_HISTORY", "0") == "1"
    
    return {
        'MODE': MODE,
        'CHANNELS': CHANNELS,
        'SESSION_NAME': SESSION_NAME,
        'SESSION_STRING': SESSION_STRING,
        'RECURSIVE': RECURSIVE,
        'NEO4J_WRITE': NEO4J_WRITE,
        'SKIP_HISTORY': SKIP_HISTORY
    }

from aether_lib.neo4j_client.connection import init_driver, close_driver

async def main(owner_id=None, case_id=None):
    """Hauptlogik - liest ENV vars zur Laufzeit"""
    env = get_env_vars()
    MODE = env['MODE']
    CHANNELS = env['CHANNELS']
    SESSION_NAME = env['SESSION_NAME']
    SESSION_STRING = env['SESSION_STRING']
    RECURSIVE = env['RECURSIVE']
    NEO4J_WRITE = env['NEO4J_WRITE']
    SKIP_HISTORY = env['SKIP_HISTORY']
    if owner_id is None:
        owner_id = os.getenv('OWNER_ID', 'unknown')
    if case_id is None:
        case_id_env = os.getenv('CASE_ID')
        case_id = int(case_id_env) if case_id_env and case_id_env.isdigit() else None
    if not MODE:
        sys.exit("MODE environment variable is required")

    if not SESSION_STRING:
        raise ValueError("SESSION_STRING environment variable is required but not set.")

    # ✅ Initialize Neo4j driver once at startup
    await init_driver()
    print("[INIT] Neo4j driver initialized")

    try:
        await login()
        print(f"[DEBUG] Logged in with {MODE}")
        if not CHANNELS:
            print("[]")
            return

        if MODE == "similar":
            root = CHANNELS[0]
            if await is_scraped(root):
                return
            recs = await similar_channels(root)
            print(json.dumps(recs, ensure_ascii=False))
            if NEO4J_WRITE:
                await write_recommendations(root, recs)
            usernames = [c["username"] for c in recs if c.get("username")]
            if usernames:
                await run_scraper(usernames, SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY, case_id=case_id, owner_id=owner_id)

        elif MODE == "scrape":
            for ch in CHANNELS:
                if await is_scraped(ch):
                    continue
                await run_scraper([ch], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY, case_id=case_id, owner_id=owner_id)

        elif MODE == "full":
            for root in CHANNELS:
                await run_scraper([root], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY, case_id=case_id, owner_id=owner_id)
                recs = await similar_channels(root)
                if NEO4J_WRITE:
                    await write_recommendations(root, recs)
                usernames = [c["username"] for c in recs if c.get("username")]
                if usernames:
                    await run_scraper(usernames, SESSION_NAME, recursive=False, skip_history=SKIP_HISTORY, owner_id=owner_id)

        elif MODE == "live":
            print("[LIVE] Listening for new messages only...")
            try:
                await run_live_listener_only(CHANNELS, owner_id=owner_id, case_id=case_id)
            except Exception as e:
                print("[ERROR] Exception in live listener:", e)
                import traceback
                traceback.print_exc()
            print("[DEBUG] Live listener finished.")

        else:
            print(f"[ERROR] Unknown MODE: {MODE!r}")
            sys.exit("unknown MODE")

    finally:
        # ✅ Always close the driver cleanly
        await close_driver()
        print("[CLOSE] Neo4j driver closed")

# Für direkten Aufruf (alte Docker-Container)
if __name__ == "__main__":
    try:
        print("[START] Starting Telegram scraper job...")
        asyncio.run(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)