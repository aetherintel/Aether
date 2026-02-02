
import os, json, sys, asyncio, uuid
from redis import Redis
from rq import Queue

# GEÄNDERT: Relative Imports verwenden
from .similar import similar_channels_flexible as similar_channels
from .similar import similar_channels_flexible as similar_channels
from .scraper import run_scraper, run_live_listener_only, reload_scraper_config, init_scraper_state
from aether_lib.neo4j_client.channels import write_recommendations, is_scraped
from aether_lib.neo4j_client.connection import init_driver, close_driver, set_owner_id
from .telegram_client import login

# ========================================
# NEU: RQ Worker Entry Point
# ========================================
def run_job(**kwargs):
    """
    Entry point für RQ Worker.
    """
    print(f"[RQ] Starting job with kwargs: {kwargs}", flush=True)
    print(f"[RQ] Job PID: {os.getpid()}", flush=True)

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
    os.environ['ENABLE_TRANSLATION'] = '1' if kwargs.get('enable_translation', True) else '0'
    os.environ['ENABLE_IMAGE_ANALYSIS'] = '1' if kwargs.get('enable_image_analysis', True) else '0'
    os.environ['ENABLE_AUDIO_TRANSCRIPTION'] = '1' if kwargs.get('enable_audio_transcription', True) else '0'
    os.environ['ENABLE_EMOTION_ANALYSIS'] = '1' if kwargs.get('enable_emotion_analysis', True) else '0'
    os.environ['ENABLE_LABEL_CLASSIFIER'] = '1' if kwargs.get('enable_label_classifier', True) else '0'
    os.environ['ENABLE_GEOLOCATION_EXTRACTION'] = '1' if kwargs.get('enable_geolocation_extraction', True) else '0'
    os.environ['ENABLE_LIVE_MONITORING'] = '1' if kwargs.get('enable_live_monitoring', False) else '0'
    
    print("[RQ] Reloading scraper config...", flush=True)
    reload_scraper_config()
    print("[RQ] Config reloaded.", flush=True)
    
    # Optional parameters
    if kwargs.get('parent_container_id'):
        os.environ['PARENT_CONTAINER_ID'] = kwargs['parent_container_id']
    if kwargs.get('depth') is not None:
        os.environ['RECURSION_DEPTH'] = str(kwargs['depth'])
    if kwargs.get('case_id') is not None:
        os.environ['CASE_ID'] = str(kwargs['case_id'])
    
    # Führe main() aus (ENV vars sind jetzt gesetzt)
    try:
        print("[RQ] Starting asyncio.run(main)...", flush=True)
        result = asyncio.run(main(owner_id=owner_id, case_id=case_id))
        print(f"[RQ] Job completed successfully", flush=True)
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
    finally:
        # Self-Rescheduling Logic for Live Monitoring
        if os.environ.get('ENABLE_LIVE_MONITORING') == '1':
            try:
                print("[RQ] Live monitoring enabled. Rescheduling job...", flush=True)
                
                # Connect to Redis (using same host/port as standard env)
                redis_host = os.getenv("REDIS_HOST", "redis")
                redis_port = int(os.getenv("REDIS_PORT", "6379"))
                r = Redis(host=redis_host, port=redis_port, db=0) # db=0 for telegram
                q = Queue('telegram-jobs', connection=r)
                
                # Generate new job ID
                new_job_id = f"{kwargs.get('mode', 'scrape')}_{uuid.uuid4().hex[:6]}"
                
                q.enqueue(
                    'telegram_job.entry.run_job',
                    kwargs=kwargs,
                    job_id=new_job_id,
                    job_timeout='6h',
                    result_ttl=86400,
                    failure_ttl=86400
                )
                print(f"[RQ] ✅ Rescheduled job as {new_job_id}", flush=True)
            except Exception as e:
                print(f"[RQ] ❌ Failed to reschedule job: {e}", flush=True)

