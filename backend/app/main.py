from fastapi import FastAPI
from contextlib import asynccontextmanager

from controller import message_controller
from controller import auth_controller
from controller import casefile_controller
from controller import graph_controller
from controller import telegram_auth_controller
from controller import queue_controller
from controller import scraper_controller
from controller import report_controller
from services.scheduler_service import start_scheduler
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown (if needed)

app = FastAPI(title="FastAPI with Keycloak", root_path="/api", lifespan=lifespan)

app.include_router(auth_controller.router)
app.include_router(casefile_controller.router)
app.include_router(message_controller.router)
app.include_router(graph_controller.router)
app.include_router(telegram_auth_controller.router)
app.include_router(scraper_controller.router)
app.include_router(queue_controller.router)
app.include_router(report_controller.router)

origins = [
    "http://localhost",
    "http://localhost:5173",
    "https://æther.tech",
    "https://xn--ther-uoa.tech"
    "http://localhost:8080",
    "http://localhost:9001",   # job launcher
    "http://keycloak:8080",   # keycloak
    "http://65.108.38.53 ⁠",
    "http://65.108.38.53 ⁠:8080",
    "http://65.108.38.53 ⁠:9001",
    "http://65.108.38.53 ⁠:5173",
    "https://aethery.cloud",
    "https://aethery.cloud:8080",
    "https://aethery.cloud:9001",
    "https://aethery.cloud:5173",
    "http://aethery.cloud",
    "http://aethery.cloud:8080",
    "http://aethery.cloud:9001",
    "http://aethery.cloud:5173"

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # allow all origins with ["*"] in development
    allow_credentials=True,
    allow_methods=["*"],  # or ["GET", "POST"] for stricter control
    allow_headers=["*"],
)