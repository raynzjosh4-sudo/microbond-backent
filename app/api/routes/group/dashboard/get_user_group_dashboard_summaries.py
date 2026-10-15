from typing import List
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import GroupListSummaryResponse
from app.services.group.dashboard_summary_service import GroupDashboardSummaryService

router = APIRouter()

@router.get(
    "/summaries",
    response_model=List[GroupListSummaryResponse],
    summary="Get User Group Summaries & Animated Tickers",
    description="Pre-calculates avatar progress ring statuses, cycling action messages, and unread badges for the Android main screen."
)
def get_user_group_dashboard_summaries(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    return GroupDashboardSummaryService.get_user_dashboard_summaries(
        session=session,
        user_id=current_user.id
    )
