from pydantic import BaseModel


class ExportStatementRequest(BaseModel):
    months_back: int = 3
