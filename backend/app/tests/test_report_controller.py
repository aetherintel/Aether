import pytest
from unittest.mock import MagicMock
from pathlib import Path

def test_generate_report_success(client, mocker):
    # Mock the service ensuring it returns a valid tuple
    mocker.patch(
        "controller.report_controller.create_report_pdf", 
        return_value=("test_report.pdf", Path("/tmp/test_report.pdf"))
    )
    
    # Mock DB commit
    mock_db = MagicMock()
    # We are mocking the dependency override in conftest, 
    # but we can't easily access the *instance* yielded by the override unless we patch it or uses a fixture that returns it.
    # The current override_get_db yields a new MagicMock each time. 
    # For now, we trust the endpoints use the db session correctly without asserting on db.add calls 
    # unless we refactor conftest to expose the mock.
    
    response = client.post(
        "/reports/generate/1",
        json={"period": "weekly", "sections": ["stats"]}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test_report.pdf"
    assert data["path"] == "/tmp/test_report.pdf"

def test_list_reports(client, mocker):
    # Mock DB query result
    # The controller does: db.query(ReportModel, CaseFileModel.title).join(...).filter(...).all()
    
    mock_report = MagicMock()
    mock_report.filename = "report1.pdf"
    mock_report.path = "/tmp/report1.pdf"
    mock_report.created_at = "2023-01-01T00:00:00"
    mock_report.period = "daily"
    mock_report.case_id = 1
    
    # Mock Path.exists to return True
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024))
    
    # Mock get_db to return our prepared mock
    mock_db_session = MagicMock()
    mock_db_session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [
        (mock_report, "Test Case Title")
    ]
    
    # We need to override the get_db dependency again for this test to inject OUR mock_db_session
    # OR we can patch the query chain. 
    # Easier to just rely on the fact that `client` usage triggers `override_get_db`.
    # But `override_get_db` creates a generic MagicMock. 
    # We need to configure THAT mock. 
    # Since `override_get_db` is a function, we can patch it?
    # Better: patch `controller.report_controller.get_db` isn't possible because it's used as a Depends default.
    # We need to update app.dependency_overrides.
    
    from main import app
    from controller.casefile_controller import get_db
    
    def override_get_db_custom():
        yield mock_db_session
        
    app.dependency_overrides[get_db] = override_get_db_custom
    
    response = client.get("/reports/list")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "report1.pdf"
    assert data[0]["case_title"] == "Test Case Title"

def test_download_report_not_found(client, mocker):
    # Mock Path.exists to return False
    mocker.patch("pathlib.Path.exists", return_value=False)
    
    response = client.get("/reports/download/missing_file.pdf")
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"
