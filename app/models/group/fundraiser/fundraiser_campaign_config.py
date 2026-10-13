from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class FundraiserCampaignConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. All fields are LOCKED after creation.
    Protects donors — they know where money goes before they donate.
    """
    __tablename__ = "fundraisercampaignconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # 1. Campaign Target & Timeline (locked)
    target_amount: int = Field(default=0, sa_column=Column(BigInteger),
                               description="Total to raise. 0 = open-ended, no fixed goal.")
    campaign_deadline: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True),
                                             description="When donations stop (epoch ms). Null = no deadline.")

    # 2. Where the Money Goes (locked)
    payout_destination_type: str = Field(default="NOMINATED_ACCOUNT",
                                         description="NOMINATED_ACCOUNT or SPLIT_EQUALLY")
    nominated_account_id: Optional[str] = Field(default=None,
                                                 description="Verified bank/mobile money account ID.")

    # 3. How the Money is Released (locked)
    payout_trigger_mode: str = Field(default="MANUAL",
                                     description="MANUAL (admin releases) or AUTO_ON_DEADLINE.")
    require_multi_signoff: bool = Field(default=False,
                                        description="Multiple signers must approve before money moves.")
    signoff_count_required: int = Field(default=1,
                                        description="Number of signers needed (only when multi-signoff is on).")

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
