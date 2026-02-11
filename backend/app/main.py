from fastapi import FastAPI
from contextlib import asynccontextmanager
import os

from controller import message_controller
from controller import auth_controller
from controller import casefile_controller
from controller import graph_controller
from controller import telegram_auth_controller
from controller import queue_controller
from controller import scraper_controller
from controller import report_controller
from controller import stats_controller 
from controller import dashboard_controller
from controller import dashboard_controller
from controller import agent_controller
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
app.include_router(stats_controller.router)
app.include_router(dashboard_controller.router)
app.include_router(agent_controller.router)

    # Dynamic origins from environment
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
    os.getenv("KEYCLOAK_URL", "http://keycloak:8080"),
    f"https://{os.getenv('PROD_DOMAIN', 'localhost')}",
    f"http://{os.getenv('PROD_DOMAIN', 'localhost')}",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # allow all origins with ["*"] in development
    allow_credentials=True,
    allow_methods=["*"],  # or ["GET", "POST"] for stricter control
    allow_headers=["*"],
)