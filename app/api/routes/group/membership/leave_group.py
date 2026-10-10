from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation
from app.api.routes.group.chat.messages import broadcast_system_message_sync

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])

@router.delete("/{group_id}/membership/me", summary="Leave a group")
def leave_group(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify membership
    membership = session.query(GroupMembership).filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this group.")

    group = session.query(Group).filter_by(group_id=group_id).first()

    # 2. Check if the user is the group creator
    if group and group.created_by_user_id == current_user.id:
        if group.member_count > 1:
            raise HTTPException(
                status_code=400, 
                detail="You are the creator of this group. You must transfer ownership to another admin before leaving."
            )
        else:
            # If they are the only member, the group is essentially disbanded
            group.status = "CANCELLED"

    # 3. Financial Safety Lock
    # Prevent users from leaving if they owe money to the group
    pending_obligations = session.query(MemberObligation).filter(
        MemberObligation.group_id == group_id,
        MemberObligation.user_id == current_user.id,
        MemberObligation.status.in_(["PENDING", "LATE"])
    ).first()
    
    if pending_obligations:
        raise HTTPException(
            status_code=400, 
            detail="You cannot leave this group because you have outstanding financial obligations (pending or late payments)."
        )

    # 4. Remove membership
    session.delete(membership)
    
    # 5. Decrement member count
    if group:
        group.member_count = max(0, group.member_count - 1)
        
    session.commit()
    
    # --- CHAT INTEGRATION ---
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name} has left the group.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )
    
    return {"status": "success", "message": "You have successfully left the group."}
