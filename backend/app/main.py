from fastapi import FastAPI
from controller import auth_controller
from services.config import settings
from fastapi.middleware.cors import CORSMiddleware

print("Using Keycloak URL:", settings.KEYCLOAK_URL)

app = FastAPI(title="FastAPI with Keycloak",root_path="/api")

app.include_router(auth_controller.router)

origins = [
    "http://localhost:5173",
    "https://htit-monitor.marvin-carstensen.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # allow all origins with ["*"] in development
    allow_credentials=True,
    allow_methods=["*"],  # or ["GET", "POST"] for stricter control
    allow_headers=["*"],
)