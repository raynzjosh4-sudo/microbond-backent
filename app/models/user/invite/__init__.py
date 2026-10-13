from app.models.user.invite.invite import Invite
from app.utils.time.now_utc_datetime import now_utc_datetime

utc_now = now_utc_datetime

__all__ = ["Invite", "utc_now"]
