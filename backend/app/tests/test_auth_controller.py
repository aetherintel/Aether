import pytest
from unittest.mock import MagicMock
import os

def test_login_success(client, mocker):
    # Mock requests.post for keycloak token endpoint
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "fake-token", "token_type": "Bearer"}
    
    mocker.patch("requests.post", return_value=mock_response)
    
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "password", "grant_type": "password"}
    )
    
    assert response.status_code == 200
    assert response.json()["access_token"] == "fake-token"

def test_login_failure(client, mocker):
    mock_response = MagicMock()
    mock_response.status_code = 401
    
    mocker.patch("requests.post", return_value=mock_response)
    
    response = client.post(
        "/auth/login",
        data={"username": "wronguser", "password": "wrongpassword", "grant_type": "password"}
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Login failed"

def test_register_success(client, mocker):
    # Mock Admin Token Request
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "admin-token"}
    
    # Mock Create User Request
    mock_create_resp = MagicMock()
    mock_create_resp.status_code = 201
    mock_create_resp.headers = {"Location": "http://keycloak/users/new-user-id"}
    
    # Mock Send Email Request
    mock_email_resp = MagicMock()
    mock_email_resp.status_code = 204
    
    # Using side_effect to return different responses for sequential calls
    # 1. Get Admin Token (POST)
    # 2. Create User (POST)
    # 3. Send Email (PUT) - Note: The controller uses PUT for execute-actions-email
    
    mocker.patch("requests.post", side_effect=[mock_token_resp, mock_create_resp])
    mocker.patch("requests.put", return_value=mock_email_resp)
    
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser", 
            "email": "new@example.com", 
            "password": "pass", 
            "firstname": "New", 
            "lastname": "User"
        }
    )
    
    assert response.status_code == 200
    assert "User registered successfully" in response.json()["message"]

def test_register_failure_existing_user(client, mocker):
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "admin-token"}
    
    mock_create_resp = MagicMock()
    mock_create_resp.status_code = 409 # Conflict
    
    mocker.patch("requests.post", side_effect=[mock_token_resp, mock_create_resp])
    
    response = client.post(
        "/auth/register",
        json={
            "username": "existing", 
            "email": "exist@example.com", 
            "password": "pass", 
            "firstname": "Ex", 
            "lastname": "Ist"
        }
    )
    
    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"
