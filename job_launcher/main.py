from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import docker, os, uuid, json
from pathlib import Path

app = FastAPI()
docker_client = docker.from_env()

SECRET = os.getenv("JOB_SECRET_TOKEN", "changeme")
SESSION_DIR = Path("/app/sessions")

class SimilarRequest(BaseModel):
    channel: str
    tg_session: str

class ScrapeRequest(BaseModel):
    channels: list[str]
    tg_session: str
    mode: str = "scrape"  # scrape | similar | full
    recursive: bool = False
    neo4j: bool = True

def _check_auth(request: Request):
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {SECRET}":
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.post("/similar")
def launch_similarity(req: SimilarRequest, request: Request):
    _check_auth(request)

    session_string, user_info = load_string_session(req.tg_session)

    print(f"Launching similarity job for: {req.channel}")
    container = docker_client.containers.run(
        image="telegram-job:latest",
        name=f"similar_{uuid.uuid4().hex[:6]}",
        remove=True,
        detach=False,
        environment={
            "MODE": "similar",
            "CHANNELS": req.channel,
            "SESSION_STRING": session_string,
            "NEO4J_WRITE": "1",
            "NEO4J_URI": os.getenv("NEO4J_URI"),
            "NEO4J_USER": os.getenv("NEO4J_USER"),
            "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
            "TG_API_ID": os.getenv("TG_API_ID"),
            "TG_API_HASH": os.getenv("TG_API_HASH"),
        },
        network= "monitor_default",
        labels={
            "MODE": "similar",
            "CHANNELS": req.channel
        }
    )
    return {"result": container.decode()}

@app.post("/scrape")
def launch_scraper(req: ScrapeRequest, request: Request):
    _check_auth(request)

    session_string, user_info = load_string_session(req.tg_session)

    print(f"Launching {req.mode} job for: {req.channels} with session: {req.tg_session}")
    env_vars = {
        "MODE": req.mode,
        "CHANNELS": ",".join(req.channels),
        "SESSION_STRING": session_string,
        "RECURSIVE": str(int(req.recursive)),
        "NEO4J_WRITE": str(int(req.neo4j)),
        "NEO4J_URI": os.getenv("NEO4J_URI"),
        "NEO4J_USER": os.getenv("NEO4J_USER"),
        "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
        "TG_API_ID": os.getenv("TG_API_ID"),
        "TG_API_HASH": os.getenv("TG_API_HASH"),
    }

    container = docker_client.containers.run(
        image="telegram-job:latest",
        name=f"{req.mode}_{uuid.uuid4().hex[:6]}",
        detach=True,
        environment=env_vars,
        network="monitor_default",
        labels={
            "MODE": req.mode,
            "CHANNELS": ",".join(req.channels)
        }
    )
    return {"container_id": container.id}

def load_string_session(session_name: str) -> tuple:
    """StringSession aus JSON-Datei"""
    session_file = SESSION_DIR / f"{session_name}.json"
    if not session_file.exists():
        return None, None
    
    with open(session_file, 'r') as f:
        data = json.load(f)
    
    return data.get("session_string"), data.get("user_info")