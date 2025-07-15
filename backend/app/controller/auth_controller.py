from typing import List, Optional, TypedDict
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer
import os
import requests
from services.keycloak_service import get_current_user, has_role
from controller.telegram_controller import remove_container, restart_container, run_similarity, start_container, start_scraper, launch_full_scrape_job, launch_live_scrape_job, stop_container
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
    case_id: Optional[int] = None

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
    case_id: Optional[int] = None  # Optional case ID for tracking

class StatusRequest(BaseModel):
    case_id: Optional[int] = None


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
def user_route(user=Depends(has_role(["user", "admin", "default-roles-aether"]))):
    return {"message": f"Hello, {user['preferred_username']}! You are a user."}

@router.get("/admin")
def admin_route(user=Depends(has_role(["admin"]))):
    return {"message": f"Hello, Admin {user['preferred_username']}!"}

def get_admin_token():
    token_url = f"{os.getenv('KEYCLOAK_URL')}/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("KEYCLOAK_ADMIN_CLIENT_ID"),
        "client_secret": os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET")
    }
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Admin login failed")
    return response.json()["access_token"]

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # FIX: Container-interne URL für Login
    token_url = f"{os.getenv('KEYCLOAK_INTERNAL_URL')}/protocol/openid-connect/token"
    print(f"Using token URL: {token_url}")
    payload = {
        "grant_type": "password",
        "client_id": form_data.client_id or os.getenv("KEYCLOAK_CLIENT_ID"),
        "client_secret": form_data.client_secret or os.getenv("KEYCLOAK_CLIENT_SECRET"),
        "username": form_data.username,
        "password": form_data.password,
    }
    print(f"Login payload: {payload}")
    headers = { "Content-Type": "application/x-www-form-urlencoded" }
    response = requests.post(token_url, data=payload, headers=headers)
    print(f"Login response: {response.status_code} - {response.text} - {response.text}")
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Login failed")
    return response.json()

@router.post("/refresh")
def refresh(data: TokenRefreshRequest):
    # FIX: Container-interne URL für Refresh
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
    # FIX: Container-interne URL für Logout
    logout_url = f"{os.getenv('KEYCLOAK_INTERNAL_URL')}/protocol/openid-connect/logout"
    payload = {
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID"),
        "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
        "refresh_token": data.refresh_token,
    }
    response = requests.post(logout_url, data=payload)
    if response.status_code != 204:
        raise HTTPException(status_code=400, detail="Logout failed")
    return {"message": "Logged out"}

def send_verification_email(user_id: str, admin_token: str):
    """Sendet Verification Email an User"""
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }
    
    # FIX: Container-interne URL für Admin API
    email_url = f"{os.getenv('KEYCLOAK_BASE_URL')}/admin/realms/Aether/users/{user_id}/execute-actions-email"

    # Query Parameter für Redirect (EXTERN URL!)
    params = {
        # TODO: redirect URL einfügen
        "redirect_uri": os.getenv("FRONTEND_URL", "http://localhost/"),
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID")
    }
    
    actions_payload = ["VERIFY_EMAIL"]
    
    response = requests.put(email_url, headers=headers, json=actions_payload, params=params)
    
    if response.status_code != 204:
        print(f"Failed to send verification email: {response.status_code} - {response.text}")
    else:
        print(f"Verification email sent to user {user_id}")

@router.post("/register")
def register(data: RegisterRequest):
    token = get_admin_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    user_url = f"{os.getenv('KEYCLOAK_BASE_URL')}/admin/realms/Aether/users"
    
    # User payload MIT Email Verification
    user_payload = {
        "username": data.username,
        "email": data.email,
        "enabled": True,
        "emailVerified": False,  # ← WICHTIG: Email nicht verified!
        "firstName": data.firstname,
        "lastName": data.lastname,
        "requiredActions": ["VERIFY_EMAIL"],  # ← REQUIRED ACTIONS setzen!
        "credentials": [{
            "type": "password",
            "value": data.password,
            "temporary": False
        }]
    }
    
    # User erstellen
    response = requests.post(user_url, headers=headers, json=user_payload)
    
    if response.status_code == 201:
        # User ID aus Location Header extrahieren
        location = response.headers.get('Location')
        user_id = location.split('/')[-1]
        
        # Verification Email senden
        send_verification_email(user_id, token)
        
        return {"message": "User registered successfully. Check your email for verification."}
    elif response.status_code == 409:
        raise HTTPException(status_code=409, detail="User already exists")
    else:
        raise HTTPException(status_code=500, detail=f"Failed to register user {response.status_code}: {response.text}")


