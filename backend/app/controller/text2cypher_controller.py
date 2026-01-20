from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Any, Dict

from services.text2cypher_service import Text2CypherService

router = APIRouter(
    prefix="/text2cypher",
    tags=["Text2Cypher"]
)

class Text2CypherRequest(BaseModel):
    question: str
    history: List[str] = []

class Text2CypherResponse(BaseModel):
    summary: str
    visualization: Dict[str, Any]
    cypher: Optional[str] = None
    question: Optional[str] = None
    error: Optional[str] = None

@router.post("/", response_model=Text2CypherResponse)
async def run_text2cypher(request: Text2CypherRequest):
    service = Text2CypherService()
    try:
        result = await service.run_text2cypher(request.question, request.history)
        return Text2CypherResponse(**result)
    except Exception as e:
        # Log error in production
        print(f"Text2Cypher Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schema")
async def get_schema():
    service = Text2CypherService()
    try:
        schema = await service.get_schema()
        return {"schema": schema}
    except Exception as e:
        print(f"Schema Retrieval Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
