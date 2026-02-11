import pytest
from unittest.mock import MagicMock, AsyncMock

def test_query_dashboard_success(client, mocker):
    # Mock the rag_service instance in the controller
    # The controller does: rag_service = GraphRAGService()
    # So we patch the 'rag_service' object in that module
    
    # We need an AsyncMock for the async methods
    mock_service = AsyncMock()
    mock_service.run_dashboard_query.return_value = {
        "summary": "Test Summary",
        "data": {"nodes": [], "edges": []}
    }
    
    mocker.patch("controller.dashboard_controller.rag_service", mock_service)
    
    # Send request
    response = client.post(
        "/dashboard/query",
        json={"query": "Show me the money"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Test Summary"
    
    # Verify service called with correct args
    # We assume the user from conftest has id="test-user-id"
    mock_service.run_dashboard_query.assert_called_once_with("Show me the money", "test-user-id")

def test_query_dashboard_error(client, mocker):
    mock_service = AsyncMock()
    mock_service.run_dashboard_query.side_effect = Exception("Service failure")
    
    mocker.patch("controller.dashboard_controller.rag_service", mock_service)
    
    response = client.post(
        "/dashboard/query",
        json={"query": "Crash it"}
    )
    
    assert response.status_code == 500
    assert response.json()["detail"] == "Service failure"

def test_initialize_index_success(client, mocker):
    mock_service = AsyncMock()
    mock_service.initialize_vector_index.return_value = None
    
    mocker.patch("controller.dashboard_controller.rag_service", mock_service)
    
    response = client.post("/dashboard/initialize")
    
    assert response.status_code == 200
    assert response.json() == {"status": "Vector Index initialization completed."}
    
    mock_service.initialize_vector_index.assert_called_once()

def test_initialize_index_error(client, mocker):
    mock_service = AsyncMock()
    mock_service.initialize_vector_index.side_effect = Exception("Init failed")
    
    mocker.patch("controller.dashboard_controller.rag_service", mock_service)
    
    response = client.post("/dashboard/initialize")
    
    assert response.status_code == 500
    assert response.json()["detail"] == "Init failed"
