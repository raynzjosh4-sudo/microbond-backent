from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger, JSON, String
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms


class RotatingCycleReport(SQLModel, table=True):
    """
    Immutable milestone audit statement generated upon cycle completion in rotating groups.
    Includes financial totals, recipient details, individual member compliance, and a
    cryptographic SHA-256 seal over the double-entry ledger entries.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: str = Field(default_factory=lambda: f"rep_rot_{uuid.uuid4().hex[:12]}", unique=True, index=True)
    
    group_id: str = Field(foreign_key="group.group_id", index=True)
    cycle_number: int = Field(index=True)
    report_type: str = Field(default="ROTATING_CYCLE_COMPLETION", index=True)
    
    # Financial snapshot
    expected_pool_target: int = Field(default=0, sa_column=Column(BigInteger))
    actual_collected_amount: int = Field(default=0, sa_column=Column(BigInteger))
    collection_rate_percentage: float = Field(default=0.0)
    gross_payout_amount: int = Field(default=0, sa_column=Column(BigInteger))
    early_security_hold_deducted: int = Field(default=0, sa_column=Column(BigInteger))
    net_payout_disbursed: int = Field(default=0, sa_column=Column(BigInteger))
    
    # Recipient snapshot
    recipient_user_id: uuid.UUID = Field(index=True)
    recipient_name: str = Field(default="Member")
    recipient_turn_position: int = Field(default=1)
    
    # Full Canonical Payload conforming to plan specification
    report_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Cryptographic Audit Integrity Seal
    ledger_entries_count: int = Field(default=0)
    cryptographic_hash_sha256: str = Field(index=True)
    certified_by: str = Field(default="Microbond Authoritative Ledger Engine")
    
    generated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
