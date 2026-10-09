from pydantic import BaseModel

class CreatePaymentMethodRequest(BaseModel):
    provider_name: str
    account_number: str
    account_name: str
    is_default: bool = False

class PaymentMethodResponse(BaseModel):
    id: str
    provider_name: str
    account_number: str
    account_name: str
    is_default: bool
    masked_number: str
