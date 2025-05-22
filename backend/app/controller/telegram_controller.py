import requests
from fastapi import HTTPException
from services.config import settings  # assuming you keep shared settings here
import os # for environment variables
LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL") or "http://job-launcher:9001"
LAUNCHER_SECRET = os.getenv("JOB_SECRET_TOKEN") or "changeme"

def run_similarity(channel: str) -> dict:
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/similar",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={"channel": channel},
            timeout=30
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity job failed: {str(e)}")

def start_scraper(channels: list[str]) -> str:
    try:
        response = requests.post(
            f"{LAUNCHER_URL}/scrape",
            headers={"Authorization": f"Bearer {LAUNCHER_SECRET}"},
            json={"channels": channels},
            timeout=10
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)
        return response.json().get("container_id", "unknown")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper job failed: {str(e)}")
