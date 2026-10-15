import logging
from fastapi import APIRouter, Depends
from app.core.internal_auth import verify_internal_task_request
from app.cronjobs.finance.late_fee_processor import process_daily_late_fees

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/process-late-fees",
    summary="Cloud Scheduler Trigger: Process daily group late fees",
    dependencies=[Depends(verify_internal_task_request)]
)
def process_late_fees():
    """
    Invoked periodically by Google Cloud Scheduler (e.g. hourly or daily).
    Calculates and levies late penalty fees on delinquent members.
    """
    logger.info("[InternalTask] Triggering process_daily_late_fees...")
    process_daily_late_fees()
    return {"status": "success", "task": "process_late_fees"}
