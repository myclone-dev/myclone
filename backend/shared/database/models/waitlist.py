import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WaitlistBase(BaseModel):
    name: str = Field(
        ..., description="Name of the person joining the waitlist", min_length=1, max_length=255
    )
    email: str = Field(..., description="Email address of the person", max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        # RFC 5322 compliant email validation regex
        # Prevents: consecutive dots, leading/trailing dots, overly long emails
        email_regex = r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email address")
        return v.lower()


class WaitlistCreate(WaitlistBase):
    pass


class WaitlistResponse(WaitlistBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
