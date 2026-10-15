import logging
from fastapi import APIRouter, Depends
from app.core.internal_auth import verify_internal_task_request
from app.cronjobs.launcher.group_launcher import check_and_launch_pending_groups

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/launch-groups",
    summary="Cloud Scheduler Trigger: Auto-launch pending groups",
    dependencies=[Depends(verify_internal_task_request)]
)
def launch_groups():
    """
    Invoked periodically by Google Cloud Scheduler (e.g. every 1 minute).
    Checks and activates groups whose start times or capacity conditions have matured.
    """
    logger.info("[InternalTask] Triggering check_and_launch_pending_groups...")
    check_and_launch_pending_groups()
    return {"status": "success", "task": "launch_groups"}
