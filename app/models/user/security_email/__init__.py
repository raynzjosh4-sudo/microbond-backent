from app.models.user.security_email.user_security_email import UserSecurityEmail
from app.utils.time.now_utc_datetime import now_utc_datetime

utc_now = now_utc_datetime

__all__ = ["UserSecurityEmail", "utc_now"]
