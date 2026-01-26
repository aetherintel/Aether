import os
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Set env vars for testing before imports
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"
os.environ["JWT_SECRET_KEY"] = "secret"
os.environ["JWT_ALGORITHM"] = "HS256"

# Keycloak mocks
os.environ["KEYCLOAK_URL"] = "http://mock-keycloak"
# This needs to be set for the JWKS URL construction in keycloak_service.py
os.environ["KEYCLOAK_INTERNAL_URL"] = "http://mock-keycloak/realms/test-realm"
os.environ["KEYCLOAK_REALM"] = "test-realm"
os.environ["KEYCLOAK_CLIENT_ID"] = "test-client"
os.environ["KEYCLOAK_CLIENT_SECRET"] = "test-secret"
os.environ["SWAGGER_TOKEN_URL"] = "http://mock-keycloak/token"
os.environ["KEYCLOAK_BASE_URL"] = "http://mock-keycloak"
os.environ["KEYCLOAK_ADMIN_CLIENT_ID"] = "test-admin-client"
os.environ["KEYCLOAK_ADMIN_CLIENT_SECRET"] = "test-admin-secret"
os.environ["SESSION_DIR"] = "/tmp/sessions"
# Use in-memory SQLite for tests if actual DB not needed or mocked
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "password"
os.environ["POSTGRES_DB"] = "aether"
os.environ["POSTGRES_HOST"] = "localhost"

# Telegram mocks
os.environ["TG_API_ID"] = "12345"
os.environ["TG_API_HASH"] = "testpath"

# Reports mock
os.environ["REPORTS_DIR"] = "/tmp/reports"

# Mock requests for JWKS fetch at import time
import requests
original_get = requests.get

def mock_get(url, *args, **kwargs):
    # Check if this is the JWKS request
    if url and "openid-connect/certs" in str(url):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"keys": []}
        return mock_resp
    return original_get(url, *args, **kwargs)

requests.get = mock_get


# Mock langchain_community to avoid dependency issues during tests
import sys
mock_langchain = MagicMock()
sys.modules["langchain_community"] = mock_langchain
sys.modules["langchain_community.graphs"] = mock_langchain
sys.modules["langchain_community.chat_models"] = mock_langchain
sys.modules["langchain_openai"] = mock_langchain
sys.modules["langchain_neo4j"] = mock_langchain
sys.modules["neo4j"] = mock_langchain
sys.modules["neo4j.time"] = mock_langchain
sys.modules["mcp"] = mock_langchain
sys.modules["mcp.client"] = mock_langchain
sys.modules["mcp.client.sse"] = mock_langchain
sys.modules["telethon"] = mock_langchain
sys.modules["telethon.sync"] = mock_langchain
sys.modules["telethon.sessions"] = mock_langchain
sys.modules["telethon.errors"] = mock_langchain
sys.modules["weasyprint"] = mock_langchain
sys.modules["matplotlib"] = mock_langchain
sys.modules["matplotlib.pyplot"] = mock_langchain
sys.modules["seaborn"] = mock_langchain
sys.modules["apscheduler"] = mock_langchain
sys.modules["apscheduler.schedulers.asyncio"] = mock_langchain
sys.modules["apscheduler.triggers"] = mock_langchain
sys.modules["apscheduler.triggers.cron"] = mock_langchain
sys.modules["redis"] = mock_langchain
sys.modules["rq"] = mock_langchain
sys.modules["rq.job"] = mock_langchain
sys.modules["rq.registry"] = mock_langchain
sys.modules["matplotlib.dates"] = mock_langchain
sys.modules["networkx"] = mock_langchain
sys.modules["jinja2"] = mock_langchain


from main import app
from controller.casefile_controller import get_db
from services.auth_ctx import user_ctx
from services import report_service

# Mock User Context
mock_user_data = {
    "id": "test-user-id",
    "username": "testuser",
    "email": "test@example.com",
    "roles": ["user"]
}

def override_user_ctx():
    return mock_user_data

# Mock DB Session
def override_get_db():
    try:
        db = MagicMock()
        yield db
    finally:
        pass

@pytest.fixture
def client():
    app.dependency_overrides[user_ctx] = override_user_ctx
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def mock_db_session():
    return MagicMock()

@pytest.fixture(autouse=True)
def mock_neo4j_services(mocker):
    """Automatically mock all Neo4j backend calls to avoid real DB connection"""
    mocker.patch("services.report_service.get_active_channels_in_period", return_value=[])
    mocker.patch("services.report_service.get_message_volume_over_time", return_value=[])
    mocker.patch("services.report_service.get_top_locations", return_value=[])
    mocker.patch("services.report_service.get_channel_recommendation_graph", return_value={"nodes": [], "edges": []})
    mocker.patch("services.report_service.get_aggregated_emotions", return_value=[])
    mocker.patch("services.report_service.get_messages_with_media", return_value=[])
    
    # Also mock internal service calls if needed
    mocker.patch("services.report_service.get_case_details", return_value={"name": "Test Case", "id": 1})
    
    # Mock file system operations to avoid writing actual PDFs
    mocker.patch("services.report_service.HTML")
    mocker.patch("pathlib.Path.open", mocker.mock_open())
