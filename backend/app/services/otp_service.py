"""
OTP Service - Handles email-based OTP verification for persona access control

Uses Resend API to send verification emails with 6-digit OTP codes.
Integrates with PersonaAccessRepository for OTP creation and verification.

Supports whitelabel email domains - if the persona owner has a verified
custom email domain, emails will be sent from their domain instead of myclone.is.
"""

import logging
from typing import Optional
from uuid import UUID

import resend

from shared.config import settings
from shared.database.repositories import get_persona_access_repository

logger = logging.getLogger(__name__)

# Configure Resend API
resend.api_key = settings.resend_api_key


class OTPService:
    """Service for sending OTP verification emails"""

    def __init__(self):
        self.repo = get_persona_access_repository()
        self.from_email = settings.resend_from_email  # Default sender

    async def _get_sender_for_user(self, user_id: UUID) -> str:
        """
        Get the sender email for a user.

        If the user has a verified custom email domain, return that sender.
        Otherwise, return the default MyClone sender.

        Args:
            user_id: User ID to look up custom domain for

        Returns:
            Formatted sender string (e.g., "Name <email@domain.com>")
        """
        try:
            from sqlalchemy import select

            from shared.database.models.custom_email_domain import (
                CustomEmailDomain,
                EmailDomainStatus,
            )
            from shared.database.models.database import async_session_maker

            async with async_session_maker() as session:
                stmt = (
                    select(CustomEmailDomain)
                    .where(
                        CustomEmailDomain.user_id == user_id,
                        CustomEmailDomain.status == EmailDomainStatus.VERIFIED,
                    )
                    .limit(1)
                )
                result = await session.execute(stmt)
                custom_domain = result.scalar_one_or_none()

                if custom_domain:
                    logger.info(
                        f"Using custom email domain {custom_domain.domain} for user {user_id}"
                    )
                    return custom_domain.sender_address

        except Exception as e:
            logger.warning(f"Failed to look up custom email domain for user {user_id}: {e}")

        return self.from_email

    async def send_otp_email(
        self,
        persona_id: UUID,
        persona_name: str,
        email: str,
        first_name: Optional[str] = None,
        persona_owner_id: Optional[UUID] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Send OTP verification email

        Supports whitelabel email domains - if persona_owner_id is provided
        and the user has a verified custom email domain, the email will be
        sent from their domain instead of myclone.is.

        Args:
            persona_id: Persona UUID
            persona_name: Persona display name (for email template)
            email: Recipient email address
            first_name: Recipient's first name (optional, for personalization)
            persona_owner_id: Optional persona owner's user ID for custom sender lookup

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Check rate limiting (max 6 OTPs per hour)
            recent_count = await self.repo.get_recent_otp_count(persona_id, email, hours=1)
            if recent_count >= 6:
                return False, "Too many OTP requests. Please try again later."

            # Create OTP record in database
            otp_record = await self.repo.create_otp(persona_id, email, expires_in_minutes=5)

            # Determine sender - use custom domain if available
            if persona_owner_id:
                from_email = await self._get_sender_for_user(persona_owner_id)
            else:
                from_email = self.from_email

            # Generate email content with optional custom branding
            html_content = self._generate_html_email(
                persona_name=persona_name,
                otp_code=otp_record.otp_code,
                first_name=first_name,
            )

            plain_text_content = self._generate_plain_text_email(
                persona_name=persona_name,
                otp_code=otp_record.otp_code,
                first_name=first_name,
            )

            # Send email via Resend
            params = {
                "from": from_email,
                "to": [email],
                "subject": f"Your verification code for {persona_name}",
                "html": html_content,
                "text": plain_text_content,
            }

            response = resend.Emails.send(params)

            logger.info(
                f"OTP email sent successfully to {email} for persona {persona_id}, "
                f"email_id={response.get('id')}, from={from_email}"
            )
            return True, None

        except Exception as e:
            logger.error(f"Error sending OTP email to {email}: {e}")
            return False, "Failed to send verification email. Please try again."

    def _generate_html_email(
        self, persona_name: str, otp_code: str, first_name: Optional[str] = None
    ) -> str:
        """Generate HTML email template"""
        greeting = f"Hi {first_name}," if first_name else "Hi,"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #ffffff;
                    border-radius: 8px;
                    padding: 40px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #6366f1;
                }}
                .otp-code {{
                    background-color: #f3f4f6;
                    border: 2px dashed #6366f1;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                    margin: 30px 0;
                }}
                .otp-number {{
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    color: #6366f1;
                    font-family: 'Courier New', monospace;
                }}
                .info {{
                    background-color: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 12px 16px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                    font-size: 12px;
                    color: #6b7280;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">MyClone</div>
                </div>

                <p>{greeting}</p>

                <p>You requested access to chat with <strong>{persona_name}</strong>. Please use the verification code below to complete your access request:</p>

                <div class="otp-code">
                    <div class="otp-number">{otp_code}</div>
                </div>

                <div class="info">
                    <strong>⏱️ This code expires in 5 minutes</strong><br>
                    You have 3 attempts to enter the correct code.
                </div>

                <p>If you didn't request this code, you can safely ignore this email.</p>

                <div class="footer">
                    <p>© 2025 MyClone. All rights reserved.</p>
                    <p>This is an automated email. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_plain_text_email(
        self, persona_name: str, otp_code: str, first_name: Optional[str] = None
    ) -> str:
        """Generate plain text email template (fallback)"""
        greeting = f"Hi {first_name}," if first_name else "Hi,"

        return f"""{greeting}

You requested access to chat with {persona_name}.

Your verification code is: {otp_code}

This code expires in 5 minutes and you have 3 attempts to enter it correctly.

If you didn't request this code, you can safely ignore this email.

---
MyClone
This is an automated email. Please do not reply.
"""


# Singleton instance
_otp_service: Optional[OTPService] = None


def get_otp_service() -> OTPService:
    """Get singleton OTP service instance"""
    global _otp_service
    if _otp_service is None:
        _otp_service = OTPService()
    return _otp_service
