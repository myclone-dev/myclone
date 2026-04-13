"""
Pydantic models for authentication API endpoints
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Request schema for user registration"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    fullname: str = Field(..., min_length=1, max_length=200, description="User full name")
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=30,
        description="Optional username (alphanumeric only, 3-30 chars)",
    )
    account_type: str = Field(
        default="creator",
        description="Account type: 'creator' (creates personas) or 'visitor' (purchases access). Defaults to 'creator'.",
    )
    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        """Validate account_type is either 'creator' or 'visitor'"""
        if v.lower() not in ["creator", "visitor"]:
            raise ValueError("account_type must be either 'creator' or 'visitor'")
        return v.lower()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate username format and restrictions

        Uses shared validation function from shared.utils.validators
        to ensure consistency across all authentication flows.

        Rules:
        - 3-30 characters
        - Alphanumeric only (letters and numbers)
        - No special characters allowed (no spaces, hyphens, underscores, etc.)
        - Case-insensitive (converted to lowercase)
        - Cannot be a reserved word

        Returns normalized username (lowercase, alphanumeric only)
        """
        if v is None:
            return None

        # Import here to avoid circular dependency
        from shared.utils.validators import validate_username_format

        is_valid, error_message, normalized_username = validate_username_format(v)

        if not is_valid:
            raise ValueError(error_message)

        return normalized_username

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "SecurePass123",
                "fullname": "John Doe",
                "username": "johndoe",
            }
        }


class RegisterResponse(BaseModel):
    """Response schema for successful registration"""

    message: str = Field(..., description="Success message")
    email: str = Field(..., description="Registered email address")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Registration successful! Please check your email to verify your account.",
                "email": "john.doe@example.com",
            }
        }


class LoginRequest(BaseModel):
    """Request schema for user login"""

    email: str = Field(..., description="Email or username")
    password: str = Field(..., description="User password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "SecurePass123",
            }
        }


class LoginResponse(BaseModel):
    """Response schema for successful login"""

    message: str = Field(..., description="Success message")
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    fullname: str = Field(..., description="User full name")
    account_type: str = Field(..., description="Account type: 'creator' or 'visitor'")
    token: Optional[str] = Field(None, description="JWT token (also set in HTTP-only cookie)")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Login successful",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "john.doe@example.com",
                "fullname": "John Doe",
                "account_type": "creator",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }


class ForgotPasswordRequest(BaseModel):
    """Request schema for password reset request"""

    email: EmailStr = Field(..., description="User email address")

    class Config:
        json_schema_extra = {"example": {"email": "john.doe@example.com"}}


class ForgotPasswordResponse(BaseModel):
    """Response schema for password reset request"""

    message: str = Field(
        ...,
        description="Generic success message (sent even if email doesn't exist - security best practice)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "If an account with this email exists, a password reset link has been sent."
            }
        }


class ResetPasswordRequest(BaseModel):
    """Request schema for password reset confirmation"""

    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "550e8400-e29b-41d4-a716-446655440000",
                "new_password": "NewSecurePass123",
            }
        }


class ResetPasswordResponse(BaseModel):
    """Response schema for successful password reset"""

    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Password reset successful. You can now login with your new password."
            }
        }


class ResendVerificationRequest(BaseModel):
    """Request schema for resending verification email"""

    email: EmailStr = Field(..., description="User email address")

    class Config:
        json_schema_extra = {"example": {"email": "john.doe@example.com"}}


class ResendVerificationResponse(BaseModel):
    """Response schema for resend verification"""

    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {"message": "Verification email has been sent. Please check your inbox."}
        }


class VerifyEmailResponse(BaseModel):
    """Response schema for email verification"""

    message: str = Field(..., description="Success message")
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    fullname: str = Field(..., description="User full name")
    account_type: str = Field(..., description="Account type: 'creator' or 'visitor'")
    token: Optional[str] = Field(None, description="JWT token (also set in HTTP-only cookie)")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Email verified successfully! You are now logged in.",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "john.doe@example.com",
                "fullname": "John Doe",
                "account_type": "creator",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }


class SetPasswordRequest(BaseModel):
    """Request schema for OAuth users setting password"""

    password: str = Field(..., min_length=8, description="New password (min 8 characters)")

    class Config:
        json_schema_extra = {"example": {"password": "SecurePass123"}}


class SetPasswordResponse(BaseModel):
    """Response schema for successful password set"""

    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Password set successfully! You can now login with email and password."
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""

    detail: str = Field(..., description="Error message")

    class Config:
        json_schema_extra = {"example": {"detail": "Invalid credentials"}}


# Claim Account Models


class VerifyClaimCodeRequest(BaseModel):
    """Request schema for verifying claim code"""

    code: str = Field(..., description="Claim code from auto-onboard link")

    class Config:
        json_schema_extra = {"example": {"code": "abc123xyz789..."}}


class VerifyClaimCodeResponse(BaseModel):
    """Response schema for successful claim code verification"""

    message: str = Field(..., description="Success message")
    username: str = Field(..., description="Current username (editable)")
    email: str = Field(..., description="Current email (editable if auto-generated)")
    fullname: str = Field(..., description="User full name")
    is_generated_email: bool = Field(
        ..., description="True if email is auto-generated (@auto-generated.local)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Claim code verified successfully",
                "username": "john_doe",
                "email": "john_doe@auto-generated.local",
                "fullname": "John Doe",
                "is_generated_email": True,
            }
        }


