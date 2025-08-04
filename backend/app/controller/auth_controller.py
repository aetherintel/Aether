from typing import List, Optional, TypedDict
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer
import os
import requests
from services.auth0_service import get_current_user, has_role
from services.auth_ctx import user_ctx, is_admin, UserCtx
from services.config import settings
import json
from controller.telegram_controller import remove_container, restart_container, run_similarity, start_container, start_scraper, launch_full_scrape_job, launch_live_scrape_job, stop_container
from pydantic import BaseModel
import docker
from jose import jwt, jwk, JWTError
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

def get_management_token():
    """Get Auth0 Management API token"""
    token_url = f"{settings.AUTH0_BASE_URL}/oauth/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": settings.AUTH0_MANAGEMENT_CLIENT_ID,
        "client_secret": settings.AUTH0_MANAGEMENT_CLIENT_SECRET,
        "audience": f"{settings.AUTH0_BASE_URL}/api/v2/"
    }
    response = requests.post(token_url, json=data)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Management API login failed")
    return response.json()["access_token"]

# STEP 2: Debug endpoint to check your Auth0 configuration
@router.get("/debug/auth0-config")
def debug_auth0_config():
    """Debug Auth0 configuration"""
    try:
        # Test management token
        management_token = get_management_token()
        
        # Get application details
        headers = {"Authorization": f"Bearer {management_token}"}
        app_url = f"{settings.AUTH0_BASE_URL}/api/v2/clients/{settings.AUTH0_CLIENT_ID}"
        
        app_response = requests.get(app_url, headers=headers)
        
        if app_response.status_code == 200:
            app_data = app_response.json()
            return {
                "client_id": app_data.get("client_id"),
                "name": app_data.get("name"),
                "app_type": app_data.get("app_type"),
                "grant_types": app_data.get("grant_types", []),
                "callbacks": app_data.get("callbacks", []),
                "web_origins": app_data.get("web_origins", []),
                "allowed_origins": app_data.get("allowed_origins", [])
            }
        else:
            return {"error": f"Could not fetch app config: {app_response.text}"}
            
    except Exception as e:
        return {"error": str(e)}

# STEP 3: Check connections and their configuration
@router.get("/debug/connections")
def debug_connections():
    """Debug database connections"""
    try:
        management_token = get_management_token()
        headers = {"Authorization": f"Bearer {management_token}"}
        
        # Get all connections
        connections_url = f"{settings.AUTH0_BASE_URL}/api/v2/connections"
        response = requests.get(connections_url, headers=headers)
        
        if response.status_code == 200:
            connections = response.json()
            
            # Filter database connections
            db_connections = []
            for conn in connections:
                if conn["strategy"] == "auth0":  # Database connections
                    db_connections.append({
                        "name": conn["name"],
                        "strategy": conn["strategy"],
                        "enabled_clients": conn.get("enabled_clients", []),
                        "is_domain_connection": conn.get("is_domain_connection", False),
                        "options": {
                            "password_policy": conn.get("options", {}).get("password_policy"),
                            "enabled_database_customization": conn.get("options", {}).get("enabled_database_customization")
                        }
                    })
            
            return {
                "database_connections": db_connections,
                "your_client_id": settings.AUTH0_CLIENT_ID
            }
        else:
            return {"error": f"Could not fetch connections: {response.text}"}
            
    except Exception as e:
        return {"error": str(e)}
@router.get("/debug/my-token")
def debug_my_token(token: str = Depends(oauth2_scheme)):
    """See what's actually in your token"""
    try:
        unverified_payload = jwt.get_unverified_claims(token)
        return {
            "full_payload": unverified_payload,
            "custom_claims": {
                "aether_roles": unverified_payload.get(f"{settings.AUTH0_AUDIENCE}/roles", "NOT FOUND"),
                "app_metadata": unverified_payload.get("app_metadata", "NOT FOUND"),
                "permissions": unverified_payload.get("permissions", "NOT FOUND")
            },
            "standard_claims": {
                "sub": unverified_payload.get("sub"),
                "aud": unverified_payload.get("aud"),
                "scope": unverified_payload.get("scope")
            }
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    token_url = f"{settings.AUTH0_BASE_URL}/oauth/token"
    
    payload = {
        "grant_type": "password",
        "client_id": settings.AUTH0_CLIENT_ID,
        "client_secret": settings.AUTH0_CLIENT_SECRET,
        "username": form_data.username,
        "password": form_data.password,
        "audience": settings.AUTH0_AUDIENCE,
        "scope": "openid profile email",
        "realm": "con_UyPZREuwX0ZCkly2"
    }
    
    # CRITICAL: Use data= and headers, NOT json=
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(token_url, data=payload, headers=headers)  # ← data, not json
    
    print(f"Request URL: {token_url}")
    print(f"Request payload: {payload}")
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    if response.status_code != 200:
        error_data = response.json() if response.content else {}
        error_msg = error_data.get("error_description", "Login failed")
        raise HTTPException(status_code=401, detail=error_msg)
    
    return response.json()

@router.post("/refresh")
def refresh(data: TokenRefreshRequest):
    token_url = f"{settings.AUTH0_BASE_URL}/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": settings.AUTH0_CLIENT_ID,
        "client_secret": settings.AUTH0_CLIENT_SECRET,
        "refresh_token": data.refresh_token,
    }
    response = requests.post(token_url, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Refresh failed")
    return response.json()

@router.post("/register")
def register(data: RegisterRequest):
    management_token = get_management_token()
    headers = {
        "Authorization": f"Bearer {management_token}",
        "Content-Type": "application/json"
    }
    
    # Auth0 Management API endpoint for creating users
    users_url = f"{settings.AUTH0_BASE_URL}/api/v2/users"
    
    user_payload = {
        "email": data.email,
        "username": data.username,
        "password": data.password,
        "given_name": data.firstname,
        "family_name": data.lastname,
        "name": f"{data.firstname} {data.lastname}",
        "connection": "Username-Password-Authentication",  # Default DB connection
        "email_verified": False,
        "verify_email": True  # This will trigger verification email
    }
    
    response = requests.post(users_url, headers=headers, json=user_payload)
    
    if response.status_code == 201:
        return {"message": "User registered successfully. Check your email for verification."}
    elif response.status_code == 409:
        raise HTTPException(status_code=409, detail="User already exists")
    else:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {response.text}")

# Keep your existing protected routes - they'll work the same way
@router.get("/public")
def public_route():
    return {"message": "Anyone can access this"}

@router.get("/user")
def user_route(user=Depends(has_role(["user", "admin"]))):
    return {"message": f"Hello, {user.get('name', 'User')}! You are a user."}

@router.get("/admin")
def admin_route(user=Depends(has_role(["admin"]))):
    return {"message": f"Hello, Admin {user.get('name', 'Admin')}!"}

@router.get("/me")
def get_user(user=Depends(get_current_user)):
    return user

# Falls du die andere Funktion auch verwenden willst, hier der Fix:
def resend_verification(email_address: str):  # Parameter umbenannt
    """Resend verification email für bestehenden User"""
    token = get_management_token()
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
