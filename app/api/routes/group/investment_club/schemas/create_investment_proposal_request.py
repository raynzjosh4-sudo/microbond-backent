from pydantic import BaseModel, Field
from typing import Optional

class CreateInvestmentProposalRequest(BaseModel):
    asset_name: str = Field(..., min_length=2, max_length=150, description="Title of the asset (e.g. 5 Acres Maize Farm)")
    asset_type: str = Field(..., description="e.g. AGRICULTURE, REAL_ESTATE, STOCKS, BONDS, MONEY_MARKET")
    required_capital: int = Field(..., gt=0, description="Capital required from the vault")
    expected_roi_pct: Optional[float] = Field(default=None, description="Expected annual or harvest return %")
    description: str = Field(..., min_length=10, max_length=1000, description="Details of the investment thesis")
    broker_destination_account: str = Field(..., description="Registered broker account or mobile money paybill")
