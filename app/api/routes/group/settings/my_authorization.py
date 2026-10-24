from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Approval Authorization Settings"])


class UpdateMyAuthorizationRequest(BaseModel):
    auto_approve_small_requests: Optional[bool] = Field(
        default=None,
        description="Whether to automatically approve small payout or spend requests"
    )
    auto_approve_max_amount: Optional[float] = Field(
        default=None,
        ge=0,
        le=500000,
        description="Maximum amount for auto-approval (must not exceed 500,000 UGX)"
    )


@router.get(
    "/{group_id}/settings/my-authorization",
    summary="Get My Approval Authorization & Auto-Approve Settings",
    description="Returns personal signing authorization status and auto-approval threshold."
)
@router.get(
    "/{group_id}/settings/approval-authorization",
    include_in_schema=False
)
def get_my_approval_authorization(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an active member of this group."
        )

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    is_admin = (membership.role == "ADMIN")
    is_signer = getattr(membership, "is_signer", False)
    is_authorized = is_admin or is_signer

    max_amount = membership.auto_approve_max_amount or 0.0

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": getattr(group, "name", "Group"),
            "user_id": str(current_user.id),
            "user_name": current_user.full_name or "Member",
            "role": membership.role,
            "is_admin": is_admin,
            "is_signer": is_signer,
            "is_authorized": is_authorized,
            "authorization_status": "Authorized" if is_authorized else "Unauthorized",
            "auto_approve_small_requests": membership.auto_approve_small_requests,
            "auto_approve_max_amount": max_amount,
            "auto_approve_max_amount_formatted": f"{int(max_amount):,} UGX",
            "max_allowed_limit": 500000,
            "max_allowed_limit_formatted": "500,000 UGX",
            "currency": "UGX",
            "description": (
                "When enabled, payout and disbursement requests up to your chosen limit "
                "(up to 500,000 UGX) are automatically approved with your signature without "
                "requiring manual confirmation."
            )
        }
    }


@router.patch(
    "/{group_id}/settings/my-authorization",
    summary="Update My Auto-Approve Small Requests Setting",
    description="Updates auto-approve toggle and threshold amount (must not exceed 500,000 UGX)."
)
@router.patch(
    "/{group_id}/settings/approval-authorization",
    include_in_schema=False
)
def update_my_approval_authorization(
    group_id: str,
    request: UpdateMyAuthorizationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an active member of this group."
        )

    is_admin = (membership.role == "ADMIN")
    is_signer = getattr(membership, "is_signer", False)
    if not (is_admin or is_signer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorized multi-signature signers or admins can configure auto-approval."
        )

    if request.auto_approve_small_requests is not None:
        if request.auto_approve_small_requests is True and request.auto_approve_max_amount is None and not membership.auto_approve_max_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must specify a maximum amount when enabling auto-approve."
            )
        membership.auto_approve_small_requests = request.auto_approve_small_requests

    if request.auto_approve_max_amount is not None:
        if request.auto_approve_max_amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auto-approve maximum amount cannot be negative."
            )
        if request.auto_approve_max_amount > 500000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auto-approve amount cannot exceed 500,000 UGX."
            )
        membership.auto_approve_max_amount = request.auto_approve_max_amount

    session.add(membership)

    AuditService.record_event(
        session=session,
        action="AUTO_APPROVE_SETTINGS_UPDATED",
        entity_type="GROUP_MEMBERSHIP",
        entity_id=f"{group_id}_{current_user.id}",
        payload={
            "user_id": str(current_user.id),
            "group_id": group_id,
            "auto_approve_small_requests": membership.auto_approve_small_requests,
            "auto_approve_max_amount": membership.auto_approve_max_amount
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(membership)

    max_amount = membership.auto_approve_max_amount or 0.0

    return {
        "status": "success",
        "message": "Approval authorization settings updated successfully.",
        "data": {
            "group_id": group_id,
            "user_id": str(current_user.id),
            "is_authorized": True,
            "authorization_status": "Authorized",
            "auto_approve_small_requests": membership.auto_approve_small_requests,
            "auto_approve_max_amount": max_amount,
            "auto_approve_max_amount_formatted": f"{int(max_amount):,} UGX",
            "max_allowed_limit": 500000,
            "max_allowed_limit_formatted": "500,000 UGX",
            "currency": "UGX"
        }
    }
