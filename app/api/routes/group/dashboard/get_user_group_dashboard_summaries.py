from typing import List
from fastapi import APIRouter, Depends
from sqlmodel import Session
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import GroupListSummaryResponse
from app.services.group.dashboard_summary_service import GroupDashboardSummaryService

router = APIRouter()

class TotalUnreadCountResponse(BaseModel):
    total_unread_count: int = Field(default=0, ge=0)

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

@router.get(
    "/unread-count",
    response_model=TotalUnreadCountResponse,
    summary="Get Total Unread Message Count",
    description="Lightweight endpoint for rendering the bottom navigation tab badge count without loading all group summaries."
)
def get_user_total_unread_count(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    total = GroupDashboardSummaryService.get_user_total_unread_count(
        session=session,
        user_id=current_user.id
    )
    return TotalUnreadCountResponse(total_unread_count=total)

