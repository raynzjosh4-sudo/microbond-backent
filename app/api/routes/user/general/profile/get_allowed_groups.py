from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.models.user.user import User
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.services.group.group_auth_service import (
    evaluate_group_creation_permissions,
)

router = APIRouter()


@router.get("/me/allowed-groups", summary="Get Authorized Group Creation Types")
def get_allowed_groups(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    evaluation = evaluate_group_creation_permissions(session, current_user.id)
    return {
        "status": "success",
        "allowed_groups": evaluation["allowed_groups"],
        "reasons": evaluation["reasons"],
        "allowed_group_details": evaluation["allowed_group_details"],
        "groups": evaluation["all_groups"],
    }
