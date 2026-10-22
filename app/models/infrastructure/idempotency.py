from typing import Optional
from sqlmodel import SQLModel, Field, UniqueConstraint
import uuid
from sqlalchemy import Column, BigInteger, Text
from app.utils.time.now_epoch_ms import now_epoch_ms

class CommandIdempotency(SQLModel, table=True):
    """
    Authoritative database-level command idempotency record.
    Guarantees duplicate network retries do not execute mutations twice.
    """
    __tablename__ = "command_idempotency"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_user_client_request_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True, foreign_key="user.id")
    client_request_id: str = Field(index=True, max_length=128)
    status: str = Field(default="COMPLETED", index=True, max_length=32)  # PENDING, COMPLETED, REJECTED, FAILED
    response_code: int = Field(default=200)
    response_json: str = Field(sa_column=Column(Text, nullable=False))
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger, nullable=False))
