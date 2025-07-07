from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import docker, os, uuid, json
from pathlib import Path
from typing import Optional

app = FastAPI()
docker_client = docker.from_env()

SECRET = os.getenv("JOB_SECRET_TOKEN", "changeme")
SESSION_DIR = Path("/app/sessions")
media_host_path = os.environ["MEDIA_PATH"]

class SimilarRequest(BaseModel):
    channel: str
    tg_session: str
    owner_id: str = "unknown"

class ScrapeRequest(BaseModel):
    channels: list[str]
    tg_session: str
    mode: str = "scrape"  # scrape | similar | full | discover
    recursive: bool = False
    neo4j: bool = True
    owner_id: str = "unknown"
    parent_container_id: Optional[str] = None  # Track parent container to prevent cycles
    depth: int = 0  # Track recursion depth
    max_discover_messages: int = 200  # Limit for quick discovery mode

def _check_auth(request: Request):
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {SECRET}":
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.post("/similar")
def launch_similarity(req: SimilarRequest, request: Request):
    _check_auth(request)

    session_string, user_info = load_string_session(req.tg_session)
    container = docker_client.containers.run(
        image="telegram-job:latest",
        name=f"similar_{uuid.uuid4().hex[:6]}",
        remove=True,
        detach=False,
        environment={
            "MODE": "similar",
            "CHANNELS": req.channel,
            "SESSION_STRING": session_string,
            "SESSION_NAME": req.tg_session,
            "NEO4J_WRITE": "1",
            "NEO4J_URI": os.getenv("NEO4J_URI"),
            "NEO4J_USER": os.getenv("NEO4J_USER"),
            "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
            "TG_API_ID": os.getenv("TG_API_ID"),
            "TG_API_HASH": os.getenv("TG_API_HASH"),
            "OWNER_ID": req.owner_id,
            "JOB_LAUNCHER_URL": os.getenv("JOB_LAUNCHER_URL"),
            "JOB_SECRET_TOKEN": os.getenv("JOB_SECRET_TOKEN"),
            "MEDIA_ROOT": "/app/public/media",
        },
        volumes={
            media_host_path: {
                'bind': '/app/public/media',
                'mode': 'rw',
            },
        },
        network="aether_default",
        labels={
            "MODE": "similar",
            "CHANNELS": req.channel,
            "OWNER_ID": req.owner_id,
        }
    )
    return {"result": container.decode()}

@app.post("/scrape")
def launch_scraper(req: ScrapeRequest, request: Request):
    _check_auth(request)

    # Prevent infinite recursion by limiting depth
    MAX_RECURSION_DEPTH = 3
    if req.depth >= MAX_RECURSION_DEPTH:
        raise HTTPException(
            status_code=400, 
            detail=f"Maximum recursion depth ({MAX_RECURSION_DEPTH}) exceeded"
        )

    session_string, user_info = load_string_session(req.tg_session)

    print(f"Launching {req.mode} job for: {req.channels} with session: {req.tg_session} (depth: {req.depth})")
    
    container_id = f"{req.mode}_{uuid.uuid4().hex[:6]}"
    
    env_vars = {
        "MODE": req.mode,
        "CHANNELS": ",".join(req.channels),
        "SESSION_STRING": session_string,
        "SESSION_NAME": req.tg_session,
        "RECURSIVE": str(int(req.recursive)),
        "NEO4J_WRITE": str(int(req.neo4j)),
        "NEO4J_URI": os.getenv("NEO4J_URI"),
        "NEO4J_USER": os.getenv("NEO4J_USER"),
        "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
        "TG_API_ID": os.getenv("TG_API_ID"),
        "TG_API_HASH": os.getenv("TG_API_HASH"),
        "OWNER_ID": req.owner_id,
        "JOB_LAUNCHER_URL": os.getenv("JOB_LAUNCHER_URL"),
        "JOB_SECRET_TOKEN": os.getenv("JOB_SECRET_TOKEN"),
        "PARENT_CONTAINER_ID": req.parent_container_id or "",
        "RECURSION_DEPTH": str(req.depth),
        "MEDIA_ROOT": "/app/public/media",
    }
    
    labels = {
        "MODE": req.mode,
        "CHANNELS": ",".join(req.channels),
        "OWNER_ID": req.owner_id,
        "RECURSION_DEPTH": str(req.depth),
    }
    
    if req.parent_container_id:
        labels["PARENT_CONTAINER_ID"] = req.parent_container_id
    
    container = docker_client.containers.run(
        image="telegram-job:latest",
        name=container_id,
        detach=True,
        environment=env_vars,
        volumes={
            media_host_path: {
                'bind': '/app/public/media',
                'mode': 'rw',
            },
        },
        network="aether_default",
        labels=labels
    )
    
    import time
    time.sleep(2)
    print("[DEBUG] Live container logs:")
    print(container.logs(stdout=True, stderr=True).decode())
    return {"container_id": container.id}

@app.get("/containers")
def list_containers(request: Request):
    """List all running scraper containers"""
    _check_auth(request)
    
    containers = docker_client.containers.list(
        filters={"label": "MODE"}
    )
    
    result = []
    for container in containers:
        labels = container.labels
        result.append({
            "id": container.id,
            "name": container.name,
            "status": container.status,
            "mode": labels.get("MODE"),
            "channels": labels.get("CHANNELS"),
            "owner_id": labels.get("OWNER_ID"),
            "recursion_depth": labels.get("RECURSION_DEPTH"),
            "parent_container_id": labels.get("PARENT_CONTAINER_ID"),
        })
    
    return {"containers": result}

@app.delete("/containers/{container_id}")
def kill_container(container_id: str, request: Request):
    """Kill a specific container"""
    _check_auth(request)
    
    try:
        container = docker_client.containers.get(container_id)
        container.kill()
        return {"message": f"Container {container_id} killed successfully"}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def load_string_session(session_name: str) -> tuple:
    """StringSession aus JSON-Datei"""
    session_file = SESSION_DIR / f"{session_name}.json"
    if not session_file.exists():
        return None, None
    
    with open(session_file, 'r') as f:
        data = json.load(f)
    
    return data.get("session_string"), data.get("user_info")