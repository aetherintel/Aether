from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import docker, os, uuid

app = FastAPI()
docker_client = docker.from_env()

SECRET = os.getenv("JOB_SECRET_TOKEN", "changeme")

class SimilarRequest(BaseModel):
    channel: str

class ScrapeRequest(BaseModel):
    channels: list[str]

def _check_auth(request: Request):
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {SECRET}":
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.post("/similar")
def launch_similarity(req: SimilarRequest, request: Request):
    _check_auth(request)

    print(f"Launching similarity job for: {req.channel}")
    container = docker_client.containers.run(
        image="telegram-job:latest",
        name=f"similar_{uuid.uuid4().hex[:6]}",
        remove=True,
        detach=False,
        environment={
            "MODE": "similar",
            "CHANNELS": req.channel,
            "SESSION_NAME": "default",
            "NEO4J_WRITE": "1",
            "NEO4J_URI": os.getenv("NEO4J_URI"),
            "NEO4J_USER": os.getenv("NEO4J_USER"),
            "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
            "TG_API_ID": os.getenv("TG_API_ID"),
            "TG_API_HASH": os.getenv("TG_API_HASH"),
        },
        volumes={"tg_default": {"bind": "/app/session", "mode": "rw"}},
        network= "monitor_default"
    )
    return {"result": container.decode()}

@app.post("/scrape")
def launch_scraper(req: ScrapeRequest, request: Request):
    _check_auth(request)

    print(f"Launching scraper job for: {req.channels}")
    container = docker_client.containers.run(
        image="telegram-job:latest",
        name=f"scraper_{uuid.uuid4().hex[:6]}",
        detach=True,
        environment={
            "MODE": "scrape",
            "CHANNELS": ",".join(req.channels),
            "SESSION_NAME": "default",
            "NEO4J_URI": os.getenv("NEO4J_URI"),
            "NEO4J_USER": os.getenv("NEO4J_USER"),
            "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
            "TG_API_ID": os.getenv("TG_API_ID"),
            "TG_API_HASH": os.getenv("TG_API_HASH"),
        },
        volumes={"tg_default": {"bind": "/app/session", "mode": "rw"}},
        network="monitor_default"
    )
    return {"container_id": container.id}
