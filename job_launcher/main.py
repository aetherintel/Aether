from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import docker, os, uuid, json
from pathlib import Path
from typing import Optional
import docker
import os

docker_client = docker.from_env()

def docker_login_if_needed():
    if os.getenv("ENVIRONMENT") == "prod":
        try:
            docker_client.login(
                username=os.getenv("DOCKER_USERNAME"),
                password=os.getenv("DOCKER_PASSWORD")
            )
            print("✅ Docker login successful.")
        except docker.errors.APIError as e:
            print("❌ Docker login failed:", e)

app = FastAPI()
docker_client = docker.from_env()

SECRET = os.getenv("JOB_SECRET_TOKEN", "changeme")
SESSION_DIR = Path("/app/sessions")
media_host_path = os.environ["MEDIA_PATH"]

class ContainerControlRequest(BaseModel):
    owner_id: str
    force: Optional[bool] = False

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
    case_id: Optional[int] = None  # Optional case ID for tracking

def _check_auth(request: Request):
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {SECRET}":
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.post("/similar")
def launch_similarity(req: SimilarRequest, request: Request):
    _check_auth(request)

    docker_login_if_needed()

    image_name = (
        f"{os.getenv('DOCKER_USERNAME')}/aether-telegram_scraper:latest"
        if os.getenv("ENVIRONMENT") == "prod"
        else "telegram-job:latest"
    )

    network = (
        f"app_default"
        if os.getenv("ENVIRONMENT") == "prod"
        else "aether_default"
    )

    session_string, user_info = load_string_session(req.tg_session)
    container = docker_client.containers.run(
        image=image_name,
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
        network=network,
        labels={
            "MODE": "similar",
            "CHANNELS": req.channel,
            "OWNER_ID": req.owner_id,
            "case_id": str(req.case_id) if req.case_id is not None else ""
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
        "case_id": str(req.case_id) if req.case_id is not None else ""
    }

    if req.parent_container_id:
        labels["PARENT_CONTAINER_ID"] = req.parent_container_id
    
    docker_login_if_needed()

    image_name = (
        f"{os.getenv('DOCKER_USERNAME')}/aether-telegram_scraper:latest"
        if os.getenv("ENVIRONMENT") == "prod"
        else "telegram-job:latest"
    )

    network = (
        f"app_default"
        if os.getenv("ENVIRONMENT") == "prod"
        else "aether_default"
    )

    print(f"[INFO] ENV: {os.getenv('ENVIRONMENT')}, Using image: {image_name}")

    container = docker_client.containers.run(
        image=image_name,
        name=container_id,
        detach=True,
        environment=env_vars,
        volumes={
            media_host_path: {
                'bind': '/app/public/media',
                'mode': 'rw',
            },
        },
        network=network,
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
            "case_id": labels.get("case_id"),
        })
    
    return {"containers": result}

