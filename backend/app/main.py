from fastapi import FastAPI
from controller import auth_controller
from services.config import settings

print("Using Keycloak URL:", settings.KEYCLOAK_URL)

app = FastAPI(title="FastAPI with Keycloak")

app.include_router(auth_controller.router, prefix="/api")
