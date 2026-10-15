import logging
from fastapi import APIRouter, Depends
from app.core.internal_auth import verify_internal_task_request
from app.cronjobs.finance.payout_disbursement_worker import process_due_group_payouts

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/process-payouts",
    summary="Cloud Scheduler Trigger: Process due group payout disbursements",
    dependencies=[Depends(verify_internal_task_request)]
)
def process_payouts():
    """
    Invoked periodically by Google Cloud Scheduler (e.g. every 2 minutes).
    Finds matured payouts, verifies rules, and safely executes disbursements using row locks.
    """
    logger.info("[InternalTask] Triggering process_due_group_payouts...")
    process_due_group_payouts()
    return {"status": "success", "task": "process_payouts"}
