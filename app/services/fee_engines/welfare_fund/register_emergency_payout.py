def register_emergency_payout(current_pending: int) -> int:
    """
    Called immediately after an emergency disbursement is successfully sent
    to a member in crisis. Increments the group-level pending fee queue.

    This is the ONLY place the queue counter is ever increased. Call this
    after the MTN Disbursement API confirms the payout succeeded — never
    before, to avoid queue drift on failed payments.
    """
    if not isinstance(current_pending, int) or current_pending < 0:
        raise ValueError(f"current_pending must be a non-negative int. Got: {current_pending!r}")
    return current_pending + 1
