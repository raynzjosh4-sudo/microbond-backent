from pydantic import BaseModel


class ExecuteDepositResponse(BaseModel):
    status: str = "PROCESSING"
    message: str
    transaction_id: str
    provider: str
    formatted_phone_number: str
