from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
from controller.report_controller import create_report_pdf
from controller.casefile_controller import SessionLocal, CaseFileModel

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def generate_reports_for_frequency(frequency: str):
    """
    Generate reports for all cases with the specified frequency.
    """
    logger.info(f"Starting {frequency} report generation...")
    
    db = SessionLocal()
    try:
        # Query cases with matching frequency and not archived
        cases = db.query(CaseFileModel).filter(
            CaseFileModel.report_frequency == frequency,
            CaseFileModel.archived == False
        ).all()
        
        logger.info(f"Found {len(cases)} cases for {frequency} reports.")
        
        for case in cases:
            try:
                logger.info(f"Generating report for case {case.id} ({case.title})")
                # Pass report_sections to generation function
                # Note: create_report_pdf needs to be updated to accept sections
                # For now, we pass it, but we need to update report_controller next.
                await create_report_pdf(
                    case_id=case.id, 
                    owner_id=case.owner_id, 
                    period=frequency,
                    sections=case.report_sections or ["stats", "charts", "messages"]
                )
            except Exception as e:
                logger.error(f"Failed to generate report for case {case.id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in report generation job: {e}")
    finally:
        db.close()
    
    logger.info(f"{frequency} report generation completed.")

async def generate_daily_reports():
    await generate_reports_for_frequency("daily")

async def generate_weekly_reports():
    await generate_reports_for_frequency("weekly")

async def generate_monthly_reports():
    await generate_reports_for_frequency("monthly")

def start_scheduler():
    # Daily at 00:00
    scheduler.add_job(
        generate_daily_reports,
        CronTrigger(hour=0, minute=0),
        id="daily_reports",
        replace_existing=True
    )
    
    # Weekly on Monday at 00:00
    scheduler.add_job(
        generate_weekly_reports,
        CronTrigger(day_of_week="mon", hour=0, minute=0),
        id="weekly_reports",
        replace_existing=True
    )
    
    # Monthly on 1st at 00:00
    scheduler.add_job(
        generate_monthly_reports,
        CronTrigger(day=1, hour=0, minute=0),
        id="monthly_reports",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started.")
