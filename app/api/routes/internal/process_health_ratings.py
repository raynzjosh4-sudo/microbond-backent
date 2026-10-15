import logging
from fastapi import APIRouter, Depends
from app.core.internal_auth import verify_internal_task_request
from app.cronjobs.health.daily_health_ratings import process_daily_health_ratings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/process-health-ratings",
    summary="Cloud Scheduler Trigger: Process group health ratings",
    dependencies=[Depends(verify_internal_task_request)]
)
def process_health_ratings():
    """
    Invoked periodically by Google Cloud Scheduler (e.g. every 6 hours).
    Computes reputation scores and defaults across all active savings groups.
    """
    logger.info("[InternalTask] Triggering process_daily_health_ratings...")
    process_daily_health_ratings()
    return {"status": "success", "task": "process_health_ratings"}
