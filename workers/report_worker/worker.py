import os
import logging
from redis import Redis
from rq import Queue
from datetime import datetime

# Import from backend app
# PYTHONPATH must include /app/app
from services.report_service import create_report_pdf
from controller.casefile_controller import SessionLocal, ReportModel

# ---------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# Redis Queue setup
# ---------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT)
report_queue = Queue('report-jobs', connection=redis_conn)

# ---------------------------------------------------------------
# Worker job function
# ---------------------------------------------------------------
async def generate_report_job(case_id: int, owner_id: str, period: str, sections: list[str] = None):
    """
    Generate report and save to DB
    """
    logger.info("=" * 80)
    logger.info(f"📊 Report generation job started")
    logger.info(f"   Case ID: {case_id}")
    logger.info(f"   Period: {period}")
    logger.info("=" * 80)
    
    try:
        # Generate PDF
        # create_report_pdf is async, but RQ workers are typically synchronous.
        # We need to run async function in sync context.
        import asyncio
        filename, filepath = await create_report_pdf(case_id, owner_id, period, sections)
        
        logger.info(f"✅ Report generated: {filename}")
        
        # Save to DB
        db = SessionLocal()
        try:
            report = ReportModel(
                case_id=case_id,
                path=str(filepath),
                filename=filename,
                period=period,
                created_at=datetime.now()
            )
            db.add(report)
            db.commit()
            logger.info(f"💾 Report saved to DB with ID: {report.id}")
        except Exception as e:
            logger.error(f"❌ Failed to save report to DB: {e}")
            db.rollback()
        finally:
            db.close()
            
        return filename
        
    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}")
        raise

# Wrapper for RQ (which expects sync functions)
def run_generate_report_job(case_id: int, owner_id: str, period: str, sections: list[str] = None):
    import asyncio
    asyncio.run(generate_report_job(case_id, owner_id, period, sections))
