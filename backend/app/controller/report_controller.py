from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from datetime import datetime
from pathlib import Path
from pathlib import Path
from sqlalchemy.orm import Session
from services.auth_ctx import user_ctx, UserCtx
from database import get_db
from model.casefile_model import ReportModel
from services.report_service import create_report_pdf, REPORTS_DIR

router = APIRouter(prefix="/reports", tags=["reports"])

class GenerateReportRequest(BaseModel):
    period: str = "daily"
    sections: list[str] = ["stats", "charts", "messages"]

@router.post("/generate/{case_id}")
async def generate_report(
    case_id: int,
    request: GenerateReportRequest,
    db: Session = Depends(get_db), 
    user: UserCtx = Depends(user_ctx)
):
    """Generate PDF report for case"""
    owner_id = user["id"]
    # Debug logging
    print(f"Generate Report: User={user}, OwnerID={owner_id}, CaseID={case_id}")
    
    filename, filepath = await create_report_pdf(case_id, owner_id, request.period, request.sections)
    
    # Save to DB
    new_report = ReportModel(
        case_id=case_id,
        path=str(filepath),
        filename=filename,
        period=request.period
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    
    return {"filename": filename, "path": str(filepath)}

@router.get("/list")
async def list_all_reports(
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx)
):
    """List all available reports for the user across all cases"""
    # Join ReportModel and CaseFileModel to filter by owner_id
    from model.casefile_model import CaseFileModel
    
    reports = db.query(ReportModel, CaseFileModel.title).join(
        CaseFileModel, ReportModel.case_id == CaseFileModel.id
    ).filter(
        CaseFileModel.owner_id == user["id"]
    ).order_by(ReportModel.created_at.desc()).all()
    
    result = []
    for r, case_title in reports:
        # Check if file exists
        file_path = Path(r.path)
        if file_path.exists():
            result.append({
                "filename": r.filename,
                "size": file_path.stat().st_size,
                "created": r.created_at,
                "period": r.period,
                "case_id": r.case_id,
                "case_title": case_title,
                "url": f"/api/reports/download/{r.filename}"
            })
            
    return result

@router.get("/list/{case_id}")
async def list_reports(
    case_id: int,
    db: Session = Depends(get_db),
    user: UserCtx = Depends(user_ctx)
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
                "case_id": r.case_id,
                "url": f"/api/reports/download/{r.filename}"
            })
            
    return result

@router.get("/download/{filename}")
async def download_report(filename: str, preview: bool = False):
    """Download specific report"""
    # Try to find file in root first (legacy)
    filepath = REPORTS_DIR / filename
    
    if not filepath.exists():
        # Try to parse case_id from filename: report_{case_id}_{period}_{date}.pdf
        try:
            parts = filename.split('_')
            if len(parts) >= 2 and parts[0] == 'report':
                case_id = parts[1]
                filepath = REPORTS_DIR / f"case_{case_id}" / filename
        except Exception:
            pass
            
    if not filepath.exists():
        raise HTTPException(404, "Report not found")
    
    content_disposition = "inline" if preview else f'attachment; filename="{filename}"'
    return FileResponse(filepath, media_type="application/pdf", headers={"Content-Disposition": content_disposition})