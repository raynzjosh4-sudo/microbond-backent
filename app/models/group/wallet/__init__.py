from app.models.group.wallet.group_wallet import GroupWallet
from app.utils.time.now_epoch_ms import now_epoch_ms

utc_now = now_epoch_ms

__all__ = ["GroupWallet", "utc_now"]
