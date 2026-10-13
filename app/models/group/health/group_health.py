from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupHealth(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # 1. Overall Grades
    health_grade: str = Field(default="A+", description="A+, A, B, C, D, F")
    risk_level: str = Field(default="LOW", description="LOW, MODERATE, HIGH, CRITICAL")
    
    # 2. Repayment & Default Metrics
    on_time_repayment_rate_pct: float = Field(default=100.0)
    active_default_rate_pct: float = Field(default=0.0)
    total_defaulted_amount: float = Field(default=0.0)
    members_in_arrears_count: int = Field(default=0)
    
    # 3. Liquidity & Capital Health
    liquidity_ratio: float = Field(default=1.0, description="Available funds / upcoming obligations")
    reserve_fund_balance: float = Field(default=0.0)
    
    # 4. Activity & Engagement
    average_member_trust_score: float = Field(default=100.0)
    consecutive_successful_cycles: int = Field(default=0)
    dispute_rate_pct: float = Field(default=0.0)
    
    # Metadata
    last_recalculated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