# Falls du die andere Funktion auch verwenden willst, hier der Fix:
def resend_verification(email_address: str):  # Parameter umbenannt
    """Resend verification email für bestehenden User"""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # User by email finden - KORRIGIERT!
    users_url = f"{os.getenv('KEYCLOAK_BASE_URL')}/admin/realms/Aether/users?email={email_address}"
    response = requests.get(users_url, headers=headers)
    
    if response.status_code == 200 and response.json():
        user = response.json()[0]
        user_id = user['id']
        
        # Required Actions setzen und Email senden
        user_url = f"{os.getenv('KEYCLOAK_BASE_URL')}/admin/realms/Aether/users/{user_id}"
        update_payload = {"requiredActions": ["VERIFY_EMAIL"]}
        requests.put(user_url, headers=headers, json=update_payload)
        
        # Email senden
        email_url = f"{os.getenv('KEYCLOAK_BASE_URL')}/admin/realms/Aether/users/{user_id}/execute-actions-email"
        email_response = requests.put(email_url, headers=headers, json=["VERIFY_EMAIL"])
        
        if email_response.status_code == 204:
            return {"message": "Verification email sent"}
        else:
            return {"message": "Failed to send email"}
    else:
        raise HTTPException(status_code=404, detail="User not found")
@router.get("/me")
def get_user(token: str = Depends(oauth2_scheme)):
    return {"token": token}

@router.post("/telegram/status")
def telegram_status(
    req: StatusRequest, 
    user: UserCtx = Depends(user_ctx)
):
    """
    Get telegram job containers filtered by case_id and user ownership
    """
    containers = docker_client.containers.list(all=True)
    container_list = []

    image_name = (
        f"{os.getenv('DOCKER_USERNAME')}/aether-telegram_scraper:latest"
        if os.getenv("ENVIRONMENT") == "prod"
        else "telegram-job:latest"
    )
    
    for c in containers:
        try:
            image_tags = c.image.tags if c.image and c.image.tags else []
            
            is_telegram_job = False
            if image_tags:
                is_telegram_job = any(image_name in tag for tag in image_tags)
            
            if is_telegram_job:
                # Check if container belongs to the current user
                container_owner = c.labels.get("OWNER_ID")
                if container_owner != user["id"]:
                    continue  # Skip containers not owned by current user
                
                # Check case_id filter if provided
                if req.case_id is not None and c.labels.get("case_id") is not None:
                    container_case_id = c.labels.get("case_id")
                    print(c.labels)
                    # Convert to int for comparison, skip if no case_id or doesn't match
                    try:
                        if container_case_id is None or int(container_case_id) != req.case_id:
                            continue
                    except (ValueError, TypeError):
                        continue  # Skip if case_id is not a valid integer
                
                container_info = {
                    "id": c.id,
                    "name": c.name,
                    "image": image_tags[0] if image_tags else None,
                    "status": c.status,
                    "labels": c.labels,
                    "created": c.attrs['Created'],
                    # Extract useful info from labels for frontend
                    "case_id": c.labels.get("case_id"),
                    "owner_id": c.labels.get("owner_id"),
                    "channels": c.labels.get("channels", ""),
                    "mode": c.labels.get("mode", "unknown"),
                    "session": c.labels.get("tg_session", "unknown")
                }
                container_list.append(container_info)
                
        except (docker.errors.ImageNotFound, docker.errors.APIError) as e:
            print(f"Warning: Container {c.id} references a missing image: {e}")
            
            # For containers with missing images, still check if they're telegram jobs
            if (c.labels and "telegram" in str(c.labels).lower()) or \
               (c.name and "telegram" in c.name.lower()):
                
                # Apply same filtering logic
                container_owner = c.labels.get("owner_id")
                if container_owner != user["id"]:
                    continue
                
                if req.case_id is not None:
                    container_case_id = c.labels.get("case_id")
                    try:
                        if container_case_id is None or int(container_case_id) != req.case_id:
                            continue
                    except (ValueError, TypeError):
                        continue
                
                container_info = {
                    "id": c.id,
                    "name": c.name,
                    "image": "Image not found",
                    "status": c.status,
                    "labels": c.labels,
                    "created": c.attrs['Created'],
                    "case_id": c.labels.get("case_id"),
                    "owner_id": c.labels.get("owner_id"),
                    "channels": c.labels.get("channels", ""),
                    "mode": c.labels.get("mode", "unknown"),
                    "session": c.labels.get("tg_session", "unknown")
                }
                container_list.append(container_info)
            continue
        except Exception as e:
            print(f"Unexpected error processing container {c.id}: {e}")
            continue
    
    return {
        "containers": container_list,
        "total": len(container_list),
        "filtered_by_case": req.case_id,
        "user_id": user["id"]
    }


