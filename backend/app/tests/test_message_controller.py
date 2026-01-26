import pytest
from unittest.mock import AsyncMock

def test_list_channels(client, mocker):
    mock_channels = [
        {
            "channel_id": "1", "username": "chan1", "title": "Channel 1",
            "message_count": 10, "recommended_by": 0, "is_scraped": True, "scraped_at": None,
            "last_active": None, "last_message_date": None
        },
        {
            "channel_id": "2", "username": "chan2", "title": "Channel 2",
            "message_count": 5, "recommended_by": 0, "is_scraped": False, "scraped_at": None,
            "last_active": None, "last_message_date": None
        }
    ]
    
    # Patch the service function used in controller
    mocker.patch(
        "controller.message_controller.fetch_channels", 
        new_callable=AsyncMock,
        return_value=mock_channels
    )
    # Note: list_channels calls fetch_channels, so we mock fetch_channels OR get_channel_list
    # In controller: fetch_channels calls get_channel_list
    # If we want to test list_channels -> fetch_channels -> get_channel_list, we should mock get_channel_list IN controller.message_controller
    
    mocker.patch(
        "controller.message_controller.get_channel_list",
        new_callable=AsyncMock,
        return_value=mock_channels
    )
    
    response = client.get("/messages/channels")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["username"] == "chan1"

def test_list_channels_filtered(client, mocker):
    mock_channels = [
        {
            "channel_id": "1", "username": "chan1", "title": "Channel 1",
            "message_count": 10, "recommended_by": 0, "is_scraped": True, "scraped_at": None,
            "last_active": None, "last_message_date": None
        }
    ]
    
    mocker.patch(
        "controller.message_controller.get_channel_list",
        new_callable=AsyncMock,
        return_value=mock_channels
    )
    
    response = client.get("/messages/channels?usernames=chan1")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    # Check if the mock was called with filters if we were testing the service layer, 
    # but here we test the controller passing args. 
    # Since fetch_channels logic filters in python if usernames are passed to it 
    # (wait, let's check controller logic, yes it does filtered list comperhension if usernames passed)
    # Actually wait, fetch_channels calls get_channel_list passing usernames.
    
    # In my mock above I return a list. The controller calls fetch_channels which calls service.
    # If the service mock returns the list, the controller should return it.
    
    assert data[0]["username"] == "chan1"

def test_get_channel_messages(client, mocker):
    mock_msgs = [
        {
            "mid": "m1", "message_id": "m1", "text": "hello", "date": "2023-01-01T12:00:00",
            "author": {"id": 123, "name": "User"},
            "channel": {"id": "123", "username": "test_channel"}
        }
    ]
    
    mocker.patch(
        "controller.message_controller.get_messages_for_channel",
        new_callable=AsyncMock,
        return_value=mock_msgs
    )
    
    response = client.get("/messages/channels/123/messages")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "hello"

def test_get_media_not_found(client, mocker):
    # Mock get_messages_by_id to return None
    mocker.patch(
        "controller.message_controller.get_messages_by_id",
        new_callable=AsyncMock,
        return_value=None
    )
    
    response = client.get("/messages/media/message/123")
    
    assert response.status_code == 404
    assert "nicht gefunden" in response.json()["detail"]