# ========================================
# Globale Variablen - NUR für direkten Aufruf
# ========================================

def reload_config():
    """Lädt alle Konfigurationsvariablen aus den aktuellen ENV-Variablen neu."""
    global ENABLE_TRANSLATION, ENABLE_IMAGE_ANALYSIS, ENABLE_AUDIO_TRANSCRIPTION
    global ENABLE_EMOTION_ANALYSIS, ENABLE_LABEL_CLASSIFIER, ENABLE_GEOLOCATION_EXTRACTION
    
    ENABLE_TRANSLATION = os.getenv('ENABLE_TRANSLATION', '1') == '1'
    ENABLE_IMAGE_ANALYSIS = os.getenv('ENABLE_IMAGE_ANALYSIS', '1') == '1'
    ENABLE_AUDIO_TRANSCRIPTION = os.getenv('ENABLE_AUDIO_TRANSCRIPTION', '1') == '1'
    ENABLE_EMOTION_ANALYSIS = os.getenv('ENABLE_EMOTION_ANALYSIS', '1') == '1'
    ENABLE_LABEL_CLASSIFIER = os.getenv('ENABLE_LABEL_CLASSIFIER', '1') == '1'
    ENABLE_GEOLOCATION_EXTRACTION = os.getenv('ENABLE_GEOLOCATION_EXTRACTION', '1') == '1'
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

    # ✅ Set owner_id in context
    set_owner_id(owner_id)
    print(f"[INIT] Owner ID set to: {owner_id}", flush=True)

    # ✅ Initialize Neo4j driver once at startup
    print("[INIT] Initializing Neo4j driver...", flush=True)
    await init_driver()
    print("[INIT] Neo4j driver initialized", flush=True)
    
    # Initialize scraper state (Queue/Semaphore) in current loop
    print("[INIT] Initializing scraper state...", flush=True)
    init_scraper_state()
    print("[INIT] Scraper state initialized", flush=True)

    try:
        print(f"[INIT] Logging in with session string length: {len(SESSION_STRING) if SESSION_STRING else 0}", flush=True)
        await login(session_string=SESSION_STRING)
        print(f"[DEBUG] Logged in with {MODE}", flush=True)
        if not CHANNELS:
            print("[DEBUG] No channels to process", flush=True)
            return

        if MODE == "similar":
            print(f"[MODE] Starting SIMILAR mode for {CHANNELS[0]}", flush=True)
            root = CHANNELS[0]
            if await is_scraped(root):
                print(f"[SKIP] {root} already scraped", flush=True)
                return
            recs = await similar_channels(root)
            print(json.dumps(recs, ensure_ascii=False), flush=True)
            if NEO4J_WRITE:
                await write_recommendations(root, recs)
            usernames = [c["username"] for c in recs if c.get("username")]
            if usernames:
                await run_scraper(usernames, SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY, case_id=case_id, owner_id=owner_id)

        elif MODE == "scrape":
            print(f"[MODE] Starting SCRAPE mode for {len(CHANNELS)} channels", flush=True)
            for ch in CHANNELS:
                if await is_scraped(ch):
                    print(f"[SKIP] {ch} already scraped", flush=True)
                    continue
                await run_scraper([ch], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY, case_id=case_id, owner_id=owner_id)

        elif MODE == "full":
            print(f"[MODE] Starting FULL mode for {len(CHANNELS)} channels", flush=True)
            for root in CHANNELS:
                print(f"[FULL] Processing root: {root}", flush=True)
                await run_scraper([root], SESSION_NAME, recursive=RECURSIVE, skip_history=SKIP_HISTORY, case_id=case_id, owner_id=owner_id)
                recs = await similar_channels(root)
                if NEO4J_WRITE:
                    await write_recommendations(root, recs)
                usernames = [c["username"] for c in recs if c.get("username")]
                if usernames:
                    print(f"[FULL] Found {len(usernames)} similar channels to scrape", flush=True)
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