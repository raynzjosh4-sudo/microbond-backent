def get_new_pending_count_after_deposit(current_pending: int, fees_cleared: int) -> int:
    """
    Helper to safely compute the new pending count after a deposit absorbs
    fees. Clamps to 0 to prevent negative values from race conditions.
    """
    return max(0, current_pending - fees_cleared)
