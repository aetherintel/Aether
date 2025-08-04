from typing import TypedDict
from fastapi import Depends
from services.auth0_service import get_current_user
from services.config import settings

class UserCtx(TypedDict):
    id: str
    roles: list[str]

def user_ctx(token = Depends(get_current_user)) -> UserCtx:
    # Auth0 uses 'sub' for user ID, similar to Keycloak
    user_id = token["sub"]
    
    # Extract roles from various possible locations
    roles = []
    
    # Custom claims (recommended approach)
    roles_claim = token.get(f"{settings.AUTH0_AUDIENCE}/roles", [])
    if roles_claim:
        roles.extend(roles_claim)
    
    # Permissions (RBAC)
    permissions = token.get("permissions", [])
    roles.extend(permissions)
    
    # App metadata
    app_metadata = token.get("app_metadata", {})
    if "roles" in app_metadata:
        roles.extend(app_metadata["roles"])
    
    return {
        "id": user_id,
        "roles": roles,
    }

def is_admin(ctx: UserCtx) -> bool:
    return "admin" in ctx["roles"]