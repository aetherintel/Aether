import requests
from fastapi import HTTPException
from pydantic import BaseModel
from services.config import settings  # assuming you keep shared settings here
import os # for environment variables
LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL") or "http://job-launcher:9001"
LAUNCHER_SECRET = os.getenv("JOB_SECRET_TOKEN") or "changeme"

class ExtendedScrapeRequest(BaseModel):
    channel: str
    tg_session: str
    recursive: bool = True
    neo4j: bool = True,
    owner_id: str

def run_similarity(channel: str, tg_session: str, owner_id: str) -> dict:
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/similar",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={
                "channel": channel,
                "tg_session": tg_session,
                "owner_id": owner_id,
            },
            timeout=30
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity job failed: {str(e)}")

def start_scraper(channels: list[str], tg_session: str, owner_id: str, case_id: int) -> str:
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/scrape",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={
                "channels": channels,
                "tg_session": tg_session,
                "owner_id": owner_id,
                "case_id": case_id,
            },
            timeout=10
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json().get("container_id", "unknown")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper job failed: {str(e)}")

def launch_full_scrape_job(channel: str, tg_session: str, recursive: bool = True, neo4j: bool = True, owner_id: str = "", case_id: int = None) -> dict:
    """
    Launch a Docker container to run a Telegram scraping + similarity job.
    """
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/scrape",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={
                "channels": [channel],
                "tg_session": tg_session,
                "mode": "full",
                "recursive": recursive,
                "neo4j": neo4j,
                "owner_id": owner_id,
                "case_id": case_id,  # Optional case ID for tracking
            },
            timeout=15
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch scraper job: {str(e)}")

def launch_live_scrape_job(channels: list[str], tg_session: str, neo4j: bool, owner_id: str, case_id: int = None) -> dict:
    """
    Launch a Docker container to run live-only Telegram listener.
    """
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/scrape",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={
                "channels": channels,
                "tg_session": tg_session,
                "neo4j": neo4j,
                "mode": "live",
                "owner_id": owner_id,  # Owner ID is not needed for live mode
                "case_id": case_id
            },
            timeout=10
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live scraper job failed: {str(e)}")

def get_container_status(owner_id: str, case_id: str = None) -> dict:
    """
    Get container status via job_launcher
    """
    try:
        params = {"owner_id": owner_id}
        if case_id:
            params["case_id"] = case_id
            
        response = requests.get(
            f"{LAUNCHER_URL}/containers",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            params=params,
            timeout=10
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get container status: {str(e)}")

def start_container(container_id: str, owner_id: str) -> dict:
    """
    Start a container via job_launcher
    """
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/containers/{container_id}/start",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={"owner_id": owner_id},
            timeout=15
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start container: {str(e)}")

def stop_container(container_id: str, owner_id: str) -> dict:
    """
    Stop a container via job_launcher
    """
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/containers/{container_id}/stop",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={"owner_id": owner_id},
            timeout=15
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop container: {str(e)}")

def restart_container(container_id: str, owner_id: str) -> dict:
    """
    Restart a container via job_launcher
    """
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/containers/{container_id}/restart",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={"owner_id": owner_id},
            timeout=15
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart container: {str(e)}")

def remove_container(container_id: str, owner_id: str, force: bool = False) -> dict:
    """
    Remove a container via job_launcher
    """
    try:
        response = requests.delete(
            f"{LAUNCHER_URL}/containers/{container_id}",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={"owner_id": owner_id, "force": force},
            timeout=15
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove container: {str(e)}")
