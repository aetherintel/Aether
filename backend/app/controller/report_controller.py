from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from controller.auth_controller import get_current_user
from controller.casefile_controller import get_db, ReportModel
from services.report_service import create_report_pdf, REPORTS_DIR

router = APIRouter(prefix="/reports", tags=["reports"])

class GenerateReportRequest(BaseModel):
    period: str = "daily"
    sections: list[str] = ["stats", "charts", "messages"]

@router.post("/generate/{case_id}")
async def generate_report(
    case_id: int,
    request: GenerateReportRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate PDF report for case"""
    owner_id = current_user.get("owner_id")
    
    filename, filepath = await create_report_pdf(case_id, owner_id, request.period, request.sections)
    
    return {"filename": filename, "path": str(filepath)}

@router.get("/list/{case_id}")
async def list_reports(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List available reports for case from DB"""
    reports = db.query(ReportModel).filter(
        ReportModel.case_id == case_id
    ).order_by(ReportModel.created_at.desc()).all()
    
    result = []
    for r in reports:
        # Check if file exists
        file_path = Path(r.path)
        if file_path.exists():
            result.append({
                "filename": r.filename,
                "size": file_path.stat().st_size,
                "created": r.created_at,
                "period": r.period,
                "url": f"/api/reports/download/{r.filename}"
            })
            
    return result

@router.get("/download/{filename}")
async def download_report(filename: str):
    """Download specific report"""
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Report not found")
    
    return FileResponse(filepath, media_type="application/pdf", filename=filename)