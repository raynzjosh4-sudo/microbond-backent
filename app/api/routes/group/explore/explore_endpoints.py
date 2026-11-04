from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_optional_current_user
from app.models.user.user import User
from app.services.group.explore_service import ExploreGroupService
from app.schemas.explore_discovery import (
    ExploreDiscoveryResponse,
    ExploreCategoriesResponse,
    ExplorePreviewResponse,
)

router = APIRouter(prefix="/api/v1/groups/explore", tags=["Group Explore & Discovery"])


@router.get("", response_model=ExploreDiscoveryResponse, summary="Discover and Search Public Groups")
def explore_groups(
    q: Optional[str] = Query(None, description="Keyword search against group name and description"),
    type: Optional[str] = Query(None, description="Filter by group type (e.g. MERRY_GO_ROUND, TARGET_SAVINGS, INVESTMENT_CLUB)"),
    currency: Optional[str] = Query(None, description="Filter by currency (e.g. UGX, KES, USD)"),
    frequency: Optional[int] = Query(None, description="Collection interval in days (e.g. 1 for daily, 7 for weekly)"),
    min_contribution: Optional[float] = Query(None, ge=0, description="Minimum contribution amount"),
    max_contribution: Optional[float] = Query(None, ge=0, description="Maximum contribution amount"),
    hide_full: bool = Query(True, description="Exclude groups that have reached maximum capacity"),
    eligible_only: bool = Query(False, description="Show only groups the caller meets KYC and trust score criteria for"),
    sort_by: str = Query("POPULAR", description="Sort order: POPULAR, NEWEST, OLDEST, HEALTH"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Page size"),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> ExploreDiscoveryResponse:
    """
    Returns public discoverable groups.
    - Excludes private and invite-only groups.
    - Excludes groups with critical health risk.
    - Excludes groups the caller is already actively enrolled in.
    - Computes real-time caller eligibility flags (KYC, Trust Score, Capacity).
    """
    return ExploreGroupService.search_and_discover_groups(
        session=session,
        current_user=current_user,
        q=q,
        type=type,
        currency=currency,
        frequency=frequency,
        min_contribution=min_contribution,
        max_contribution=max_contribution,
        hide_full=hide_full,
        eligible_only=eligible_only,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.get("/categories", response_model=ExploreCategoriesResponse, summary="Explore Curated Group Collections")
def get_explore_categories(
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> ExploreCategoriesResponse:
    """
    Returns thematic curated group collections for discovery feeds:
    - Trending Rotating Circles
    - Goal & Target Savings
    - Top Rated & Grade A+ Circles
    - Open Starter Circles (Tier 1 friendly)
    """
    return ExploreGroupService.get_explore_categories(
        session=session,
        current_user=current_user,
    )


@router.get("/{group_id}/preview", response_model=ExplorePreviewResponse, summary="Public Group Preview")
def get_explore_group_preview(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> ExplorePreviewResponse:
    """
    Provides a comprehensive public preview of a discoverable group before joining,
    including rotation strategy, creator information, and user requirement checklist.
    """
    preview = ExploreGroupService.get_explore_group_preview(
        group_id=group_id,
        session=session,
        current_user=current_user,
    )
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found or is private/invite-only.",
        )
    return preview
