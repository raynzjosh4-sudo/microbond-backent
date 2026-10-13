from app.models.group.report.group_report import GroupReport
from app.utils.time.now_epoch_ms import now_epoch_ms

utc_now = now_epoch_ms

__all__ = ["GroupReport", "utc_now"]
