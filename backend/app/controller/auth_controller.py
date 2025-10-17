from typing import List, Optional, TypedDict
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer
import os
import requests
import logging
from services.keycloak_service import get_current_user, has_role
from controller.telegram_controller import remove_container, restart_container, run_similarity, start_container, start_scraper, launch_full_scrape_job, launch_live_scrape_job, stop_container
from pydantic import BaseModel
import docker
from services.auth_ctx import user_ctx, is_admin, UserCtx
JOB_LAUNCHER_URL = os.getenv("JOB_LAUNCHER_URL", "http://job-launcher:9001")
JOB_SECRET_TOKEN = os.getenv("JOB_SECRET_TOKEN", "changeme")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
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
        "redirect_uri": os.getenv("FRONTEND_URL", "http://46.243.55.90/"),
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID")
    }
    print(f"Sending verification email to user {user_id} with params: {params}")
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

# backend/app/routers/auth.py - Update telegram_status endpoint

@router.post("/telegram/status")
def telegram_status(
    req: StatusRequest, 
    user: UserCtx = Depends(user_ctx)
):
    """
    Get ALL job statuses (telegram, translation, image) filtered by case_id and user
    """
    try:
        # Call job-launcher to get ALL jobs
        params = {
            "owner_id": user["id"],
        }
        
        if req.case_id:
            params["case_id"] = req.case_id
        
        response = requests.get(
            f"{JOB_LAUNCHER_URL}/jobs",
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            params=params,  # Use params instead of json for GET
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # Transform job data to match frontend container format
        containers = []
        for job in data.get("jobs", []):
            # Map job status to container status
            status_map = {
                "queued": "pending",
                "started": "running",
                "finished": "exited",
                "failed": "failed"
            }
            
            # Format channels display
            channels_display = ", ".join(job.get("channels", [])) if job.get("channels") else job.get("message_id", "N/A")
            
            # Determine image/name based on queue
            queue = job.get("queue", "unknown")
            if "telegram" in queue:
                image = "telegram-scraper"
            elif "translation" in queue:
                image = "translation-worker"
            elif "image" in queue:
                image = "image-worker"
            else:
                image = "unknown-worker"
            
            containers.append({
                "id": job.get("job_id", "unknown"),
                "name": f"{job.get('mode', 'job')}_{job.get('job_id', 'unknown')[:8]}",
                "status": status_map.get(job.get("status", "unknown"), "unknown"),
                "image": image,
                "labels": {
                    "case_id": str(job.get("case_id", "")),
                    "owner_id": job.get("owner_id", ""),
                    "channels": channels_display,
                    "mode": job.get("mode", "unknown"),
                    "queue": queue
                },
                "created": job.get("created_at"),
                "case_id": job.get("case_id"),
                "owner_id": job.get("owner_id"),
                "channels": channels_display,
                "mode": job.get("mode", "unknown"),
                "session": job.get("session_name", "N/A"),
                "runtime": job.get("runtime"),
                "queue": queue
            })
        
        return {
            "containers": containers,
            "total": len(containers),
            "filtered_by_case": req.case_id,
            "user_id": user["id"],
            "queues": data.get("queues", [])
        }
        
    except requests.RequestException as e:
        logger.error(f"Error fetching jobs from launcher: {e}")
        raise HTTPException(status_code=503, detail="Job launcher unavailable")


@router.delete("/telegram/job/{job_id}")
def cancel_telegram_job(
    job_id: str,
    user: UserCtx = Depends(user_ctx)
):
    """
    Cancel/remove a specific job (works for all job types)
    """
    try:
        response = requests.delete(
            f"{JOB_LAUNCHER_URL}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            timeout=10
        )
        response.raise_for_status()
        
        return response.json()
        
    except requests.RequestException as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        if e.response and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=503, detail="Job launcher unavailable")


@router.post("/telegram/job/{job_id}/requeue")
def requeue_failed_job(
    job_id: str,
    user: UserCtx = Depends(user_ctx)
):
    """
    Requeue a failed job
    """
    try:
        response = requests.post(
            f"{JOB_LAUNCHER_URL}/jobs/{job_id}/requeue",
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            timeout=10
        )
        response.raise_for_status()
        
        return response.json()
        
    except requests.RequestException as e:
        logger.error(f"Error requeuing job {job_id}: {e}")
        if e.response and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Job not found")
        elif e.response and e.response.status_code == 400:
            raise HTTPException(status_code=400, detail="Job is not failed")
        raise HTTPException(status_code=503, detail="Job launcher unavailable")


@router.get("/telegram/stats")
def get_job_stats(
    case_id: Optional[int] = None,
    user: UserCtx = Depends(user_ctx)
):
    """
    Get job statistics
    """
    try:
        params = {"owner_id": user["id"]}
        if case_id:
            params["case_id"] = case_id
        
        response = requests.get(
            f"{JOB_LAUNCHER_URL}/jobs/stats",
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        return response.json()
        
    except requests.RequestException as e:
        logger.error(f"Error fetching job stats: {e}")
        raise HTTPException(status_code=503, detail="Job launcher unavailable")

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
# backend/controller/auth_controller.py

@router.post("/telegram/container/{job_id}/stop")
def stop_telegram_job(job_id: str, user: UserCtx = Depends(user_ctx)):
    """Cancel/stop a running job"""
    try:
        response = requests.delete(
            f"{JOB_LAUNCHER_URL}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            json={"owner_id": user["id"]},
            timeout=5
        )
        response.raise_for_status()
        return {"message": f"Job cancelled", "status": "cancelled"}
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(404, "Job not found")
        raise HTTPException(500, str(e))



@router.delete("/telegram/container/{job_id}/remove")
def remove_telegram_job(
    job_id: str, 
    user: UserCtx = Depends(user_ctx),
    force: bool = False
):
    """Cancel and remove a job"""
    try:
        response = requests.delete(
            f"{JOB_LAUNCHER_URL}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {JOB_SECRET_TOKEN}"},
            json={"owner_id": user["id"], "force": force},
            timeout=5
        )
        response.raise_for_status()
        return {"message": "Job cancelled and removed", "status": "removed"}
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(404, "Job not found")
        raise HTTPException(500, str(e))
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
        case_id=req.case_id or None,        
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
