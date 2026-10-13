from enum import Enum


class MidCycleJoinPolicy(str, Enum):
    """
    Configures how a new member joining an already-active Rotating Group
    is treated with respect to their financial obligation.
    """
    FRESH_START = "FRESH_START"
    BUY_IN_REQUIRED = "BUY_IN_REQUIRED"
