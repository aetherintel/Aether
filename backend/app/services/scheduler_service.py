from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
import os
from redis import Redis
from rq import Queue
from database import SessionLocal
from model.casefile_model import CaseFileModel

logger = logging.getLogger(__name__)

# Setup Redis Queue
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT)
report_queue = Queue('report-jobs', connection=redis_conn)

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
                logger.info(f"Enqueuing report job for case {case.id} ({case.title})")
                
                # Enqueue job to worker
                report_queue.enqueue(
                    'workers.report_worker.worker.run_generate_report_job',
                    case_id=case.id, 
                    owner_id=case.owner_id, 
                    period=frequency,
                    sections=case.report_sections or ["stats", "charts", "messages"]
                )
            except Exception as e:
                logger.error(f"Failed to enqueue report for case {case.id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in report generation job: {e}")
    finally:
        db.close()
    
    logger.info(f"{frequency} report generation completed.")

async def reconcile_pending_statuses():
    """
    Reconcile 'pending' statuses in Neo4j against what's actually in the Redis queues.

    For each worker type, collect the message_ids of jobs that are currently
    queued or being processed. Any message whose status is still 'pending'
    but has NO active job is reset to 'none' so the UI re-enables the
    trigger buttons and the job can be re-submitted.

    This handles:
    - Redis flush / restart (jobs lost but status stays 'pending')
    - Jobs that crashed before updating Neo4j
    - Manual queue clears
    """
    from services.queue_service import queue_service
    from repository.neo4j.base import driver

    # Map: (queue_name, neo4j_status_field)
    QUEUE_STATUS_FIELDS = [
        ('image',          'image_analysis_status'),
        ('audio',          'audio_transcription_status'),
        ('translation',    'translation_status'),
        ('emotion',        'emotion_status'),
        ('classification', 'classification_status'),
        ('geolocation',    'geolocation_status'),
    ]

    total_reset = 0

    async with driver.session() as session:
        for queue_name, status_field in QUEUE_STATUS_FIELDS:
            try:
                active_ids = queue_service.get_active_message_ids(queue_name)

                # Reset messages that are 'pending' but not actively in-flight
                if active_ids:
                    cypher = f"""
                    MATCH (m:Message)
                    WHERE m.{status_field} = 'pending'
                      AND NOT m.mid IN $active_ids
                    SET m.{status_field} = 'none'
                    RETURN count(m) AS n
                    """
                    result = await session.run(cypher, {"active_ids": list(active_ids)})
                else:
                    # Queue is empty — reset ALL pending for this type
                    cypher = f"""
                    MATCH (m:Message)
                    WHERE m.{status_field} = 'pending'
                    SET m.{status_field} = 'none'
                    RETURN count(m) AS n
                    """
                    result = await session.run(cypher, {})

                record = await result.single()
                n = record["n"] if record else 0
                if n > 0:
                    logger.info(f"♻️  Reconciled {n} orphaned '{status_field}' pending → none")
                    total_reset += n

            except Exception as e:
                logger.error(f"Reconciliation error for {queue_name}/{status_field}: {e}")

    if total_reset > 0:
        logger.info(f"♻️  Reconciliation complete: {total_reset} statuses reset to 'none'")


async def generate_daily_reports():
    await generate_reports_for_frequency("daily")

async def generate_weekly_reports():
    await generate_reports_for_frequency("weekly")

async def generate_monthly_reports():
    await generate_reports_for_frequency("monthly")

def start_scheduler():
    # Every 5 minutes: reset orphaned 'pending' statuses whose Redis job is gone
    scheduler.add_job(
        reconcile_pending_statuses,
        IntervalTrigger(minutes=5),
        id="reconcile_pending_statuses",
        replace_existing=True,
    )

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
