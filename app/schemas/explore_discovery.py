from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ExploreFinancialTermsSummary(BaseModel):
    contribution_amount: Optional[float] = Field(default=None, description="Per-interval contribution amount")
    collection_frequency_days: Optional[int] = Field(default=None, description="Frequency in days (e.g. 1 = daily, 7 = weekly)")
    saving_days_per_cycle: Optional[int] = Field(default=None, description="Number of collection days per cycle")
    expected_pool_per_cycle: Optional[float] = Field(default=None, description="Total expected pool target per cycle")
    target_amount: Optional[float] = Field(default=None, description="Overall goal or target amount if applicable")


class ExploreHealthSummary(BaseModel):
    health_grade: str = Field(default="A+", description="Health letter grade (A+, A, B, C, D, F)")
    risk_level: str = Field(default="LOW", description="Risk level (LOW, MODERATE, HIGH, CRITICAL)")
    on_time_repayment_rate_pct: float = Field(default=100.0, description="Percentage of obligations paid on time")


class ExploreGovernanceSummary(BaseModel):
    requires_admin_approval: bool = Field(default=False, description="True if joining requires admin review")
    minimum_kyc_tier: int = Field(default=1, description="Minimum KYC tier required (0-3)")
    minimum_trust_score: Optional[int] = Field(default=None, description="Minimum caller trust score required")
    require_guarantor: bool = Field(default=False, description="True if a guarantor pledge is required")


class ExploreCallerStatus(BaseModel):
    is_eligible: bool = Field(default=True, description="Whether caller meets trust score and KYC criteria")
    ineligibility_reasons: List[str] = Field(default_factory=list, description="List of reasons if ineligible")
    can_join_instantly: bool = Field(default=True, description="True if caller is eligible and no admin approval is required")
    requires_approval: bool = Field(default=False, description="True if joining requires submitting an application")
    has_pending_join_request: bool = Field(default=False, description="True if caller already has a pending application")
    is_member: bool = Field(default=False, description="True if caller is already an enrolled member")
    mutual_contacts_count: int = Field(default=0, description="Number of phone contacts actively in this group")


class ExploreGroupCard(BaseModel):
    group_id: str
    name: str
    description: str = ""
    group_image_url: str = ""
    avatar_color: str = "Blue"
    type: str
    currency: str = "UGX"
    member_count: int = 0
    max_members: Optional[int] = None
    is_full: bool = False
    created_at: int
    financial_terms: ExploreFinancialTermsSummary
    health: ExploreHealthSummary
    governance: ExploreGovernanceSummary
    caller_status: ExploreCallerStatus


class ExploreDiscoveryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    has_more: bool
    items: List[ExploreGroupCard]


class ExploreCategoryCollection(BaseModel):
    id: str
    title: str
    description: str
    badge_label: Optional[str] = None
    count: int
    groups: List[ExploreGroupCard]


class ExploreCategoriesResponse(BaseModel):
    categories: List[ExploreCategoryCollection]


class ExplorePreviewResponse(BaseModel):
    group: ExploreGroupCard
    creator_name: Optional[str] = None
    payout_order_strategy: Optional[str] = None
    cycle_summary: Optional[str] = None
    join_requirements_checklist: List[Dict[str, Any]] = Field(default_factory=list)

