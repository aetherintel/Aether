from fastapi import APIRouter, Depends, HTTPException
import requests
from services.config import settings
from services.keycloak_service import get_current_user, has_role
from pydantic import BaseModel
router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    firstname: str
    lastname: str
    password: str


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
def login(data: LoginRequest):
    token_url = f"{settings.KEYCLOAK_URL}/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "username": data.username,
        "password": data.password,
    }
    headers = { "Content-Type": "application/x-www-form-urlencoded" }
    response = requests.post(token_url, data=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Login failed")
    return response.json()

@router.post("/refresh")
def refresh(data: TokenRefreshRequest):
    token_url = f"{settings.KEYCLOAK_URL}/protocol/openid-connect/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "refresh_token": data.refresh_token,
    }
    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Refresh failed")
    return response.json()

@router.post("/logout")
def logout(data: TokenRefreshRequest):
    logout_url = f"{settings.KEYCLOAK_URL}/protocol/openid-connect/logout"
    payload = {
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "refresh_token": data.refresh_token,
    }
    response = requests.post(logout_url, data=payload)
    if response.status_code != 204:
        raise HTTPException(status_code=400, detail="Logout failed")
    return {"message": "Logged out"}

def get_admin_token():
    token_url = f"{settings.KEYCLOAK_BASE_URL}/realms/HotTopics/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET
    }
    response = requests.post(token_url, data=data)
    print(response)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Admin login failed")
    return response.json()["access_token"]


@router.post("/register")
def register(data: RegisterRequest):
    token = get_admin_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    print(token)
    user_url = f"{settings.KEYCLOAK_BASE_URL}/admin/realms/HotTopics/users"

    user_payload = {
        "username": data.username,
        "email": data.email,
        "enabled": True,
        "firstName": data.firstname,
        "lastName": data.lastname,
        "enabled": True,
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
