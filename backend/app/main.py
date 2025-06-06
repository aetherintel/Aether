from fastapi import FastAPI

from backend.app.controller import message_controller
from controller import auth_controller
from controller import casefile_controller
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FastAPI with Keycloak",root_path="/api")

app.include_router(auth_controller.router)
app.include_router(casefile_controller.router)
app.include_router(message_controller.router)


origins = [
    "http://localhost:5173",
    "https://htit-monitor.marvin-carstensen.com",
    "http://localhost:8080",
    "http://localhost:9001",   # job launcher
    "http://keycloak:8080",   # keycloak

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # allow all origins with ["*"] in development
    allow_credentials=True,
    allow_methods=["*"],  # or ["GET", "POST"] for stricter control
    allow_headers=["*"],
)