import pytest
from unittest.mock import MagicMock

def test_create_casefile_success(client, mocker):
    # Mock the service logic
    mock_case = {
        "id": 1,
        "title": "New Case",
        "description": "Desc",
        "owner_id": "test-user-id",
        "tgchannels": [],
        "created_at": "2023-01-01T00:00:00",
        "archived": False,
        "report_frequency": "daily",
        "report_sections": ["stats"]
    }
    
    mocker.patch(
        "controller.casefile_controller.create_casefile_logic",
        return_value=(mock_case, [], None)
    )
    
    response = client.post(
        "/casefiles/",
        json={"title": "New Case", "description": "Desc"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Case"
    assert data["id"] == 1

def test_read_casefiles(client, mocker):
    mock_case1 = MagicMock()
    mock_case1.id = 1
    mock_case1.title = "Case 1"
    mock_case1.owner_id = "test-user-id"
    mock_case1.archived = False
    mock_case1.created_at = "2023-01-01T00:00:00" # OR datetime object if not Pydantic converts. Pydantic handles str if format OK.
    # Better use datetime to be safe if model uses it
    from datetime import datetime
    mock_case1.created_at = datetime(2023, 1, 1)
    mock_case1.report_frequency = "daily"
    mock_case1.report_sections = ["stats"]
    mock_case1.tgchannels = []
    mock_case1.topics = []
    mock_case1.terms = []
    mock_case1.thumbnails = []
    mock_case1.tg_session = None
    mock_case1.description = None
    mock_case1.category = None
    mock_case1.postCount = 0
    mock_case1.duration = 0
    mock_case1.scraper_mode = "full"
    
    # We need to mock the db session yielded by get_db dependency
    # In conftest we have override_get_db which yields a MagicMock
    # We can't easily access that specific mock instance unless we use the pattern 
    # of patching the dependency override AGAIN or relying on the 'db' argument in the controller.
    # But since we use client, we are integration testing the controller + dependency injection.
    
    # Best way here is to patch the chained calls on the db session mock that the controller receives.
    # OR simpler: patch the methods on the Session/Query objects if possible, 
    # but since it's a MagicMock, we just need to satisfy the call chain:
    # db.query(CaseFileModel).filter_by(...).limit(...).all()
    
    # The 'mock_db_session' fixture in conftest is independent of what client uses unless we link them.
    # Let's adjust how we inject the mock db.
    
    # Define a custom override for this test
    mock_db = MagicMock()
    
    # Setup query mock to return itself for chained calls
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = [mock_case1]
    
    from main import app
    from controller.casefile_controller import get_db
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.get("/casefiles/")
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Case 1"

def test_delete_casefile_success(client, mocker):
    mock_case = MagicMock()
    mock_case.id = 1
    mock_case.owner_id = "test-user-id"
    
    mock_db = MagicMock()
    # db.query(Model).get(id)
    mock_db.query.return_value.get.return_value = mock_case
    
    from main import app
    from controller.casefile_controller import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.delete("/casefiles/1")
    
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_db.delete.assert_called_once_with(mock_case)
    mock_db.commit.assert_called_once()

def test_delete_casefile_forbidden(client, mocker):
    mock_case = MagicMock()
    mock_case.id = 1
    mock_case.owner_id = "other-user-id" # Not the test-user-id
    
    mock_db = MagicMock()
    mock_db.query.return_value.get.return_value = mock_case
    
    from main import app
    from controller.casefile_controller import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.delete("/casefiles/1")
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"