# Add this to your existing FastAPI router in the auth module

@router.post("/telegram/container/{container_id}/start")
def start_telegram_container(
    container_id: str, 
    user: UserCtx = Depends(user_ctx)
):
    """Start a specific telegram container via job_launcher"""
    try:
        result = start_container(container_id, user["id"])
        return {
            "message": result.get("message", f"Container {container_id[:12]} started successfully"),
            "status": result.get("status", "running"),
            "container_id": container_id
        }
    except HTTPException:
        raise  # Re-raise HTTPExceptions from the helper
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/telegram/container/{container_id}/stop")
def stop_telegram_container(
    container_id: str, 
    user: UserCtx = Depends(user_ctx)
):
    """Stop a specific telegram container via job_launcher"""
    try:
        result = stop_container(container_id, user["id"])
        return {
            "message": result.get("message", f"Container {container_id[:12]} stopped successfully"),
            "status": result.get("status", "exited"),
            "container_id": container_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/telegram/container/{container_id}/restart")
def restart_telegram_container(
    container_id: str, 
    user: UserCtx = Depends(user_ctx)
):
    """Restart a specific telegram container via job_launcher"""
    try:
        print(f"Restarting container {container_id} for user {user['id']}")
        result = restart_container(container_id, user["id"])
        return {
            "message": result.get("message", f"Container {container_id[:12]} restarted successfully"),
            "status": result.get("status", "running"),
            "container_id": container_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.delete("/telegram/container/{container_id}/remove")
def remove_telegram_container(
    container_id: str, 
    user: UserCtx = Depends(user_ctx),
    force: bool = False
):
    """Remove a specific telegram container via job_launcher"""
    try:
        result = remove_container(container_id, user["id"], force)
        print(f"Removing container {container_id} for user {user['id']} with force={force}")
        return {
            "message": result.get("message", f"Container {container_id[:12]} removed successfully"),
            "status": "removed",
            "container_id": container_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
@router.post("/telegram/similar")
def telegram_similar(req: ChannelInput, user: UserCtx = Depends(user_ctx)):
    result = run_similarity(req.channel,
                            tg_session=req.tg_session, 
                            owner_id=user["id"], 
                            case_id = req.case_id or None)  # ← NEW
    return {"similar": result}

@router.post("/telegram/scrape")
def telegram_scrape(
    req: ChannelListInput,
    user: UserCtx = Depends(user_ctx)             # ← decode token once
):
    container_id = start_scraper(
        channels=req.channels,
        tg_session=req.tg_session,
        owner_id=user["id"],                       
        case_id=req.case_id or None,               # ← NEW
    )
    return {"message": "Scraper started", "container_id": container_id}

@router.post("/telegram/full")
def telegram_full_scrape(req: ExtendedScrapeRequest, user: UserCtx = Depends(user_ctx)):
    return launch_full_scrape_job(
        channel=req.channel,
        tg_session=req.tg_session,
        recursive=req.recursive,
        neo4j=req.neo4j,
        owner_id=user["id"],  # ← NEW
        case_id=req.case_id or None  # ← NEW
    )
@router.post("/telegram/live")
def telegram_live_scrape(req: ChannelListInput, user: UserCtx = Depends(user_ctx)):
    return launch_live_scrape_job(channels=req.channels,tg_session=req.tg_session, neo4j=req.neo4j, owner_id=user["id"], case_id= req.case_id or None)
