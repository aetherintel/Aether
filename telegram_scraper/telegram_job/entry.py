# telegram_job/entry.py
print("[DEBUG] entry.py loaded.")
import os, json, sys, asyncio

# GEÄNDERT: Relative Imports verwenden
from similar import similar_channels_flexible as similar_channels
from scraper import run_scraper, run_live_listener_only
from neo4j_client import write_recommendations, is_scraped
from telegram_client import login

# ========================================
# NEU: RQ Worker Entry Point
# ========================================
def run_job(**kwargs):
    """
    Entry point für RQ Worker.
    Wird vom Job-Launcher via Queue aufgerufen.
    """
    print(f"[RQ] Starting job with kwargs: {kwargs}")
    
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
        result = asyncio.run(main())
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

async def main():
    """Hauptlogik - liest ENV vars zur Laufzeit"""
    # Lese ENV vars HIER (nicht beim Import!)
    env = get_env_vars()
    MODE = env['MODE']
    CHANNELS = env['CHANNELS']
    SESSION_NAME = env['SESSION_NAME']
    SESSION_STRING = env['SESSION_STRING']
    RECURSIVE = env['RECURSIVE']
    NEO4J_WRITE = env['NEO4J_WRITE']
    SKIP_HISTORY = env['SKIP_HISTORY']
    
    if not MODE:
        sys.exit("MODE environment variable is required")
    
    if not SESSION_STRING:
        raise ValueError("SESSION_STRING environment variable is required but not set.")
    
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
            await run_scraper(usernames, SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)
    
    elif MODE == "scrape":
        for ch in CHANNELS:
            if await is_scraped(ch):
                continue
            await run_scraper([ch], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)
    
    elif MODE == "full":
        for root in CHANNELS:
            # Step 1: Scrape the root channel
            await run_scraper([root], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY)
            # Step 2: Find similar channels and scrape them
            recs = await similar_channels(root)
            if NEO4J_WRITE:
                await write_recommendations(root, recs)
            usernames = [c["username"] for c in recs if c.get("username")]
            if usernames:
                await run_scraper(usernames, SESSION_NAME, recursive=False, skip_history=SKIP_HISTORY)
    
    elif MODE == "live":
        print("[LIVE] Listening for new messages only...")
        try:
            await run_live_listener_only(CHANNELS)
        except Exception as e:
            print("[ERROR] Exception in live listener:", e)
            import traceback
            traceback.print_exc()
        print("[DEBUG] Live listener finished.")
    
    else:
        print(f"[ERROR] Unknown MODE: {MODE!r}")
        sys.exit("unknown MODE")

# Für direkten Aufruf (alte Docker-Container)
if __name__ == "__main__":
    try:
        print("[START] Starting Telegram scraper job...")
        asyncio.run(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)