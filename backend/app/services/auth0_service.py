from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, jwk, JWTError
from typing import List
import requests
from services.config import settings
import json

# OAuth2 configuration for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# JWKS endpoint for Auth0
PUBLIC_KEY_URL = f"{settings.AUTH0_BASE_URL}/.well-known/jwks.json"

# Cache for JWKS
_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if not _jwks_cache:
        response = requests.get(PUBLIC_KEY_URL)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache

def get_public_key(kid: str):
    jwks = get_jwks()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return jwk.construct(key)
    raise HTTPException(status_code=401, detail="Public key not found")

def decode_token(token: str):
    try:
        unverified_header = jwt.get_unverified_header(token)
        print(f"Header: {unverified_header}")
        
        # Decode without verification first to see the payload
        unverified_payload = jwt.get_unverified_claims(token)
        print(f"Payload (unverified): {unverified_payload}")
        print(f"Audience in token: {unverified_payload.get('aud')}")
        print(f"Expected audience: {settings.AUTH0_AUDIENCE}")
        print(f"Issuer in token: {unverified_payload.get('iss')}")
        
        if 'kid' not in unverified_header:
            raise HTTPException(status_code=401, detail="Token missing 'kid'")
        
        public_key = get_public_key(unverified_header["kid"])
        
        # Try different audience configurations
        try:
            # Option 1: Use the API audience
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                audience=settings.AUTH0_AUDIENCE,
                issuer=f"{settings.AUTH0_BASE_URL}/"
            )
            print("✅ Decoded with API audience")
            return payload
        except JWTError as e1:
            print(f"❌ API audience failed: {e1}")
            
            try:
                # Option 2: Use client ID as audience (for ID tokens)
                payload = jwt.decode(
                    token,
                    key=public_key,
                    algorithms=["RS256"],
                    audience=settings.AUTH0_CLIENT_ID,
                    issuer=f"{settings.AUTH0_BASE_URL}/"
                )
                print("✅ Decoded with client ID audience")
                return payload
            except JWTError as e2:
                print(f"❌ Client ID audience failed: {e2}")
                
                try:
                    # Option 3: No audience verification
                    payload = jwt.decode(
                        token,
                        key=public_key,
                        algorithms=["RS256"],
                        options={"verify_aud": False},
                        issuer=f"{settings.AUTH0_BASE_URL}/"
                    )
                    print("✅ Decoded without audience verification")
                    return payload
                except JWTError as e3:
                    print(f"❌ No audience verification failed: {e3}")
                    raise HTTPException(status_code=403, detail=f"All decode attempts failed: {e1}, {e2}, {e3}")
        
    except JWTError as e:
        raise HTTPException(status_code=403, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation error: {str(e)}")

def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

def has_role(required_roles: List[str]):
    def role_checker(user=Depends(get_current_user)):
        # Auth0 stores roles in different places depending on configuration
        # Common locations: custom claims, app_metadata, or permissions
        user_roles = []
        
        # Check custom claims (namespace format)
        roles_claim = user.get(f"{settings.AUTH0_AUDIENCE}/roles", [])
        if roles_claim:
            user_roles.extend(roles_claim)
        
        # Check permissions (if using RBAC)
        permissions = user.get("permissions", [])
        user_roles.extend(permissions)
        
        # Check app_metadata (if accessible in token)
        app_metadata = user.get("app_metadata", {})
        if "roles" in app_metadata:
            user_roles.extend(app_metadata["roles"])
        
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user
    return role_checker