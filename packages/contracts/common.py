from datetime import datetime
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str


class TimeStamped(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None
