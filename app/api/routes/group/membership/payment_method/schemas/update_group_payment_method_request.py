from pydantic import BaseModel
from typing import Optional

class UpdateGroupPaymentMethodRequest(BaseModel):
    payment_method_id: Optional[str]
