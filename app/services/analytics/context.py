"""
Per-request data context for analytics metrics.

Datasets are loaded lazily (only if a requested metric needs them) and cached for
the request. Metrics are pure functions over these plain rows, which keeps them
unit-testable without a database: tests can pre-load rows via ``preloaded``.
"""
from __future__ import annotations

from functools import cached_property
from typing import Any, Dict, List, NamedTuple, Optional

from app.services.analytics.buckets import BucketPlan


class Obligation(NamedTuple):
    id: int
    user_id: str
    due_date: int
    amount_due: int
    amount_paid: int
    status: str


class Deposit(NamedTuple):
    user_id: Optional[str]
    obligation_id: Optional[int]
    amount: int
    settled_at: int


class Payout(NamedTuple):
    user_id: str
    status: str
    payout_date: int
    amount_expected: int
    amount_received: int


class Member(NamedTuple):
    user_id: str
    status: str
    joined_at: int
    left_at: Optional[int]


class AnalyticsContext:
    def __init__(
        self,
        plan: BucketPlan,
        now_ms: int,
        session: Any = None,
        group_id: Optional[str] = None,
        preloaded: Optional[Dict[str, list]] = None,
    ) -> None:
        self.plan = plan
        self.now_ms = now_ms
        self.session = session
        self.group_id = group_id
        self.memo: Dict[str, Any] = {}
        # cached_property is a non-data descriptor, so values placed in the
        # instance dict take precedence over the loaders below.
        for key, rows in (preloaded or {}).items():
            self.__dict__[key] = rows

    # ── Loaders ────────────────────────────────────────────────────────────

    @cached_property
    def obligations(self) -> List[Obligation]:
        """All obligations due before the end of the range (history needed for streaks/balances)."""
        from sqlmodel import select
        from app.models.group.finance import MemberObligation as M

        rows = self.session.exec(
            select(M.id, M.user_id, M.due_date, M.amount_due, M.amount_paid, M.status)
            .where(M.group_id == self.group_id, M.due_date < self.plan.end_ms)
            .order_by(M.user_id, M.due_date)
        ).all()
        return [Obligation(r[0], str(r[1]), r[2], r[3], r[4], r[5]) for r in rows]

    @cached_property
    def deposits(self) -> List[Deposit]:
        """Settled deposits from the immutable ledger, from the beginning of time up to range end."""
        from sqlmodel import select
        from app.models.group.ledger import LedgerEntry as L

        rows = self.session.exec(
            select(L.user_id, L.obligation_id, L.amount, L.settled_at).where(
                L.group_id == self.group_id,
                L.transaction_type == "DEPOSIT",
                L.status == "SETTLED",
                L.settled_at != None,  # noqa: E711
                L.settled_at < self.plan.end_ms,
            )
        ).all()
        return [Deposit(str(r[0]) if r[0] else None, r[1], r[2], r[3]) for r in rows]

    @cached_property
    def payouts(self) -> List[Payout]:
        """All payouts for the group (they are pre-scheduled, so future rows matter too)."""
        from sqlmodel import select
        from app.models.group.finance import GroupPayout as P

        rows = self.session.exec(
            select(P.user_id, P.status, P.payout_date, P.amount_expected, P.amount_received)
            .where(P.group_id == self.group_id)
        ).all()
        return [Payout(str(r[0]), r[1], r[2], r[3], r[4]) for r in rows]

    @cached_property
    def members(self) -> List[Member]:
        from sqlmodel import select
        from app.models.group.group import GroupMembership as G

        rows = self.session.exec(
            select(G.user_id, G.status, G.joined_at, G.left_at).where(G.group_id == self.group_id)
        ).all()
        return [Member(str(r[0]), r[1] or "", r[2], r[3]) for r in rows]

    @cached_property
    def chat_times(self) -> List[int]:
        from sqlmodel import select
        from app.models.group.chat import GroupChatMessage as C

        rows = self.session.exec(
            select(C.created_at).where(
                C.group_id == self.group_id,
                C.is_deleted == False,  # noqa: E712
                C.created_at >= self.plan.start_ms,
                C.created_at < self.plan.end_ms,
            )
        ).all()
        return [r if isinstance(r, int) else r[0] for r in rows]
