from enum import Enum


class LedgerStatus(str, Enum):
    """
    The member's payment standing relative to the group schedule today.
    """
    AHEAD     = "AHEAD"      # Paid more than expected — reminders silenced
    ON_TRACK  = "ON_TRACK"   # Exactly on schedule — no action needed
    BEHIND    = "BEHIND"     # Owes arrears — show red card + reminder
