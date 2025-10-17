# telegram_job/rq_worker.py
"""
Minimaler Entry Point für RQ Worker.
Vermeidet Import-Probleme beim Laden.
"""
import os
import sys
import asyncio
import signal
import sys

should_stop = False

def signal_handler(signum, frame):
    global should_stop
    print(f"[RQ] Received signal {signum}, stopping gracefully...")
    should_stop = True

# Register handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def run_job(**kwargs):
    """
    RQ Worker Entry Point.
    Importiert entry.main() erst zur Laufzeit.
    """
    print(f"[RQ] Starting job with kwargs: {kwargs}")
    
    # Setze ENV-Variablen
    os.environ['MODE'] = kwargs.get('mode', 'scrape')
    os.environ['CHANNELS'] = ','.join(kwargs.get('channels', []))
    session_string = kwargs.get('session_string')
    if session_string:
        os.environ['SESSION_STRING'] = str(session_string)
    else:
        os.environ['SESSION_STRING'] = ''
    os.environ['SESSION_NAME'] = kwargs.get('session_name', 'default')
    os.environ['RECURSIVE'] = '1' if kwargs.get('recursive', False) else '0'
    os.environ['NEO4J_WRITE'] = '1' if kwargs.get('neo4j_write', False) else '0'
    os.environ['SKIP_HISTORY'] = '0'
    
    if kwargs.get('parent_container_id'):
        os.environ['PARENT_CONTAINER_ID'] = kwargs['parent_container_id']
    if kwargs.get('depth') is not None:
        os.environ['RECURSION_DEPTH'] = str(kwargs['depth'])
    if kwargs.get('case_id') is not None:
        os.environ['CASE_ID'] = str(kwargs['case_id'])
    
    

    owner_id = kwargs.get('owner_id', 'unknown')
    
    # Set in ENV for legacy code
    os.environ['OWNER_ID'] = owner_id
    
    # Set in context for Neo4j
    from aether_lib.neo4j_client.connection import set_owner_id
    set_owner_id(owner_id)
    
    # Import and run
    sys.path.insert(0, '/app/telegram_job')
    from entry import main
    
    try:
        if should_stop:
            print("[RQ] Stopped before execution")
            return {"status": "cancelled"}
        asyncio.run(main(owner_id=owner_id)) 
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