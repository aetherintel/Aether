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
    neo4j: bool = True

def run_similarity(channel: str, tg_session: str) -> dict:
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/similar",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={
                "channel": channel,
                "tg_session": tg_session
            },
            timeout=30
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity job failed: {str(e)}")

def start_scraper(channels: list[str], tg_session: str) -> str:
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/scrape",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={
                "channels": channels,
                "tg_session": tg_session
            },
            timeout=10
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json().get("container_id", "unknown")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper job failed: {str(e)}")

def launch_full_scrape_job(channel: str, tg_session: str, recursive: bool = True, neo4j: bool = True) -> dict:
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
                "neo4j": neo4j
            },
            timeout=15
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch scraper job: {str(e)}")

def launch_live_scrape_job(channels: list[str], tg_session: str) -> dict:
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
                "mode": "live"
            },
            timeout=10
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live scraper job failed: {str(e)}")
