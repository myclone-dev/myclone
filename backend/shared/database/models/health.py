from datetime import datetime

from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    database_status: str
    openai_status: str
