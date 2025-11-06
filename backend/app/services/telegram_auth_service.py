"""
Telegram Auth Service
Provides helper functions for managing Telegram sessions
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Tuple, Optional

SESSION_DIR = Path(os.getenv("SESSION_DIR", "/app/sessions"))
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_string_session(
    session_name: str,
    session_string: str,
    user_info: Optional[dict] = None,
    user_id: Optional[str] = None
) -> None:
    """
    Save StringSession to JSON file
    
    Args:
        session_name: Name of the session
        session_string: Telegram StringSession
        user_info: Optional user information dict
        user_id: Optional user ID for user-specific storage
    """
    # User-specific directory
    if user_id:
        user_dir = SESSION_DIR / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        session_file = user_dir / f"{session_name}.json"
    else:
        session_file = SESSION_DIR / f"{session_name}.json"
    
    data = {
        "session_string": session_string,
        "user_info": user_info,
        "created_at": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0,
        "owner_user_id": user_id
    }
    
    with open(session_file, 'w') as f:
        json.dump(data, f, indent=2)


def load_string_session(
    session_name: str,
    user_id: Optional[str] = None
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Load StringSession from JSON file
    
    Args:
        session_name: Name of the session
        user_id: Optional user ID for user-specific storage
        
    Returns:
        Tuple of (session_string, user_info) or (None, None) if not found
    """
    # User-specific path
    if user_id:
        user_dir = SESSION_DIR / f"user_{user_id}"
        session_file = user_dir / f"{session_name}.json"
    else:
        session_file = SESSION_DIR / f"{session_name}.json"
    
    if not session_file.exists():
        return None, None
    
    try:
        with open(session_file, 'r') as f:
            data = json.load(f)
        
        # Security check if user_id is provided
        if user_id and data.get("owner_user_id") != user_id:
            return None, None
        
        return data.get("session_string"), data.get("user_info")
    except Exception:
        return None, None


def delete_session(
    session_name: str,
    user_id: Optional[str] = None
) -> bool:
    """
    Delete a session file
    
    Args:
        session_name: Name of the session
        user_id: Optional user ID for user-specific storage
        
    Returns:
        True if deleted, False if not found
    """
    if user_id:
        user_dir = SESSION_DIR / f"user_{user_id}"
        session_file = user_dir / f"{session_name}.json"
    else:
        session_file = SESSION_DIR / f"{session_name}.json"
    
    if session_file.exists():
        session_file.unlink()
        return True
    
    return False


def list_sessions(user_id: Optional[str] = None) -> list[str]:
    """
    List all available sessions
    
    Args:
        user_id: Optional user ID to list only user-specific sessions
        
    Returns:
        List of session names
    """
    if user_id:
        user_dir = SESSION_DIR / f"user_{user_id}"
        if not user_dir.exists():
            return []
        return [f.stem for f in user_dir.glob("*.json")]
    else:
        return [f.stem for f in SESSION_DIR.glob("*.json")]