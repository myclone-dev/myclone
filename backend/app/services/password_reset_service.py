"""
Password reset service for handling password reset flows

This service handles password reset token generation and email sending.
Tokens are stored in the auth_details table and expire after 1 hour.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import resend

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class PasswordResetService:
    """
    Service for password reset operations

    Handles:
    - Reset token generation (UUID-based)
    - Password reset email sending with links
    - Password changed confirmation emails
    - Token expiration (1 hour default)
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize password reset service

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
                "Resend API key not configured - password reset emails will not be sent"
            )

    def generate_reset_token(self) -> tuple[str, datetime]:
        """
        Generate a password reset token and expiration timestamp

        Returns:
            Tuple of (token, expiration_datetime)
            - token: UUID4 string (cryptographically secure)
            - expiration: Datetime when token expires (1 hour from now)

        Example:
            >>> service = PasswordResetService()
            >>> token, expires = service.generate_reset_token()
            >>> len(token) == 36  # UUID4 format
            True
        """
        # Generate cryptographically secure token
        token = str(uuid.uuid4())

        # Calculate expiration (1 hour from now, configurable)
        expiration = datetime.now(timezone.utc) + timedelta(
            hours=settings.password_reset_token_expiry_hours
        )

        self.logger.debug(f"Generated password reset token, expires at {expiration}")
        return (token, expiration)

    async def send_password_reset_email(
        self,
        to_email: str,
        fullname: str,
        reset_token: str,
    ) -> bool:
        """
        Send password reset email with link

        The reset link points to the frontend, which will extract the token
        and call the backend API to reset the password.

        Args:
            to_email: Recipient email address
            fullname: User's full name for personalization
            reset_token: Password reset token to include in link

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = PasswordResetService()
            >>> token, _ = service.generate_reset_token()
            >>> await service.send_password_reset_email("user@example.com", "John Doe", token)
            True
        """
        # Log API key status (masked for security)
        api_key_preview = f"{self.api_key[:8]}..." if self.api_key else "NOT_SET"
        self.logger.info(
            f"📧 [PASSWORD-RESET-EMAIL] Starting email send - API key: {api_key_preview}"
        )

        if not self.api_key:
            self.logger.error(
                "❌ [PASSWORD-RESET-EMAIL] CRITICAL: Resend API key not configured! Email cannot be sent."
            )
            return False

        try:
            # Extract first name for personalization
            first_name = fullname.split()[0] if fullname else "there"
            self.logger.info(
                f"📧 [PASSWORD-RESET-EMAIL] Preparing email for: {to_email} (name: {first_name})"
            )

            # Construct reset link (frontend URL)
            reset_link = f"{settings.frontend_url}/reset-password?token={reset_token}"
            self.logger.info(
                f"📧 [PASSWORD-RESET-EMAIL] Reset link: {settings.frontend_url}/reset-password?token={reset_token[:8]}..."
            )

            # Email HTML content with MyClone brand colors
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 0; background-color: #FAFAFA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);">
                    <!-- Header with gradient -->
                    <div style="background: linear-gradient(to bottom right, #FFF4CC, #FFF8F2, #FFF4EB); padding: 40px 30px; text-align: center;">
                        <h1 style="margin: 0; font-size: 28px; color: #121212; font-weight: 600;">Reset Your Password</h1>
                    </div>

                    <!-- Content -->
                    <div style="padding: 40px 30px;">
                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 20px 0;">Hi {first_name},</p>

                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 30px 0;">
                            We received a request to reset your MyClone account password. Click the button below to create a new password:
                        </p>

                        <!-- CTA Button -->
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="{reset_link}" style="background-color: #FFC329; color: #121212; padding: 14px 40px; text-decoration: none; border-radius: 8px; display: inline-block; font-size: 16px; font-weight: 600;">
                                Reset Password
                            </a>
                        </div>

                        <!-- Alternative link -->
                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0 0 10px 0;">
                            Or copy and paste this link into your browser:
                        </p>
                        <p style="font-size: 14px; line-height: 1.6; color: #B06B30; word-break: break-all; margin: 0 0 30px 0;">
                            {reset_link}
                        </p>

                        <!-- Info box -->
                        <div style="background-color: #FFF4CC; border-left: 4px solid #FFC329; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0;">
                                ⏰ This link will expire in {settings.password_reset_token_expiry_hours} hour(s).
                            </p>
                        </div>

                        <p style="font-size: 14px; line-height: 1.6; color: #737373; margin: 0;">
                            If you didn't request a password reset, please ignore this email and your password will remain unchanged.
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
                "subject": "Reset your MyClone password",
                "html": html_content,
            }

            self.logger.info(
                f"📧 [PASSWORD-RESET-EMAIL] Sending email via Resend API - From: {settings.resend_from_email}, To: {to_email}"
            )

            # Run synchronous Resend SDK call in thread pool
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            # Log the full response for debugging
            self.logger.info(f"📧 [PASSWORD-RESET-EMAIL] Resend API response: {email_response}")

            email_id = email_response.get("id")
            if email_id:
                self.logger.info(
                    f"✅ [PASSWORD-RESET-EMAIL] Email sent successfully to {to_email} - Resend ID: {email_id}"
                )
                return True
            else:
                self.logger.error(
                    f"❌ [PASSWORD-RESET-EMAIL] Resend API returned success but no email ID in response: {email_response}"
                )
                return False

        except Exception as e:
            # Log detailed error information
            self.logger.error(
                f"❌ [PASSWORD-RESET-EMAIL] EXCEPTION occurred while sending email to {to_email}"
            )
            self.logger.error(f"❌ [PASSWORD-RESET-EMAIL] Exception type: {type(e).__name__}")
            self.logger.error(f"❌ [PASSWORD-RESET-EMAIL] Exception message: {str(e)}")

            # Log the exception traceback for debugging
            import traceback

            self.logger.error(f"❌ [PASSWORD-RESET-EMAIL] Traceback:\n{traceback.format_exc()}")

            # Capture exception in Sentry
            capture_exception_with_context(
                e,
                extra={
                    "to_email": to_email,
                    "fullname": fullname,
                    "api_key_set": bool(self.api_key),
                    "from_email": settings.resend_from_email,
                    "frontend_url": settings.frontend_url,
                },
                tags={
                    "component": "email",
                    "operation": "send_password_reset_email",
                    "email_type": "password_reset",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            return False

    async def send_password_changed_email(
        self,
        to_email: str,
        fullname: str,
    ) -> bool:
        """
        Send password changed confirmation email

        This is sent after a successful password change/reset to notify the user.
        Security best practice to alert user of account changes.

        Args:
            to_email: Recipient email address
            fullname: User's full name for personalization

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = PasswordResetService()
            >>> await service.send_password_changed_email("user@example.com", "John Doe")
            True
        """
        if not self.api_key:
            self.logger.error("Cannot send password changed email - Resend API key not configured")
            return False

        try:
            # Extract first name for personalization
            first_name = fullname.split()[0] if fullname else "there"

            # Current timestamp for email
            now = datetime.now(timezone.utc)
            timestamp_str = now.strftime("%B %d, %Y at %I:%M %p UTC")

            # Email HTML content with MyClone brand colors
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 0; background-color: #FAFAFA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);">
                    <!-- Header with gradient -->
                    <div style="background: linear-gradient(to bottom right, #FFF4CC, #FFF8F2, #FFF4EB); padding: 40px 30px; text-align: center;">
                        <h1 style="margin: 0; font-size: 28px; color: #121212; font-weight: 600;">Password Changed</h1>
                    </div>

                    <!-- Content -->
                    <div style="padding: 40px 30px;">
                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 20px 0;">Hi {first_name},</p>

                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 30px 0;">
                            This email confirms that your MyClone account password was successfully changed on {timestamp_str}.
                        </p>

                        <!-- Warning box -->
                        <div style="background-color: #FFF4EB; border-left: 4px solid #FF6B6B; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0 0 10px 0;">
                                <strong>⚠️ If you didn't make this change</strong>
                            </p>
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0;">
                                Please contact our support team immediately at <a href="mailto:{settings.support_email}" style="color: #B06B30; text-decoration: none; font-weight: 600;">{settings.support_email}</a>
                            </p>
                        </div>

                        <!-- Info box -->
                        <div style="background-color: #FFF4CC; border-left: 4px solid #FFC329; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0 0 10px 0;">
                                <strong>For your security, we recommend:</strong>
                            </p>
                            <ul style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0; padding-left: 20px;">
                                <li>Using a unique password for each online account</li>
                                <li>Never sharing your password with anyone</li>
                                <li>Changing your password regularly</li>
                            </ul>
                        </div>
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
                "subject": "Your MyClone password was changed",
                "html": html_content,
            }

            # Run synchronous Resend SDK call in thread pool
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(
                f"✅ Password changed confirmation email sent successfully to {to_email}: {email_response.get('id')}"
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
                    "operation": "send_password_changed_email",
                    "email_type": "password_changed",
                    "severity": "low",  # Low severity - confirmation email failure doesn't break flow
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to send password changed email to {to_email}: {e}")
            return False

    async def send_password_set_confirmation_email(
        self,
        to_email: str,
        fullname: str,
    ) -> bool:
        """
        Send confirmation email when OAuth user adds password authentication

        This is sent after an OAuth user successfully sets a password for the first time,
        enabling them to login with email/password in addition to OAuth.

        Args:
            to_email: Recipient email address
            fullname: User's full name for personalization

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = PasswordResetService()
            >>> await service.send_password_set_confirmation_email("user@example.com", "John Doe")
            True
        """
        if not self.api_key:
            self.logger.error(
                "Cannot send password set confirmation email - Resend API key not configured"
            )
            return False

        try:
            # Extract first name for personalization
            first_name = fullname.split()[0] if fullname else "there"

            # Current timestamp for email
            now = datetime.now(timezone.utc)
            timestamp_str = now.strftime("%B %d, %Y at %I:%M %p UTC")

            # Email HTML content with MyClone brand colors
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 0; background-color: #FAFAFA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);">
                    <!-- Header with gradient -->
                    <div style="background: linear-gradient(to bottom right, #FFF4CC, #FFF8F2, #FFF4EB); padding: 40px 30px; text-align: center;">
                        <h1 style="margin: 0; font-size: 28px; color: #121212; font-weight: 600;">Password Authentication Added</h1>
                    </div>

                    <!-- Content -->
                    <div style="padding: 40px 30px;">
                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 20px 0;">Hi {first_name},</p>

                        <p style="font-size: 16px; line-height: 1.6; color: #121212; margin: 0 0 30px 0;">
                            Great news! You've successfully added password authentication to your MyClone account on {timestamp_str}.
                        </p>

                        <!-- Success box -->
                        <div style="background-color: #F0FDF4; border-left: 4px solid #10B981; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0 0 10px 0;">
                                <strong>✅ What this means for you:</strong>
                            </p>
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0 0 5px 0;">
                                You can now sign in to MyClone using either:
                            </p>
                            <ul style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0; padding-left: 20px;">
                                <li>Your existing OAuth provider (LinkedIn, Google, etc.)</li>
                                <li>Your email address and the password you just set</li>
                            </ul>
                        </div>

                        <!-- Warning box -->
                        <div style="background-color: #FFF4EB; border-left: 4px solid #FF6B6B; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0 0 10px 0;">
                                <strong>⚠️ If you didn't make this change</strong>
                            </p>
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0;">
                                Please contact our support team immediately at <a href="mailto:{settings.support_email}" style="color: #B06B30; text-decoration: none; font-weight: 600;">{settings.support_email}</a>
                            </p>
                        </div>

                        <!-- Info box -->
                        <div style="background-color: #FFF4CC; border-left: 4px solid #FFC329; padding: 16px; border-radius: 4px; margin: 30px 0;">
                            <p style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0 0 10px 0;">
                                <strong>For your security, we recommend:</strong>
                            </p>
                            <ul style="font-size: 14px; line-height: 1.6; color: #121212; margin: 0; padding-left: 20px;">
                                <li>Using a unique password for each online account</li>
                                <li>Never sharing your password with anyone</li>
                                <li>Changing your password regularly</li>
                            </ul>
                        </div>
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
                "subject": "Password authentication added to your MyClone account",
                "html": html_content,
            }

            # Run synchronous Resend SDK call in thread pool
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(
                f"✅ Password set confirmation email sent successfully to {to_email}: {email_response.get('id')}"
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
                    "operation": "send_password_set_confirmation_email",
                    "email_type": "password_set",
                    "severity": "low",
                    "user_facing": "false",
                },
            )
            self.logger.error(
                f"❌ Failed to send password set confirmation email to {to_email}: {e}"
            )
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
