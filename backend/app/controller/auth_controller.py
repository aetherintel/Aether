from typing import List
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer
import os
import requests
from services.keycloak_service import get_current_user, has_role
from controller.telegram_controller import run_similarity, start_scraper, launch_full_scrape_job, launch_live_scrape_job
from pydantic import BaseModel
import docker

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
docker_client = docker.from_env()

class ExtendedScrapeRequest(BaseModel):
    channel: str
    recursive: bool = True
    neo4j: bool = True

class LoginRequest(BaseModel):
    username: str
    password: str
    client_id: str
    client_secret: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    firstname: str
    lastname: str
    password: str

class ChannelInput(BaseModel):
    channel: str

class ChannelListInput(BaseModel):
    channels: List[str]

def get_admin_token():
    token_url = f"{os.getenv('KEYCLOAK_BASE_URL')}/realms/HotTopics/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("KEYCLOAK_ADMIN_CLIENT_ID"),
        "client_secret": os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET")
    }
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Admin login failed")
    return response.json()["access_token"]

@router.get("/public")
def public_route():
    return {"message": "Anyone can access this"}

@router.get("/user")
def user_route(user=Depends(has_role(["user", "admin", "default-roles-hottopics"]))):
    return {"message": f"Hello, {user['preferred_username']}! You are a user."}

@router.get("/admin")
def admin_route(user=Depends(has_role(["admin"]))):
    return {"message": f"Hello, Admin {user['preferred_username']}!"}

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    token_url = f"{os.getenv('KEYCLOAK_URL')}/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": form_data.client_id or os.getenv("KEYCLOAK_CLIENT_ID"),
        "client_secret": form_data.client_secret or os.getenv("KEYCLOAK_CLIENT_SECRET"),
        "username": form_data.username,
        "password": form_data.password,
    }
    headers = { "Content-Type": "application/x-www-form-urlencoded" }

    response = requests.post(token_url, data=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Login failed")

    return response.json()

@router.post("/refresh")
def refresh(data: TokenRefreshRequest):
    token_url = f"{os.getenv('KEYCLOAK_INTERNAL_URL')}/protocol/openid-connect/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID"),
        "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
        "refresh_token": data.refresh_token,
    }
    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Refresh failed")
    return response.json()

@router.post("/logout")
def logout(data: TokenRefreshRequest):
    logout_url = f"{os.getenv('KEYCLOAK_URL')}/protocol/openid-connect/logout"
    payload = {
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID"),
        "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
        "refresh_token": data.refresh_token,
    }
    response = requests.post(logout_url, data=payload)
    if response.status_code != 204:
        raise HTTPException(status_code=400, detail="Logout failed")
    return {"message": "Logged out"}

@router.post("/register")
def register(data: RegisterRequest):
    token = get_admin_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    user_url = f"{os.getenv('KEYCLOAK_BASE_URL')}/admin/realms/HotTopics/users"

    user_payload = {
        "username": data.username,
        "email": data.email,
        "enabled": True,
        "firstName": data.firstname,
        "lastName": data.lastname,
        "credentials": [{
            "type": "password",
            "value": data.password,
            "temporary": False
        }]
    }

    response = requests.post(user_url, headers=headers, json=user_payload)

    if response.status_code == 201:
        return {"message": "User registered successfully"}
    elif response.status_code == 409:
        raise HTTPException(status_code=409, detail="User already exists")
    else:
        raise HTTPException(status_code=500, detail=f"Failed to register user {response.status_code}: {response.text}")
    
@router.get("/me")
def get_user(token: str = Depends(oauth2_scheme)):
    return {"token": token}

@router.get("/telegram/status")
def telegram_status():
    containers = docker_client.containers.list(all=True)
    container_list = []
    for c in containers:
        if "telegram-job" in c.image.tags[0]:
            container_list.append({
                "id": c.id,
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else None,
                "status": c.status,
                "labels": c.labels,
                "created": c.attrs['Created'],
            })
    return container_list

@router.post("/telegram/similar")
def telegram_similar(req: ChannelInput, user=Depends(oauth2_scheme)):
    result = run_similarity(req.channel)
    return {"similar": result}

@router.post("/telegram/scrape")
def telegram_scrape(req: ChannelListInput, user=Depends(oauth2_scheme)):
    container_id = start_scraper(req.channels)
    return {"message": "Scraper started", "container_id": container_id}

@router.post("/telegram/full")
def telegram_full_scrape(req: ExtendedScrapeRequest, user=Depends(oauth2_scheme)):
    return launch_full_scrape_job(
        channel=req.channel,
        recursive=req.recursive,
        neo4j=req.neo4j
    )
@router.post("/telegram/live")
def telegram_live_scrape(req: ChannelListInput, user=Depends(oauth2_scheme)):
    return launch_live_scrape_job(channels=req.channels)
