import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add the current directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock the services before importing controller
sys.modules['services.neo4j_backend_client'] = MagicMock()
sys.modules['controller.auth_controller'] = MagicMock()

from controller.report_controller import create_report_pdf
from services.neo4j_backend_client import (
    get_channel_list,
    get_total_message_count_for_channels,
    get_top_locations,
    get_message_volume_over_time,
    get_messages_with_media
)

async def test_report_generation():
    print("Starting report generation test...")
    
    # Mock data
    mock_channels = [
        {'channel_id': '1', 'title': 'Channel A', 'username': 'channel_a', 'message_count': 150},
        {'channel_id': '2', 'title': 'Channel B', 'username': 'channel_b', 'message_count': 80},
        {'channel_id': '3', 'title': 'Channel C', 'username': 'channel_c', 'message_count': 45},
    ]
    
    mock_volume = [
        {'date': '2023-10-01', 'count': 10},
        {'date': '2023-10-02', 'count': 25},
        {'date': '2023-10-03', 'count': 15},
        {'date': '2023-10-04', 'count': 40},
        {'date': '2023-10-05', 'count': 30},
    ]
    
    mock_locations = [
        {'name': 'Berlin', 'count': 50},
        {'name': 'Munich', 'count': 30},
        {'name': 'Hamburg', 'count': 20},
    ]
    
    mock_messages = [
        {
            'date': datetime.now(),
            'channel': {'title': 'Channel A', 'username': 'channel_a'},
            'original_text': 'Suspicious activity detected near the central station.',
            'translated_text': None,
            'author': {'name': 'User123'}
        },
        {
            'date': datetime.now(),
            'channel': {'title': 'Channel B', 'username': 'channel_b'},
            'original_text': 'Meeting confirmed for tomorrow.',
            'translated_text': None,
            'author': {'name': 'User456'}
        }
    ]
    
    mock_graph = {
        "nodes": [{"id": "Channel A", "label": "Channel A"}, {"id": "Channel B", "label": "Channel B"}, {"id": "Channel C", "label": "Channel C"}],
        "edges": [{"source": "Channel A", "target": "Channel B"}, {"source": "Channel B", "target": "Channel C"}]
    }
    
    # Setup mocks
    get_active_channels_in_period.return_value = mock_channels
    get_total_message_count_for_channels.return_value = 275
    get_message_volume_over_time.return_value = mock_volume
    get_top_locations.return_value = mock_locations
    get_messages_with_media.return_value = mock_messages
    get_channel_recommendation_graph.return_value = mock_graph
    
    # Run the function
    try:
        filename, filepath = await create_report_pdf(
            case_id=123,
            owner_id="test_owner",
            period="weekly",
            sections=["stats", "charts", "messages"]
        )
        
        print(f"Report generated successfully: {filename}")
        print(f"Path: {filepath}")
        
        # Check if file exists and has size
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print("SUCCESS: PDF file created and is not empty.")
        else:
            print("FAILURE: PDF file not found or empty.")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_report_generation())
