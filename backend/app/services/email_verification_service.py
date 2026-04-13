"""
Email verification service for user account verification

This service handles email verification token generation and email sending.
Tokens are stored in the auth_details table and expire after 24 hours.
"""

import asyncio
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import resend

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class EmailVerificationService:
    """
    Service for email verification operations

    Handles:
    - Verification token generation (UUID-based)
    - Verification email sending with links
    - Token expiration (24 hours default)
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize email verification service

        Args:
            api_key: Resend API key (defaults to settings.resend_api_key)
        """
        self.api_key = api_key or settings.resend_api_key
        self.logger = logging.getLogger(__name__)

        # Initialize Resend SDK with API key
        if self.api_key:
            resend.api_key = self.api_key
        else:
            self.logger.warning(
                "Resend API key not configured - verification emails will not be sent"
            )

    def generate_verification_token(self) -> tuple[str, datetime]:
        """
        Generate a verification token and expiration timestamp

        Returns:
            Tuple of (token, expiration_datetime)
            - token: UUID4 string (cryptographically secure)
            - expiration: Datetime when token expires (24 hours from now)

        Example:
            >>> service = EmailVerificationService()
            >>> token, expires = service.generate_verification_token()
            >>> len(token) == 36  # UUID4 format
            True
        """
        # Generate cryptographically secure token
        token = str(uuid.uuid4())

        # Calculate expiration (24 hours from now, configurable)
        expiration = datetime.now(timezone.utc) + timedelta(
            hours=settings.email_verification_token_expiry_hours
        )

        self.logger.debug(f"Generated verification token, expires at {expiration}")
        return (token, expiration)

    async def send_verification_email(
        self,
        to_email: str,
        fullname: str,
        verification_token: str,
    ) -> bool:
        """
        Send email verification email with link

        The verification link points to the frontend, which will extract the token
        and call the backend API to verify it.

        Args:
            to_email: Recipient email address
            fullname: User's full name for personalization
            verification_token: Verification token to include in link

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = EmailVerificationService()
            >>> token, _ = service.generate_verification_token()
            >>> await service.send_verification_email("user@example.com", "John Doe", token)
            True
        """
        if not self.api_key:
            self.logger.error("Cannot send verification email - Resend API key not configured")
            return False

        try:
            # Extract first name for personalization
            first_name = fullname.split()[0] if fullname else "there"

            # Construct verification link (frontend URL)
            # Frontend will extract token and call backend API
            verification_link = f"{settings.frontend_url}/verify-email?token={verification_token}"

            # Email HTML content with MyClone brand colors
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 0; background-color: #FAFAFA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);">
                    <!-- Header with gradient -->
                    <div style="background: linear-gradient(to bottom right, #FFF4CC, #FFF8F2, #FFF4EB); padding: 40px 30px; text-align: center;">
                        <h1 style="margin: 0; font-size: 28px; color: #121212; font-weight: 600;">Welcome to MyClone!</h1>
                    </div>

                    <!-- Content -->
                    <div style="padding: 40px 30px;">
                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 20px 0;">Hi {first_name},</p>

                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 30px 0;">
                            Thanks for signing up for MyClone! Please verify your email address by clicking the button below:
                        </p>

                        <!-- CTA Button -->
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="{verification_link}" style="background-color: #FFC329; color: #121212; padding: 14px 40px; text-decoration: none; border-radius: 8px; display: inline-block; font-size: 16px; font-weight: 600;">
                                Verify Email Address
                            </a>
                        </div>

                        <!-- Alternative link -->
                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0 0 10px 0;">
                            Or copy and paste this link into your browser:
                        </p>
                        <p style="font-size: 14px; line-height: 1.6; color: #B06B30; word-break: break-all; margin: 0 0 30px 0;">
                            {verification_link}
                        </p>

                        <!-- Info box -->
                        <div style="background-color: #FFF4CC; border-left: 4px solid #FFC329; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0;">
                                ⏰ This link will expire in {settings.email_verification_token_expiry_hours} hours.
                            </p>
                        </div>

                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0;">
                            If you didn't create an account with MyClone, please ignore this email.
                        </p>
                    </div>

                    <!-- Footer -->
                    <div style="background-color: #FAFAFA; padding: 30px; text-align: center; border-top: 1px solid #E5E5E5;">
                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0;">
                            Best,<br>
                            <span style="color: #121212; font-weight: 600;">The MyClone Team</span>
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Prepare email parameters
            params: resend.Emails.SendParams = {
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": "Verify your MyClone account",
                "html": html_content,
            }

            # Run synchronous Resend SDK call in thread pool
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(
                f"✅ Verification email sent successfully to {to_email}: {email_response.get('id')}"
            )
            return True

        except Exception as e:
            # Capture exception in Sentry
            capture_exception_with_context(
                e,
                extra={
                    "to_email": to_email,
                    "fullname": fullname,
                },
                tags={
                    "component": "email",
                    "operation": "send_verification_email",
                    "email_type": "verification",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to send verification email to {to_email}: {e}")
            return False

    async def send_verification_resend_email(
        self,
        to_email: str,
        fullname: str,
        verification_token: str,
    ) -> bool:
        """
        Send verification resend email (similar to initial verification)

        This is called when user requests to resend verification email.
        Content is slightly different to acknowledge it's a resend.

        Args:
            to_email: Recipient email address
            fullname: User's full name for personalization
            verification_token: New verification token

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.api_key:
            self.logger.error("Cannot send verification email - Resend API key not configured")
            return False

        try:
            # Extract first name for personalization
            first_name = fullname.split()[0] if fullname else "there"

            # Construct verification link
            verification_link = f"{settings.frontend_url}/verify-email?token={verification_token}"

            # Email HTML content with MyClone brand colors
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 0; background-color: #FAFAFA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);">
                    <!-- Header with gradient -->
                    <div style="background: linear-gradient(to bottom right, #FFF4CC, #FFF8F2, #FFF4EB); padding: 40px 30px; text-align: center;">
                        <h1 style="margin: 0; font-size: 28px; color: #121212; font-weight: 600;">Verify Your Email</h1>
                    </div>

                    <!-- Content -->
                    <div style="padding: 40px 30px;">
                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 20px 0;">Hi {first_name},</p>

                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 30px 0;">
                            We received a request to resend your email verification link. Click the button below to verify your email:
                        </p>

                        <!-- CTA Button -->
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="{verification_link}" style="background-color: #FFC329; color: #121212; padding: 14px 40px; text-decoration: none; border-radius: 8px; display: inline-block; font-size: 16px; font-weight: 600;">
                                Verify Email Address
                            </a>
                        </div>

                        <!-- Alternative link -->
                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0 0 10px 0;">
                            Or copy and paste this link into your browser:
                        </p>
                        <p style="font-size: 14px; line-height: 1.6; color: #B06B30; word-break: break-all; margin: 0 0 30px 0;">
                            {verification_link}
                        </p>

                        <!-- Info box -->
                        <div style="background-color: #FFF4CC; border-left: 4px solid #FFC329; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0;">
                                ⏰ This link will expire in {settings.email_verification_token_expiry_hours} hours.
                            </p>
                        </div>

                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0;">
                            If you didn't request this email, please ignore it.
                        </p>
                    </div>

                    <!-- Footer -->
                    <div style="background-color: #FAFAFA; padding: 30px; text-align: center; border-top: 1px solid #E5E5E5;">
                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0;">
                            Best,<br>
                            <span style="color: #121212; font-weight: 600;">The MyClone Team</span>
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Prepare email parameters
            params: resend.Emails.SendParams = {
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": "Verify your MyClone account",
                "html": html_content,
            }

            # Run synchronous Resend SDK call in thread pool
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(
                f"✅ Verification resend email sent successfully to {to_email}: {email_response.get('id')}"
            )
            return True

        except Exception as e:
            # Capture exception in Sentry
            capture_exception_with_context(
                e,
                extra={
                    "to_email": to_email,
                    "fullname": fullname,
                },
                tags={
                    "component": "email",
                    "operation": "send_verification_resend_email",
                    "email_type": "verification_resend",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to send verification resend email to {to_email}: {e}")
            return False

    def generate_otp_code(self) -> tuple[str, datetime]:
        """
        Generate a 6-digit OTP code and expiration timestamp

        Returns:
            Tuple of (otp_code, expiration_datetime)
            - otp_code: 6-digit numeric string (cryptographically secure)
            - expiration: Datetime when OTP expires (5 minutes from now)

        Example:
            >>> service = EmailVerificationService()
            >>> otp, expires = service.generate_otp_code()
            >>> len(otp) == 6  # 6-digit format
            True
            >>> otp.isdigit()  # All digits
            True
        """
        # Generate cryptographically secure 6-digit OTP
        # secrets.randbelow(900000) gives 0-899999, adding 100000 gives 100000-999999
        otp_code = str(secrets.randbelow(900000) + 100000)

        # Calculate expiration (5 minutes from now)
        expiration = datetime.now(timezone.utc) + timedelta(minutes=5)

        self.logger.debug(f"Generated OTP code (redacted), expires at {expiration}")
        return (otp_code, expiration)

    async def send_otp_email(
        self,
        to_email: str,
        fullname: str,
        otp_code: str,
        purpose: str = "verification",
        from_email: str | None = None,
    ) -> bool:
        """
        Send OTP verification email

        The OTP is displayed prominently for the user to type into the UI.
        This keeps the user on the same page (no tab switching like magic links).

        Args:
            to_email: Recipient email address
            fullname: User's full name for personalization
            otp_code: 6-digit OTP code
            purpose: Purpose of OTP - 'verification' for signup, 'login' for returning users, 'email_capture' for conversation email capture
            from_email: Optional custom sender email (for whitelabel). Defaults to settings.resend_from_email

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = EmailVerificationService()
            >>> otp, _ = service.generate_otp_code()
            >>> await service.send_otp_email("user@example.com", "John Doe", otp)
            True
        """
        if not self.api_key:
            self.logger.error("Cannot send OTP email - Resend API key not configured")
            return False

        try:
            # Extract first name for personalization
            first_name = fullname.split()[0] if fullname else "there"

            # Customize subject and content based on purpose
            if purpose == "login":
                subject = "Your MyClone login code"
                header_text = "Login to MyClone"
                intro_text = "Your login code is below. Enter it to access your account."
            elif purpose == "email_capture":
                subject = "Your verification code"
                header_text = "Verify Your Email"
                intro_text = "Please enter the code below to verify your email address:"
            else:  # verification (signup)
                subject = "Verify your email for MyClone"
                header_text = "Welcome to MyClone!"
                intro_text = "Thanks for signing up! Please verify your email address by entering the code below:"

            # Email HTML content with MyClone brand colors
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 0; background-color: #FAFAFA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);">
                    <!-- Header with gradient -->
                    <div style="background: linear-gradient(to bottom right, #FFF4CC, #FFF8F2, #FFF4EB); padding: 40px 30px; text-align: center;">
                        <h1 style="margin: 0; font-size: 28px; color: #121212; font-weight: 600;">{header_text}</h1>
                    </div>

                    <!-- Content -->
                    <div style="padding: 40px 30px;">
                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 20px 0;">Hi {first_name},</p>

                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 30px 0;">
                            {intro_text}
                        </p>

                        <!-- OTP Code Box -->
                        <div style="background-color: #F3F4F6; border: 2px dashed #6366F1; border-radius: 8px; padding: 20px; text-align: center; margin: 30px 0;">
                            <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #6366F1; font-family: 'Courier New', monospace;">
                                {otp_code}
                            </div>
                        </div>

                        <!-- Info box -->
                        <div style="background-color: #FFF4CC; border-left: 4px solid #FFC329; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0;">
                                ⏰ <strong>This code expires in 5 minutes</strong><br>
                                You have 3 attempts to enter the correct code.
                            </p>
                        </div>

                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0;">
                            If you didn't request this code, you can safely ignore this email.
                        </p>
                    </div>

                    <!-- Footer -->
                    <div style="background-color: #FAFAFA; padding: 30px; text-align: center; border-top: 1px solid #E5E5E5;">
                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0;">
                            Best,<br>
                            <span style="color: #121212; font-weight: 600;">The MyClone Team</span>
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Plain text version
            plain_text = f"""Hi {first_name},

{intro_text}

Your verification code is: {otp_code}

This code expires in 5 minutes and you have 3 attempts to enter it correctly.

If you didn't request this code, you can safely ignore this email.

---
MyClone
This is an automated email. Please do not reply.
"""

            # Prepare email parameters - use custom sender if provided (whitelabel)
            sender = from_email or settings.resend_from_email
            params: resend.Emails.SendParams = {
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "text": plain_text,
            }

            # Run synchronous Resend SDK call in thread pool
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(
                f"✅ OTP email sent successfully to {to_email}: {email_response.get('id')}, from={sender}"
            )
            return True

        except Exception as e:
            # Capture exception in Sentry
            capture_exception_with_context(
                e,
                extra={
                    "to_email": to_email,
                    "fullname": fullname,
                    "purpose": purpose,
                },
                tags={
                    "component": "email",
                    "operation": "send_otp_email",
                    "email_type": "otp",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to send OTP email to {to_email}: {e}")
            return False

    def _send_email_sync(self, params: dict) -> dict:
        """
        Synchronous email sending function (to be run in thread pool)

        Args:
            params: Email parameters for Resend API

        Returns:
            Response from Resend API
        """
        return resend.Emails.send(params)
