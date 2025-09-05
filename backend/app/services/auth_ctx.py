from typing import TypedDict
from fastapi import Depends
from services.keycloak_service import get_current_user 

class UserCtx(TypedDict):
    id: str
    roles: list[str]

def user_ctx(token = Depends(get_current_user)) -> UserCtx:
    return {
        "id":   token["sub"],
        "roles": token.get("realm_access", {}).get("roles", []),
    }

def is_admin(ctx: UserCtx) -> bool:
    return "admin" in ctx["roles"]