from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Column, BigInteger, Text
from app.utils.time.now_epoch_ms import now_epoch_ms

class AuditEvent(SQLModel, table=True):
    """
    Immutable audit event record with cryptographically verified SHA-256 block hash chaining.
    """
    __tablename__ = "audit_event"

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_user_id: Optional[uuid.UUID] = Field(default=None, index=True, foreign_key="user.id")
    action: str = Field(index=True, max_length=64)  # JOIN_REQUESTED, MEMBER_ACTIVATED, PAYOUT_EXECUTED, etc.
    entity_type: str = Field(index=True, max_length=64)  # GROUP, PAYOUT, WALLET, USER
    entity_id: str = Field(index=True, max_length=128)
    payload_json: str = Field(sa_column=Column(Text, nullable=False))
    previous_hash: str = Field(default="0" * 64, max_length=64)
    current_hash: str = Field(max_length=64, index=True)
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger, nullable=False))
