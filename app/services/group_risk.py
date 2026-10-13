"""
group_risk facade — redirects to app.services.group.risk
"""
from app.services.group.risk import check_user_join_eligibility

__all__ = ["check_user_join_eligibility"]
