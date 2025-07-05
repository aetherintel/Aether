from typing import List, TypedDict
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer
import os
import requests
from services.keycloak_service import get_current_user, has_role
from controller.telegram_controller import run_similarity, start_scraper, launch_full_scrape_job, launch_live_scrape_job
from pydantic import BaseModel
import docker
from services.auth_ctx import user_ctx, is_admin, UserCtx

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
docker_client = docker.from_env()

class ExtendedScrapeRequest(BaseModel):
    channel: str
    tg_session: str
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
    tg_session: str

class ChannelListInput(BaseModel):
    channels: List[str]
    tg_session: str
    neo4j: bool = True

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

class UserCtx(TypedDict):
    id: str           # Keycloak "sub"
    roles: list[str]

def user_ctx(token_data: dict = Depends(get_current_user)) -> UserCtx:
    return {
        "id": token_data["sub"],
        "roles": token_data.get("realm_access", {}).get("roles", []),
    }

def is_admin(ctx: UserCtx) -> bool:
    return "admin" in ctx["roles"]

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
        try:
            image_tags = c.image.tags if c.image and c.image.tags else []
            
            is_telegram_job = False
            if image_tags:
                is_telegram_job = any("telegram-job" in tag for tag in image_tags)
            
            if is_telegram_job:
                container_list.append({
                    "id": c.id,
                    "name": c.name,
                    "image": image_tags[0] if image_tags else None,
                    "status": c.status,
                    "labels": c.labels,
                    "created": c.attrs['Created'],
                })
        except (docker.errors.ImageNotFound, docker.errors.APIError) as e:
            print(f"Warning: Container {c.id} references a missing image: {e}")
            
            if (c.labels and "telegram-job" in str(c.labels).lower()) or \
               (c.name and "telegram" in c.name.lower()):
                container_list.append({
                    "id": c.id,
                    "name": c.name,
                    "image": "Image not found",
                    "status": c.status,
                    "labels": c.labels,
                    "created": c.attrs['Created'],
                })
            continue
        except Exception as e:
            print(f"Unexpected error processing container {c.id}: {e}")
            continue
    
    return container_list

@router.post("/telegram/similar")
def telegram_similar(req: ChannelInput, user: UserCtx = Depends(user_ctx)):
    result = run_similarity(req.channel,tg_session=req.tg_session, owner_id=user["id"])  # ← NEW
    return {"similar": result}

@router.post("/telegram/scrape")
def telegram_scrape(
    req: ChannelListInput,
    user: UserCtx = Depends(user_ctx)             # ← decode token once
):
    container_id = start_scraper(
        channels=req.channels,
        tg_session=req.tg_session,
        owner_id=user["id"]                       # ← NEW
    )
    return {"message": "Scraper started", "container_id": container_id}

@router.post("/telegram/full")
def telegram_full_scrape(req: ExtendedScrapeRequest, user: UserCtx = Depends(user_ctx)):
    return launch_full_scrape_job(
        channel=req.channel,
        tg_session=req.tg_session,
        recursive=req.recursive,
        neo4j=req.neo4j,
        owner_id=user["id"]  # ← NEW
    )
@router.post("/telegram/live")
def telegram_live_scrape(req: ChannelListInput, user: UserCtx = Depends(user_ctx)):
    return launch_live_scrape_job(channels=req.channels,tg_session=req.tg_session, neo4j=req.neo4j, owner_id=user["id"])
