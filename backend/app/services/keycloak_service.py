from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, jwk, JWTError
from typing import List
import requests
from services.config import settings

# OAuth2 configuration for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# JWKS endpoint
PUBLIC_KEY_URL = f"{settings.KEYCLOAK_URL}/protocol/openid-connect/certs"

# Get and cache public keys
jwks = requests.get(PUBLIC_KEY_URL).json()

def get_public_key(kid: str):
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return jwk.construct(key)
    raise HTTPException(status_code=401, detail="Public key not found")

def decode_token(token: str):
    try:
        unverified_header = jwt.get_unverified_header(token)
        public_key = get_public_key(unverified_header["kid"])
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )
        aud_claim = payload.get("aud", [])
        print(f"Audience claim: {aud_claim}")
        if isinstance(aud_claim, str):
            aud_claim = [aud_claim]
        print(settings.KEYCLOAK_CLIENT_ID)
        if settings.KEYCLOAK_CLIENT_ID not in aud_claim:
            raise HTTPException(status_code=403, detail="Invalid token: audience mismatch")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=403, detail=f"Invalid token: {str(e)}")

def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

def has_role(required_roles: List[str]):
    def role_checker(user=Depends(get_current_user)):
        user_roles = user.get("realm_access", {}).get("roles", [])
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user
    return role_checker
