"""Slack notification service for sending alerts and notifications."""

import logging
from datetime import datetime
from typing import Any

import httpx

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class SlackService:
    """Service for sending Slack notifications via webhooks."""

    def __init__(self, webhook_url: str | None = None):
        """
        Initialize Slack service.

        Args:
            webhook_url: Slack webhook URL (defaults to settings.slack_webhook_url)
        """
        self.webhook_url = webhook_url or settings.slack_webhook_url
        self.logger = logging.getLogger(__name__)

    async def send_notification(self, message: dict[str, Any]) -> bool:
        """
        Send a notification to Slack.

        Args:
            message: Slack message payload (must conform to Slack's message format)

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            self.logger.warning("Slack webhook URL not configured, skipping notification")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=message,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                self.logger.info("Slack notification sent successfully")
                return True

        except httpx.HTTPError as e:
            capture_exception_with_context(
                e,
                extra={
                    "webhook_url": self.webhook_url[:50] + "...",  # Truncate for security
                    "message": str(message)[:200],  # Truncate to avoid large logs
                },
                tags={
                    "component": "slack",
                    "operation": "send_notification",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def send_onboarding_notification(
        self,
        user_id: str,
        user_name: str,
        user_email: str,
        persona_name: str,
        persona_username: str,
        linkedin_url: str | None = None,
        twitter_url: str | None = None,
        website_url: str | None = None,
    ) -> bool:
        """
        Send user onboarding notification to Slack.

        Args:
            user_id: User ID
            user_name: User's full name
            user_email: User's email address
            persona_name: Persona name
            persona_username: Persona username
            linkedin_url: LinkedIn profile URL (optional)
            twitter_url: Twitter profile URL (optional)
            website_url: Website URL (optional)

        Returns:
            True if successful, False otherwise
        """
        # Build data sources text
        data_sources = []
        if linkedin_url:
            data_sources.append(f"• LinkedIn: {linkedin_url}")
        if twitter_url:
            data_sources.append(f"• Twitter: {twitter_url}")
        if website_url:
            data_sources.append(f"• Website: {website_url}")

        data_sources_text = "\n".join(data_sources) if data_sources else "No data sources added yet"

        # Build persona profile link
        persona_profile_url = f"{settings.frontend_url}/{persona_username}"

        # Create Slack message with rich formatting
        message = {
            "text": f"🎉 New User Onboarded: {user_name}",
            "attachments": [
                {
                    "color": "#36a64f",  # Green color
                    "title": f"Profile: {persona_name} (@{persona_username})",
                    "title_link": persona_profile_url,
                    "fields": [
                        {
                            "title": "User Name",
                            "value": user_name,
                            "short": True,
                        },
                        {
                            "title": "Email",
                            "value": user_email,
                            "short": True,
                        },
                        {
                            "title": "User ID",
                            "value": user_id,
                            "short": True,
                        },
                        {
                            "title": "Persona Username",
                            "value": f"@{persona_username}",
                            "short": True,
                        },
                        {
                            "title": "Data Sources",
                            "value": data_sources_text,
                            "short": False,
                        },
                        {
                            "title": "Profile URL",
                            "value": f"<{persona_profile_url}|View Profile>",
                            "short": False,
                        },
                    ],
                    "footer": "MyClone Onboarding",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        return await self.send_notification(message)

    async def send_bulk_onboarding_notification(
        self,
        job_id: str,
        total_personas: int,
        successful: int,
        failed: int,
        started_by: str,
    ) -> bool:
        """
        Send bulk onboarding completion notification to Slack.

        Args:
            job_id: Bulk job ID
            total_personas: Total personas in the job
            successful: Number of successful onboardings
            failed: Number of failed onboardings
            started_by: User who initiated the bulk job

        Returns:
            True if successful, False otherwise
        """
        # Determine color based on success rate
        success_rate = (successful / total_personas * 100) if total_personas > 0 else 0
        if success_rate == 100:
            color = "#36a64f"  # Green
        elif success_rate >= 75:
            color = "#ff9900"  # Orange
        else:
            color = "#ff0000"  # Red

        message = {
            "text": f"📊 Bulk Onboarding Completed - Job {job_id[:8]}",
            "attachments": [
                {
                    "color": color,
                    "title": "Bulk Onboarding Summary",
                    "fields": [
                        {
                            "title": "Job ID",
                            "value": job_id,
                            "short": True,
                        },
                        {
                            "title": "Started By",
                            "value": started_by,
                            "short": True,
                        },
                        {
                            "title": "Total Personas",
                            "value": str(total_personas),
                            "short": True,
                        },
                        {
                            "title": "Success Rate",
                            "value": f"{success_rate:.1f}%",
                            "short": True,
                        },
                        {
                            "title": "✅ Successful",
                            "value": str(successful),
                            "short": True,
                        },
                        {
                            "title": "❌ Failed",
                            "value": str(failed),
                            "short": True,
                        },
                    ],
                    "footer": "MyClone Bulk Onboarding",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        return await self.send_notification(message)

    async def send_error_notification(
        self,
        error_type: str,
        error_message: str,
        user_id: str | None = None,
        persona_username: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Send error notification to Slack.

        Args:
            error_type: Type of error (e.g., "Ingestion Failed", "Email Send Failed")
            error_message: Error message
            user_id: User ID (optional)
            persona_username: Persona username (optional)
            additional_context: Additional context dict (optional)

        Returns:
            True if successful, False otherwise
        """
        fields = [
            {
                "title": "Error Type",
                "value": error_type,
                "short": True,
            },
            {
                "title": "Time",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "short": True,
            },
            {
                "title": "Error Message",
                "value": error_message[:500],  # Truncate long messages
                "short": False,
            },
        ]

        if user_id:
            fields.append(
                {
                    "title": "User ID",
                    "value": user_id,
                    "short": True,
                }
            )

        if persona_username:
            fields.append(
                {
                    "title": "Persona",
                    "value": f"@{persona_username}",
                    "short": True,
                }
            )

        if additional_context:
            for key, value in additional_context.items():
                fields.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": str(value)[:200],  # Truncate
                        "short": True,
                    }
                )

        message = {
            "text": f"⚠️ Error Alert: {error_type}",
            "attachments": [
                {
                    "color": "#ff0000",  # Red color
                    "title": "Error Details",
                    "fields": fields,
                    "footer": "MyClone Error Monitoring",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        return await self.send_notification(message)
