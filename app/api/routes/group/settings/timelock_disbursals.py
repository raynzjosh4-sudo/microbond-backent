from typing import Optional, List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.models.group.long_term import SharedWalletOperationalSettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Timelock Disbursals Settings"])


class UpdateTimelockDisbursalsRequest(BaseModel):
    # Enable payout delay: Force all large transactions to wait a specific period before completing
    enable_payout_delay: Optional[bool] = Field(
        default=None,
        description="Enable timelock delay before disbursement executes"
    )
    enable_timelock: Optional[bool] = Field(
        default=None,
        description="Alias for enable_payout_delay"
    )

    # Cooling duration: e.g. 24 or '24 Hours'
    cooling_duration: Optional[Union[int, str]] = Field(
        default=None,
        description="Cooling period before disbursements execute (e.g. 24 or '24 Hours')"
    )
    cooling_duration_hours: Optional[int] = Field(
        default=None,
        ge=1,
        le=168,
        description="Cooling window in hours (1 - 168 hours)"
    )
    timelock_duration_hours: Optional[int] = Field(
        default=None,
        ge=1,
        le=168,
        description="Alias for cooling_duration_hours"
    )


def _parse_cooling_hours(val: Union[int, str]) -> int:
    if isinstance(val, int):
        return min(max(val, 1), 168)
    cleaned = str(val).lower().replace("hours", "").replace("hour", "").replace("h", "").strip()
    try:
        parsed = int(cleaned)
        return min(max(parsed, 1), 168)
    except ValueError:
        return 24


@router.get(
    "/{group_id}/settings/timelock",
    summary="Get Timelock Disbursals & Fraud Prevention Settings",
    description="Returns payout delay toggle and cooling duration configuration."
)
@router.get(
    "/{group_id}/settings/timelock-disbursals",
    include_in_schema=False
)
def get_timelock_disbursals(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    if not fin:
        fin = GroupFinancialSettings(group_id=group_id)
        session.add(fin)
        session.commit()
        session.refresh(fin)

    duration = fin.timelock_duration_hours or 24
    duration_label = f"{duration} Hours" if duration != 1 else "1 Hour"

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": getattr(group, "name", "Group"),
            "enable_payout_delay": fin.enable_timelock,
            "enable_timelock": fin.enable_timelock,
            "cooling_duration_hours": duration,
            "timelock_duration_hours": duration,
            "cooling_duration": duration_label,
            "cooling_duration_display": duration_label,
            "available_cooling_durations": [
                {"hours": 6, "label": "6 Hours"},
                {"hours": 12, "label": "12 Hours"},
                {"hours": 24, "label": "24 Hours (Recommended)"},
                {"hours": 48, "label": "48 Hours"},
                {"hours": 72, "label": "72 Hours"}
            ],
            "allowed_options": [6, 12, 24, 48, 72],
            "description": (
                "Force all large transactions to wait a specific period before completing. "
                "Gives admins time to cancel fraudulent payouts."
            )
        }
    }


@router.patch(
    "/{group_id}/settings/timelock",
    summary="Update Timelock Disbursals & Fraud Prevention Settings",
    description="Updates payout delay toggle and cooling duration. Restricted to Group Admin."
)
@router.patch(
    "/{group_id}/settings/timelock-disbursals",
    include_in_schema=False
)
def update_timelock_disbursals(
    group_id: str,
    request: UpdateTimelockDisbursalsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update timelock settings.")

    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id).with_for_update()
    ).first()
    if not fin:
        fin = GroupFinancialSettings(group_id=group_id)

    # 1. Update enable_payout_delay / enable_timelock
    delay_val = request.enable_payout_delay if request.enable_payout_delay is not None else request.enable_timelock
    if delay_val is not None:
        fin.enable_timelock = delay_val

    # 2. Update cooling_duration / cooling_duration_hours / timelock_duration_hours
    duration_val = None
    if request.cooling_duration_hours is not None:
        duration_val = request.cooling_duration_hours
    elif request.timelock_duration_hours is not None:
        duration_val = request.timelock_duration_hours
    elif request.cooling_duration is not None:
        duration_val = _parse_cooling_hours(request.cooling_duration)

    if duration_val is not None:
        fin.timelock_duration_hours = duration_val

    session.add(fin)

    # 3. If Shared Wallet group, synchronize operational settings
    shared_wallet_settings = session.exec(
        select(SharedWalletOperationalSettings).where(SharedWalletOperationalSettings.group_id == group_id)
    ).first()
    if shared_wallet_settings and duration_val is not None:
        shared_wallet_settings.timelock_duration_hours = duration_val
        session.add(shared_wallet_settings)

    AuditService.record_event(
        session=session,
        action="TIMELOCK_DISBURSALS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "enable_timelock": fin.enable_timelock,
            "timelock_duration_hours": fin.timelock_duration_hours
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(fin)

    duration = fin.timelock_duration_hours or 24
    duration_label = f"{duration} Hours" if duration != 1 else "1 Hour"

    return {
        "status": "success",
        "message": "Timelock disbursals settings updated successfully.",
        "data": {
            "group_id": group_id,
            "group_name": getattr(group, "name", "Group"),
            "enable_payout_delay": fin.enable_timelock,
            "enable_timelock": fin.enable_timelock,
            "cooling_duration_hours": duration,
            "timelock_duration_hours": duration,
            "cooling_duration": duration_label,
            "cooling_duration_display": duration_label
        }
    }
