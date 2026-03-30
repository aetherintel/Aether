from typing import List, Optional, TypedDict
from aether_lib.schemas.jobs import ChannelInput, ChannelListInput, ExtendedScrapeRequest, RegisterRequest, StatusRequest, TokenRefreshRequest
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer
import os
import requests
import logging
from services.keycloak_service import get_current_user, has_role
from controller.telegram_controller import remove_container, restart_container, run_similarity, start_container, start_scraper, launch_full_scrape_job, launch_live_scrape_job, stop_container
from pydantic import BaseModel
from services.auth_ctx import user_ctx, is_admin, UserCtx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://keycloak:8080/keycloak")


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
    token_url = f"{os.getenv('KEYCLOAK_INTERNAL_URL')}/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("KEYCLOAK_ADMIN_CLIENT_ID"),
        "client_secret": os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET")
    }
    logger.info(f"Getting Admin Token from: {token_url}")
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        logger.error(f"Admin login failed: {response.status_code} - {response.text}")
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
    print(f"Login response: {response.status_code} - {response.text}")
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
    email_url = f"{KEYCLOAK_BASE_URL}/admin/realms/Aether/users/{user_id}/execute-actions-email"

    # Query Parameter für Redirect (EXTERN URL!)
    params = {
        # TODO: redirect URL einfügen
        "redirect_uri": os.getenv("FRONTEND_URL", "http://localhost:5173/"),
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
    user_url = f"{KEYCLOAK_BASE_URL}/admin/realms/Aether/users"
    
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
    
    logger.info(f"Registering user at: {user_url}")
    logger.info(f"Payload: {user_payload}")

    # User erstellen
    response = requests.post(user_url, headers=headers, json=user_payload)
    
    logger.info(f"Register Response: {response.status_code} - {response.text}")
    
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
    users_url = f"{KEYCLOAK_BASE_URL}/admin/realms/Aether/users?email={email_address}"
    response = requests.get(users_url, headers=headers)
    
    if response.status_code == 200 and response.json():
        user = response.json()[0]
        user_id = user['id']
        
        # Required Actions setzen und Email senden
        user_url = f"{KEYCLOAK_BASE_URL}/admin/realms/Aether/users/{user_id}"
        update_payload = {"requiredActions": ["VERIFY_EMAIL"]}
        requests.put(user_url, headers=headers, json=update_payload)
        
        # Email senden
        email_url = f"{KEYCLOAK_BASE_URL}/admin/realms/Aether/users/{user_id}/execute-actions-email"
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

