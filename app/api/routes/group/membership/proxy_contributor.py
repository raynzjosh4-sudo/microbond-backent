from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session
from uuid import UUID

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership Proxies"])

class AssignProxyRequest(BaseModel):
    proxy_user_id: UUID

class ProxyUserResponse(BaseModel):
    user_id: UUID
    full_name: Optional[str]
    phone_number: str
    avatar_color: Optional[str]
    profile_picture_url: Optional[str]

@router.post("/{group_id}/membership/me/proxy", response_model=ProxyUserResponse, summary="Assign a proxy contributor")
def assign_proxy_contributor(
    group_id: str,
    request: AssignProxyRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify caller is in the group
    my_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not my_membership:
        raise HTTPException(status_code=404, detail="You are not a member of this group.")

    if request.proxy_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot assign yourself as a proxy.")

    # 2. Verify proxy is in the group
    proxy_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == request.proxy_user_id
    ).first()
    
    if not proxy_membership:
        raise HTTPException(status_code=400, detail="The designated proxy must be an active member of this group.")
        
    # 3. Get rich user details for the proxy
    proxy_user = session.query(User).filter(User.id == request.proxy_user_id).first()
    if not proxy_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 4. Assign proxy
    my_membership.proxy_contributor_id = request.proxy_user_id
    session.commit()
    
    from app.services.privacy import can_view_profile_photo
    allow_photo = can_view_profile_photo(
        proxy_user, viewer_user_id=current_user.id, shares_group=True
    )

    return ProxyUserResponse(
        user_id=proxy_user.id,
        full_name=proxy_user.full_name,
        phone_number=proxy_user.phone_number,
        avatar_color=proxy_user.avatar_color,
        profile_picture_url=proxy_user.profile_picture_url if allow_photo else None
    )

@router.delete("/{group_id}/membership/me/proxy", summary="Remove your proxy contributor")
def remove_proxy_contributor(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    my_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not my_membership:
        raise HTTPException(status_code=404, detail="You are not a member of this group.")

    my_membership.proxy_contributor_id = None
    session.commit()
    
    return {"status": "success", "message": "Proxy contributor has been successfully removed."}