@app.post("/containers/{container_id}/start")
def start_container(container_id: str, req: ContainerControlRequest, request: Request):
    """Start a specific container"""
    _check_auth(request)
    
    image_name = (
        f"{os.getenv('DOCKER_USERNAME')}/aether-telegram_scraper"
        if os.getenv("ENVIRONMENT") == "prod"
        else "telegram-job"
    )

    try:
        container = docker_client.containers.get(container_id)
        
        # Verify ownership
        container_owner = container.labels.get("OWNER_ID")
        if container_owner != req.owner_id:
            raise HTTPException(status_code=403, detail="Access denied: container not owned by user")
        
        # Verify it's a telegram job
        image_tags = container.image.tags if container.image and container.image.tags else []
        is_telegram_job = any(image_name in tag for tag in image_tags) if image_tags else any(image_name in value for value in container.labels.values())
        if not is_telegram_job and container.labels.get(f"{image_name}:latest") != "true":
            print(f"[DEBUG] Container {container.name} is not a telegram job (tags: {container.image.tags} {container.labels})")
            raise HTTPException(status_code=400, detail="Container is not a telegram job")
        
        # Check current status
        container.reload()
        if container.status == 'running':
            return {
                "message": f"Container {container.name} is already running",
                "status": "running"
            }
        
        # Start the container
        container.start()
        container.reload()
        
        return {
            "message": f"Container {container.name} started successfully",
            "status": container.status
        }
        
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except docker.errors.APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/containers/{container_id}/stop")
def stop_container(container_id: str, req: ContainerControlRequest, request: Request):
    """Stop a specific container"""
    _check_auth(request)
    
    image_name = (
        f"{os.getenv('DOCKER_USERNAME')}/aether-telegram_scraper"
        if os.getenv("ENVIRONMENT") == "prod"
        else "telegram-job"
    )

    try:
        container = docker_client.containers.get(container_id)
        
        # Verify ownership
        container_owner = container.labels.get("OWNER_ID")
        if container_owner != req.owner_id:
            raise HTTPException(status_code=403, detail="Access denied: container not owned by user")
        
        # Verify it's a telegram job
        image_tags = container.image.tags if container.image and container.image.tags else []
        is_telegram_job = any(image_name in tag for tag in image_tags) if image_tags else False
        if not is_telegram_job and container.labels.get(f"{image_name}:latest") != "true":
            raise HTTPException(status_code=400, detail="Container is not a telegram job")
        
        # Check current status
        container.reload()
        if container.status in ['exited', 'stopped']:
            return {
                "message": f"Container {container.name} is already stopped",
                "status": container.status
            }
        
        # Stop the container
        container.stop(timeout=10)
        container.reload()
        
        return {
            "message": f"Container {container.name} stopped successfully",
            "status": container.status
        }
        
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except docker.errors.APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/containers/{container_id}/restart")
def restart_container(container_id: str, req: ContainerControlRequest, request: Request):
    """Restart a specific container"""
    _check_auth(request)
    
    image_name = (
        f"{os.getenv('DOCKER_USERNAME')}/aether-telegram_scraper"
        if os.getenv("ENVIRONMENT") == "prod"
        else "telegram-job"
    )

    try:
        container = docker_client.containers.get(container_id)
        
        # Verify ownership
        container_owner = container.labels.get("OWNER_ID")
        if container_owner != req.owner_id:
            raise HTTPException(status_code=403, detail="Access denied: container not owned by user")
        
        # Verify it's a telegram job
        image_tags = container.image.tags if container.image and container.image.tags else []
        is_telegram_job = any(image_name in tag for tag in image_tags) if image_tags else False
        if not is_telegram_job and container.labels.get(f"{image_name}:latest") != "true":
            raise HTTPException(status_code=400, detail="Container is not a telegram job")
        
        # Restart the container
        container.restart(timeout=10)
        container.reload()
        
        return {
            "message": f"Container {container.name} restarted successfully",
            "status": container.status
        }
        
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except docker.errors.APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.delete("/containers/{container_id}")
def remove_container(container_id: str, req: ContainerControlRequest, request: Request):
    """Remove a specific container"""
    _check_auth(request)
    
    image_name = (
        f"{os.getenv('DOCKER_USERNAME')}/aether-telegram_scraper"
        if os.getenv("ENVIRONMENT") == "prod"
        else "telegram-job"
    )

    try:
        # Try to get running container first
        try:
            container = docker_client.containers.get(container_id)
        except docker.errors.NotFound:
            # If not found in running, search in all containers
            all_containers = docker_client.containers.list(all=True)
            container = None
            for c in all_containers:
                if c.id == container_id or c.id.startswith(container_id):
                    container = c
                    break
            print(f"[DEBUG] Searching for container {container_id} in all containers: found={bool(container)} in {len(all_containers)} total")
            if not container:
                raise HTTPException(status_code=404, detail="Container not found")
        
        # Verify ownership
        container_owner = container.labels.get("OWNER_ID")
        if container_owner != req.owner_id:
            raise HTTPException(status_code=403, detail="Access denied: container not owned by user")
        
        # Verify it's a telegram job
        image_tags = container.image.tags if container.image and container.image.tags else []
        is_telegram_job = (any(image_name in tag for tag in image_tags) if image_tags else False) or container.labels.get("com.docker.compose.service") == image_name
        
        if not is_telegram_job:
            raise HTTPException(status_code=400, detail="Container is not a telegram job")
        
        container_name = container.name
        
        # Stop and remove the container
        if container.status == 'running':
            container.stop(timeout=10)
        
        container.remove(force=req.force)
        
        return {
            "message": f"Container {container_name} removed successfully",
            "status": "removed"
        }
        
    except docker.errors.APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def load_string_session(session_name: str) -> tuple:
    """StringSession aus JSON-Datei"""
    session_file = SESSION_DIR / f"{session_name}.json"
    if not session_file.exists():
        return None, None
    
    with open(session_file, 'r') as f:
        data = json.load(f)
    
    return data.get("session_string"), data.get("user_info")