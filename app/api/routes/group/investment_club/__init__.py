from fastapi import APIRouter
from .create_investment_club import router as create_investment_club_router, create_investment_club
from .get_investment_club_dashboard import router as get_investment_club_dashboard_router, get_investment_club_dashboard
from .update_investment_club_settings import router as update_investment_club_settings_router, update_investment_club_settings
from .buy_shares import router as buy_shares_router, buy_shares
from .create_investment_proposal import router as create_investment_proposal_router, create_investment_proposal
from .vote_on_proposal import router as vote_on_proposal_router, vote_on_proposal
from .execute_proposal import router as execute_proposal_router, execute_proposal
from .distribute_dividends import router as distribute_dividends_router, distribute_dividends
from .transfer_shares import router as transfer_shares_router, transfer_shares
from .apply_for_loan import router as apply_for_loan_router, apply_for_loan
from .list_loans import router as list_loans_router, list_loans
from .review_loan import router as review_loan_router, review_loan
from .repay_loan import router as repay_loan_router, repay_loan

router = APIRouter(prefix="/api/v1/groups/investment-club", tags=["Investment Club Groups"])
router.include_router(create_investment_club_router)
router.include_router(get_investment_club_dashboard_router)
router.include_router(update_investment_club_settings_router)
router.include_router(buy_shares_router)
router.include_router(create_investment_proposal_router)
router.include_router(vote_on_proposal_router)
router.include_router(execute_proposal_router)
router.include_router(distribute_dividends_router)
router.include_router(transfer_shares_router)
router.include_router(apply_for_loan_router)
router.include_router(list_loans_router)
router.include_router(review_loan_router)
router.include_router(repay_loan_router)
router.router = router

__all__ = [
    "router",
    "create_investment_club",
    "get_investment_club_dashboard",
    "update_investment_club_settings",
    "buy_shares",
    "create_investment_proposal",
    "vote_on_proposal",
    "execute_proposal",
    "distribute_dividends",
    "transfer_shares",
    "apply_for_loan",
    "list_loans",
    "review_loan",
    "repay_loan",
]
