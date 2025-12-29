from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from services.auth_ctx import user_ctx, UserCtx
from database import get_db
from model.casefile_model import CaseFileModel
from services.neo4j_backend_client import get_channel_list

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/overview")
async def get_stats_overview(
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx)
):
    """
    Get overview statistics for all cases of the current user
    """
    owner_id = user["id"]
    print(f"Stats Overview: User={user}, Resolved OwnerID={owner_id}")
    
    # Total cases (not archived)
    total_cases = db.query(func.count(CaseFileModel.id)).filter(
        CaseFileModel.owner_id == owner_id,
        CaseFileModel.archived == False
    ).scalar() or 0
    
    # Get all casefiles to extract channels
    cases = db.query(CaseFileModel).filter(
        CaseFileModel.owner_id == owner_id,
        CaseFileModel.archived == False
    ).all()
    
    # Collect all unique channel usernames across all cases
    all_usernames = set()
    for case in cases:
        if case.tgchannels:
            all_usernames.update(case.tgchannels)
            
    total_channels = len(all_usernames)
    
    # Get message counts from Neo4j
    total_messages = 0
    if all_usernames:
        try:
            channel_details = await get_channel_list(owner_id, list(all_usernames))
            total_messages = sum(ch.get('message_count', 0) for ch in channel_details)
        except Exception as e:
            print(f"Error fetching stats from Neo4j: {e}")
            # Fallback or just 0
    
    # Active scrapers - Placeholder for now as JobModel is deprecated
    # We could query Redis/RQ here if needed
    active_scrapers = 0
    
    return {
        "totalCases": total_cases,
        "totalChannels": total_channels,
        "totalMessages": total_messages,
        "activeScrapers": active_scrapers
    }