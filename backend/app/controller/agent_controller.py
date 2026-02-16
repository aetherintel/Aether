from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import asyncio
import logging

from services.agent_service import AgentService
from services.task_registry import TaskRegistry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent",
    tags=["Agent"]
)

class AgentRequest(BaseModel):
    message: str
    history: List[str] = []
    system_prompt_key: str = "default"
    request_id: Optional[str] = None

class AgentResponse(BaseModel):
    message: str
    widget_type: Optional[str] = None
    widget_data: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = {}

@router.post("/query", response_model=AgentResponse)
async def query_agent(request: AgentRequest):
    service = AgentService()
    
    # Create the coroutine but don't await immediately
    coro = service.process_message(
        request.message, 
        request.history, 
        request.system_prompt_key
    )
    
    if request.request_id:
        # Wrap in task for cancellation support
        task = asyncio.create_task(coro)
        TaskRegistry().register_task(request.request_id, task)
        try:
            result = await task
        except asyncio.CancelledError:
            logger.info(f"Request {request.request_id} was cancelled by user.")
            raise HTTPException(status_code=499, detail="Request cancelled by user")
        except Exception as e:
            logger.error(f"Agent Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Normal execution for requests without ID
        try:
            result = await coro
        except Exception as e:
             logger.error(f"Agent Error: {e}")
             raise HTTPException(status_code=500, detail=str(e))

    # Convert internal AgentResponse model to Pydantic model for API
    return AgentResponse(
        message=result.message,
        widget_type=result.widget_type,
        widget_data=result.widget_data,
        metadata=result.metadata
    )

class FeedbackRequest(BaseModel):
    question: str
    cypher: str
    rating: int # 1 for positive, -1 for negative

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Receives user feedback (Thumbs Up/Down) for a generated query.
    Positive feedback is saved to improve future generation (Few-Shot).
    """
    service = AgentService()
    success = await service.save_feedback(
        request.question,
        request.cypher,
        request.rating
    )
    if success:
        return {"status": "success", "message": "Feedback received"}
    else:
         raise HTTPException(status_code=500, detail="Failed to save feedback")

@router.post("/cancel/{request_id}")
async def cancel_agent_request(request_id: str):
    """Cancels a running agent request by ID."""
    success = await TaskRegistry().cancel_task(request_id)
    if success:
        return {"status": "success", "message": f"Request {request_id} cancelled."}
    else:
        # Task might have finished or ID is wrong
        return {"status": "ignored", "message": f"Request {request_id} not found or already finished."}

@router.get("/prompts")
async def get_system_prompts():
    service = AgentService()
    return await service.get_system_prompts()

@router.get("/suggestions")
async def get_suggestions():
    service = AgentService()
    return await service.get_suggested_commands()

# Legacy endpoint for backward compatibility (optional, or we can just remove it if we update frontend)
# We will effectively replace the old text2cypher usage with this new agent usage.
