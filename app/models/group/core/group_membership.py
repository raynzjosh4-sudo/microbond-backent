from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupMembership(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    membership_id: str = Field(unique=True, index=True) # UUID string
    
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    # Role & standing
    role: str = Field(default="MEMBER") # ADMIN, MEMBER, etc.
    title: Optional[str] = Field(default=None) # e.g. Treasurer
    status: str = Field(default="ACTIVE")
    group_trust_score: Optional[int] = Field(default=None)
    is_signer: bool = Field(default=False, description="Whether this member is on the multi-sig signer roster")
    auto_approve_small_requests: bool = Field(default=False)
    auto_approve_max_amount: Optional[float] = Field(default=None)
    
    # Rotating Settings
    payout_position: Optional[int] = Field(default=None, description="The assigned turn order in a rotating group (1, 2, 3...)")
    
    # Money in
    total_contributed: int = Field(default=0)
    
    # Personal Settings
    auto_pay_my_turn: bool = Field(default=True)
    proxy_contributor_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    payout_destination_id: Optional[str] = Field(default=None)
    payment_method_id: Optional[str] = Field(default=None)
    mute_notifications: bool = Field(default=False)
    custom_notification_tone: Optional[str] = Field(default="Default (Chime)")
    show_previews: bool = Field(default=True)
    include_chat_in_export: bool = Field(default=False)
    
    # SMS & Email Reminder Preferences (per-group)
    sms_reminders_opted_in: bool = Field(default=False, description="Member consented to SMS reminders in this group")
    sms_reminder_hours_before: int = Field(default=24, description="How many hours before the due date to send the SMS reminder")
    sms_fee_acknowledged: bool = Field(default=False, description="Member has been warned about the 50 UGX per-deposit SMS fee")
    pending_sms_fee_ugx: int = Field(default=0, description="Accumulated SMS fee UGX to deduct on next deposit")
    email_reminders_opted_in: bool = Field(default=True, description="Member opted in to email reminders in this group")
    email_reminder_hours_before: int = Field(default=24, description="How many hours before due date to send the email reminder")
    
    # Chat state
    is_favorite: bool = Field(default=False)
    is_chat_locked: bool = Field(default=False)
    unread_count: int = Field(default=0)
    
    # Lifecycle
    invited_by_user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    joined_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    left_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
