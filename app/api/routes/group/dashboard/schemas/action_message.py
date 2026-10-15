from pydantic import BaseModel

class ActionMessage(BaseModel):
    """
    Drives the animated vertical ticker text below each group title.
    Cycles automatically in Compose every 4-5 seconds.
    """
    text: str
    type: str  # e.g., "PAYOUT_TURN", "RECENT_CONTRIBUTION", "GOAL_PROGRESS", "SYSTEM_ALERT"
    has_blue_ticks: bool = True
    is_alert: bool = False