class SubmitClaimRequest(BaseModel):
    """Request schema for submitting claim with credentials"""

    code: str = Field(..., description="Valid claim code")
    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Username (alphanumeric only, 3-30 chars)",
    )
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format using shared validation function"""
        from shared.utils.validators import validate_username_format

        is_valid, error_message, normalized_username = validate_username_format(v)

        if not is_valid:
            raise ValueError(error_message)

        return normalized_username

    class Config:
        json_schema_extra = {
            "example": {
                "code": "abc123xyz789...",
                "username": "johndoe",
                "email": "john.doe@example.com",
                "password": "SecurePass123",
            }
        }


class SubmitClaimResponse(BaseModel):
    """Response schema for successful claim submission"""

    message: str = Field(..., description="Success message")
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    fullname: str = Field(..., description="User full name")
    account_type: str = Field(..., description="Account type: 'creator' or 'visitor'")
    token: Optional[str] = Field(None, description="JWT token (also set in HTTP-only cookie)")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Account claimed successfully! You are now logged in.",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "john.doe@example.com",
                "fullname": "John Doe",
                "account_type": "creator",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }


class CheckUsernameRequest(BaseModel):
    """Request schema for checking username availability"""

    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Username to check (alphanumeric only, 3-30 chars)",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format using shared validation function"""
        from shared.utils.validators import validate_username_format

        is_valid, error_message, normalized_username = validate_username_format(v)

        if not is_valid:
            raise ValueError(error_message)

        return normalized_username

    class Config:
        json_schema_extra = {"example": {"username": "johndoe"}}


class CheckUsernameResponse(BaseModel):
    """Response schema for username availability check"""

    available: bool = Field(..., description="True if username is available")
    username: str = Field(..., description="Normalized username that was checked")

    class Config:
        json_schema_extra = {"example": {"available": True, "username": "johndoe"}}


class GetClaimLinkRequest(BaseModel):
    """Request schema for getting or generating claim link"""

    user_id: Optional[str] = Field(None, description="User ID (UUID)")
    username: Optional[str] = Field(None, description="Username")
    email: Optional[EmailStr] = Field(None, description="Email address")

    @field_validator("user_id", "username", "email")
    @classmethod
    def at_least_one_field(cls, v, info):
        """Ensure at least one identifier is provided"""
        # This validator runs for each field, so we can't check all fields here
        # We'll validate in the endpoint instead
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
            }
        }


class GetClaimLinkResponse(BaseModel):
    """Response schema for claim link"""

    message: str = Field(..., description="Success message")
    claim_link: str = Field(..., description="Claim account link")
    expires_at: str = Field(..., description="Claim code expiration time (ISO format)")
    is_new: bool = Field(
        ..., description="True if new code was generated, False if existing code returned"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Claim link generated successfully",
                "claim_link": "https://app.example.com/claim-account?code=abc123xyz789...",
                "expires_at": "2025-11-26T12:00:00+00:00",
                "is_new": True,
            }
        }


# OTP Authentication Models (VISITOR users)


class RequestOTPRequest(BaseModel):
    """Request schema for OTP authentication (registration + login)"""

    email: EmailStr = Field(..., description="User email address")
    fullname: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="User full name (optional, falls back to email prefix if not provided)",
    )
    phone: Optional[str] = Field(
        None, min_length=10, max_length=15, description="Phone number (optional)"
    )
    persona_username: Optional[str] = Field(
        None,
        max_length=100,
        description="Username of persona owner (for whitelabel email - sends OTP from their custom domain)",
        alias="personaUsername",
    )
    source: Optional[str] = Field(
        None,
        description="Source of OTP request: 'email_capture' for conversation email capture, None for regular signup/login",
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "email": "visitor@example.com",
                "fullname": "John Doe",
                "phone": "+1234567890",
                "personaUsername": "rohans",
                "source": "email_capture",
            }
        }


class RequestOTPResponse(BaseModel):
    """Response schema for OTP request"""

    success: bool = Field(..., description="Whether OTP was sent successfully")
    message: str = Field(..., description="Success message")
    is_new_user: bool = Field(
        ..., description="True if new user was created, False if existing user"
    )
    account_type: Optional[str] = Field(
        None,
        description="Account type ('visitor' or 'creator'). Helps frontend decide whether to show OTP input or password login.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Verification code sent to visitor@example.com. Please check your inbox.",
                "is_new_user": True,
                "account_type": "visitor",
            }
        }


class VerifyOTPRequest(BaseModel):
    """Request schema for OTP verification"""

    email: EmailStr = Field(..., description="User email address")
    otp_code: str = Field(
        ..., min_length=6, max_length=6, description="6-digit OTP code", alias="otpCode"
    )

    class Config:
        populate_by_name = True  # Accept both camelCase and snake_case
        json_schema_extra = {
            "example": {
                "email": "visitor@example.com",
                "otpCode": "123456",
            }
        }


class VerifyOTPResponse(BaseModel):
    """Response schema for successful OTP verification"""

    success: bool = Field(..., description="Whether OTP was verified successfully")
    message: str = Field(..., description="Success message")
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    fullname: str = Field(..., description="User full name")
    account_type: str = Field(..., description="Account type (always 'visitor' for OTP auth)")
    token: Optional[str] = Field(None, description="JWT token (also set in HTTP-only cookie)")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Email verified successfully! You are now logged in.",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "visitor@example.com",
                "fullname": "John Doe",
                "account_type": "visitor",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
