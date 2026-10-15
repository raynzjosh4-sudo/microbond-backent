import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import DistributeDividendsRequest
from .helpers import require_admin, get_club, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/distribute-dividends", summary="Admin injects returns and distributes dividends")
def distribute_dividends(
    group_id: str,
    request: DistributeDividendsRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Records profit return from an asset:
    - Deducts admin management fee cut if configured.
    - If AUTO_PUSH_PROPORTIONAL: records distributed dividends.
    - If REINVEST_IN_VAULT: adds return directly back into vault current_balance.
    """
    require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_club(group_id, session)
    now_ms = _now_ms()

    admin_fee = 0
    if settings.admin_management_fee_pct > 0:
        admin_fee = (request.total_profit_amount * settings.admin_management_fee_pct) // 100

    net_dividends = request.total_profit_amount - admin_fee

    settings.total_dividends_distributed += request.total_profit_amount
    if config.dividend_distribution_rule == "REINVEST_IN_VAULT":
        settings.current_balance += net_dividends
    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error distributing dividends: {e}")
        raise HTTPException(status_code=500, detail="Database error recording dividends.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"ðŸ’° Dividends Declared: {request.total_profit_amount} {group.currency} return from '{request.source_asset_name}'. "
            f"Action: {config.dividend_distribution_rule}."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Dividends successfully recorded and distributed.",
        "data": {
            "gross_profit": request.total_profit_amount,
            "admin_management_fee": admin_fee,
            "net_distributed": net_dividends,
            "distribution_rule": config.dividend_distribution_rule,
            "total_dividends_to_date": settings.total_dividends_distributed
        }
    }

