from app.models.group.health.group_health import GroupHealth
from app.utils.time.now_epoch_ms import now_epoch_ms

utc_now = now_epoch_ms

__all__ = ["GroupHealth", "utc_now"]
