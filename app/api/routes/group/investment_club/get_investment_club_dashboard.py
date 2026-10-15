from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubMemberShare
from .helpers import get_club, require_member

router = APIRouter()

@router.get("/{group_id}/dashboard", summary="View club NAV, equity portfolio, and member shares")
def get_investment_club_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full status of the Investment Club:
    - Creation rules (Table 1)
    - Live portfolio balances & shares (Table 2)
    - Member's personal shares & equity percentage
    - Net Asset Value (NAV) breakdown
    """
    require_member(group_id, current_user, session)
    config, settings = get_club(group_id, session)

    # Member's equity
    member_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == current_user.id
        )
    ).first()

    shares_owned = member_share.shares_owned if member_share else 0
    total_invested = member_share.total_invested if member_share else 0

    equity_pct = 0.0
    if settings.total_shares_issued > 0:
        equity_pct = round((shares_owned / settings.total_shares_issued) * 100, 2)

    net_asset_value = settings.current_balance + settings.total_invested_capital

    return {
        "status": "success",
        "data": {
            "club_config": config.model_dump(mode="json"),
            "operational_settings": settings.model_dump(mode="json"),
            "net_asset_value": net_asset_value,
            "uninvested_vault_cash": settings.current_balance,
            "deployed_capital": settings.total_invested_capital,
            "my_equity": {
                "shares_owned": shares_owned,
                "total_invested": total_invested,
                "equity_percentage": equity_pct,
                "share_unit_price": config.share_unit_price
            }
        }
    }
