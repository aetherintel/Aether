from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.auth_ctx import user_ctx, UserCtx, is_admin
from services.graph_rag_service import GraphRAGService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Initialize service singleton
# Note: Ideally this is handled via dependency injection or startup event,
# but for simplicity we instantiate it here.
rag_service = GraphRAGService()

class DashboardQueryRequest(BaseModel):
    query: str

@router.post("/query")
async def query_dashboard(
    payload: DashboardQueryRequest,
    user: UserCtx = Depends(user_ctx)
):
    """
    Process a natural language query for the dashboard.
    Returns a summary and a visualization payload (graph/table).
    """
    # Determine owner_id for filtering
    # If admin, we currently still stick to their specific ID for the dashboard 
    # to avoid overwhelming them with ALL system data, or we could handle None -> All.
    # For 'strict' security and personal dashboards, we use their ID.
    owner_id = user["id"]
    
    try:
        result = await rag_service.run_dashboard_query(payload.query, owner_id)
        return result
    except Exception as e:
        print(f"Dashboard query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initialize")
async def initialize_index(
    user: UserCtx = Depends(user_ctx)
):
    """
    Trigger the vector index creation and context hydration.
    """
    # Allow logic: any authenticated user can trigger this for now (for PoC)
    try:
        await rag_service.initialize_vector_index()
        return {"status": "Vector Index initialization completed."}
    except Exception as e:
        print(f"Initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
