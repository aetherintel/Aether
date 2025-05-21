from fastapi import FastAPI
from controller import auth_controller
from services.config import settings

print("Using Keycloak URL:", settings.KEYCLOAK_URL)

app = FastAPI(title="FastAPI with Keycloak",root_path="/api")

app.include_router(auth_controller.router)
