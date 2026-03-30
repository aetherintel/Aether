import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from services.neo4j_backend_client import (
    get_channel_list,
    get_messages_for_channel,
    get_channel_by_id,
    get_messages_by_id,
    get_user_channels,
    get_user_messages,
    get_unified_timeline_messages,
    get_case_channels_with_recommendations,
    get_channel_locations_data,
)
from repository.neo4j.message_repo import get_message_enrichment
from starlette.responses import FileResponse
from model.message_model import (
    Message,
    ChannelDetail,
    ChannelListItem,
)

from services.auth_ctx import user_ctx, is_admin, UserCtx

router = APIRouter(prefix="/messages", tags=["messages"])

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/public/media"))

@router.get("/media/message/{message_id}")
async def get_media_by_message_id(
    message_id: str,
    user: UserCtx = Depends(user_ctx),
):
    owner = None if is_admin(user) else user["id"]
    try:
        message = await get_messages_by_id(message_id, owner)

        if not message:
            raise HTTPException(status_code=404, detail=f"Nachricht {message_id} nicht gefunden")

        if not message.media_path:
            raise HTTPException(status_code=404, detail=f"Keine Medien für diese {message_id} Nachricht")

        file_path = Path(message.media_path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Media-Datei {file_path} nicht gefunden")

        if not file_path.resolve().is_relative_to(MEDIA_ROOT.resolve()):
            raise HTTPException(status_code=403, detail=f"Media-Datei {file_path} ist nicht im Medienverzeichnis")

        return FileResponse(path = file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Medien: {str(e)}")
    
async def fetch_channels(owner: str | None, usernames: list[str] | None = None):
    all_channels = await get_channel_list(owner, usernames=usernames or [])
    if usernames:
        filtered = [
            ch for ch in all_channels
            if ch.get('username', '').lower() in [u.lower() for u in usernames]
        ]
        return filtered
    return all_channels

@router.get("/channels", response_model=List[ChannelListItem])
async def list_channels(
    usernames: Optional[str] = Query(None),
    user: UserCtx = Depends(user_ctx),
):
    owner = None if is_admin(user) else user["id"]
    username_list = [u.strip() for u in usernames.split(',')] if usernames else None
    return await fetch_channels(owner, username_list)

@router.get("/channels/expand", response_model=Dict[str, List[str]])
async def expand_channels_with_recommendations(
    channel_usernames: str = Query(..., description="Comma-separated channel usernames"),
    user: UserCtx = Depends(user_ctx),
):
    """Expand channel list to include recommended channels"""
    owner = None if is_admin(user) else user["id"]
    
    # Parse input channels
    input_channels = [ch.strip() for ch in channel_usernames.split(',') if ch.strip()]
    
    try:
        # Use the Neo4j function to expand with recommendations
        expanded_channels = await get_case_channels_with_recommendations(input_channels, owner)
        
        # If no channels found (none scraped yet), return the original list
        # This allows the frontend to know what channels are intended for the case
        if len(expanded_channels) == 0:
            return {username.lower(): [] for username in input_channels}
            
        return expanded_channels
        
    except Exception as e:
        # On error, return the original channels so the case still shows intended channels
        print(f"[WARN] Error expanding channels: {str(e)}. Returning original list.")
        return {username.lower(): [] for username in input_channels}


# ADD THIS NEW ENDPOINT - Place it BEFORE the individual channel endpoint
@router.get("/timeline", response_model=List[Message])
async def get_unified_timeline(
    channel_ids: Optional[str] = Query(None, description="Comma-separated channel IDs"),
    limit: int = Query(100, ge=1, le=1000),
    before: datetime | None = None,
    q: str | None = None,
    user: UserCtx = Depends(user_ctx),
):
    """Get messages from selected channels sorted by date globally (newest first)"""
    owner = None if is_admin(user) else user["id"]
    
    # Parse channel IDs from comma-separated string
    selected_channels = []
    if channel_ids:
        selected_channels = [ch.strip() for ch in channel_ids.split(',') if ch.strip()]
    
    try:
        messages = await get_unified_timeline_messages(
            owner,
            selected_channels=selected_channels,
            limit=limit,
            before=before,
            query=q,
        )
        return messages
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Timeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Timeline: {str(e)}")

@router.get("/channels/{channel_id}", response_model=ChannelDetail)
async def get_channel_details(
    channel_id: str,
    user: UserCtx = Depends(user_ctx),
):
    owner = None if is_admin(user) else user["id"]
    try:
        channel = await get_channel_by_id(str(channel_id), owner)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} nicht gefunden")
        return channel
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Channel-Details: {str(e)}")

@router.get("/channels/{channel_id}/messages", response_model=List[Message])
async def get_channel_messages(
    channel_id: str,
    limit: int = Query(100, ge=1, le=1000),
    before: datetime | None = None,
    q: str | None = None,
    user: UserCtx = Depends(user_ctx),
):
    owner = None if is_admin(user) else user["id"]
    try:
        messages = await get_messages_for_channel(
            str(channel_id),
            owner,  # Don't convert to string here, keep as-is
            limit=limit,
            before=before,
            query=q,
        )
        return messages
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Nachrichten: {str(e)}")

@router.get("/users/{user_id}/channels", response_model=List[ChannelListItem])
async def get_channels_for_user(
    user_id: int,
    user: UserCtx = Depends(user_ctx),
):
    owner = None if is_admin(user) else user["id"]
    try:
        channels = await get_user_channels(user_id, owner)
        for channel in channels:
            channel["last_message_date"] = channel.pop("last_active", None)
        return channels
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Kanäle für Benutzer {user_id}: {str(e)}")

@router.get("/users/{user_id}/messages", response_model=List[Message])
async def get_messages_for_user(
    user_id: int,
    limit: int = Query(100, ge=1, le=1000),
    before: datetime | None = None,
    q: str | None = None,
    user: UserCtx = Depends(user_ctx),
):
    owner = None if is_admin(user) else user["id"]
    try:
        messages = await get_user_messages(
            user_id,
            owner,
            limit=limit,
            before=before,
            query=q,
        )
        return messages
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Nachrichten für Benutzer {user_id}: {str(e)}")

@router.get("/channels/{channel_id}/locations")
async def get_channel_locations(
    channel_id: str,
    limit: int = Query(1000, ge=1, le=5000),
    user: UserCtx = Depends(user_ctx),
):
    """Get all messages with location data for a channel."""
    owner = None if is_admin(user) else user["id"]
    
    try:
        locations = await get_channel_locations_data(channel_id, owner, limit)
        return locations
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fehler beim Abrufen der Location-Daten: {str(e)}"
        )

@router.get("/channels/{channel_id}/emotions")
async def get_channel_emotions_endpoint(
    channel_id: str,
    user: UserCtx = Depends(user_ctx),
):
    """Get aggregated emotion statistics for a channel."""
    owner = None if is_admin(user) else user["id"]
    
    try:
        # Import here to avoid circular imports if any, or just standard practice
        from services.neo4j_backend_client import get_channel_emotions
        emotions = await get_channel_emotions(channel_id, owner)
        return emotions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fehler beim Abrufen der Emotionen: {str(e)}"
        )


@router.get("/{message_id}/enrichment")
async def get_enrichment(
    message_id: str,
    user: UserCtx = Depends(user_ctx),
):
    """Return emotions, classifications, and locations for a single message."""
    owner = None if is_admin(user) else user["id"]
    try:
        return await get_message_enrichment(message_id, owner)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
