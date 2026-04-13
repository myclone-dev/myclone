"""
Email service for sending onboarding and transactional emails via Resend

This service handles email delivery using the Resend API with proper async handling.
The Resend SDK is synchronous, so we use asyncio.to_thread() to run it in a thread pool
and avoid blocking the event loop.
"""

import asyncio
import html
import logging

import resend

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails via Resend API

    Unlike LinkedInOAuthService (which is stateless utility), this service maintains
    state (initialized API key) similar to ElevenLabsService pattern.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize email service with Resend API key

        Args:
            api_key: Resend API key (defaults to settings.resend_api_key)

        Note: Resend SDK uses module-level state (resend.api_key), so we set it once
        during initialization rather than on every send.
        """
        self.api_key = api_key or settings.resend_api_key
        self.logger = logging.getLogger(__name__)

        # Initialize Resend SDK with API key (sets module-level state)
        if self.api_key:
            resend.api_key = self.api_key
        else:
            self.logger.warning("Resend API key not configured - emails will not be sent")

    def _send_email_sync(self, params: dict) -> dict:
        """
        Synchronous email sending function (to be run in thread pool)

        This is a separate sync function that will be executed in a thread pool
        to avoid blocking the async event loop.

        Args:
            params: Email parameters for Resend API

        Returns:
            Response from Resend API
        """
        return resend.Emails.send(params)

    async def send_onboarding_email(
        self,
        to_email: str,
        fullname: str,
    ) -> bool:
        """
        Send a simple, personalized onboarding email to new users

        This email:
        - Uses plain HTML (no templates)
        - Feels like a personal message from the founder
        - Includes product info and contact details
        - Has a simple, clean design

        Args:
            to_email: Recipient email address
            fullname: User's full name for personalization

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.api_key:
            self.logger.error("Cannot send email - Resend API key not configured")
            return False

        try:
            # Extract first name for personalization
            first_name = fullname.split()[0] if fullname else "there"

            # Simple, personalized HTML email (no template)
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
                <p style="font-size: 16px; line-height: 1.6;">Hi {first_name},</p>

                <p style="font-size: 16px; line-height: 1.6;">
                    Welcome to {settings.project_name}! Thanks for signing up.
                </p>

                <p style="font-size: 16px; line-height: 1.6;">
                    {settings.project_name} lets you create AI-powered digital personas that can chat and interact on your behalf. Whether you want to automate responses, share your knowledge, or create an AI version of yourself - we've got you covered.
                </p>

                <p style="font-size: 16px; line-height: 1.6;">
                    If you have any questions or need help getting started, feel free to reach out anytime.
                </p>

                <p style="font-size: 16px; line-height: 1.6; margin-top: 30px;">
                    Best,<br>
                    The {settings.project_name} Team
                </p>
            </div>
            """

            # Prepare email parameters
            params: resend.Emails.SendParams = {
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": f"Welcome to {settings.project_name}!",
                "html": html_content,
            }

            # Run synchronous Resend SDK call in thread pool to avoid blocking event loop
            # This is the same pattern used by other async Python libraries (like httpx)
            # when they need to wrap synchronous operations
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(
                f"✅ Onboarding email sent successfully to {to_email}: {email_response.get('id')}"
            )
            return True

        except Exception as e:
            # Capture exception in Sentry with context
            capture_exception_with_context(
                e,
                extra={
                    "to_email": to_email,  # Email address (PII in extra, not tag)
                    "fullname": fullname,
                },
                tags={
                    "component": "email",
                    "operation": "send_onboarding_email",
                    "email_type": "onboarding",
                    "severity": "medium",  # Medium severity - email failure doesn't block auth
                    "user_facing": "false",  # Backend issue, not user-facing error
                },
            )
            self.logger.error(f"❌ Failed to send onboarding email to {to_email}: {e}")
            return False

    async def send_individual_conversation_email(
        self,
        to_email: str,
        user_name: str,
        persona_name: str,
        conversation_id: str,
        messages: list,
        ai_summary: str | None = None,
        username: str | None = None,
        persona_url_name: str | None = None,
        from_email: str | None = None,
    ) -> bool:
        """
        Send email about a single conversation with preview of first 5 turns

        This email notifies users immediately after a meaningful conversation ends,
        showing them what was discussed and encouraging them to view the full conversation.

        Args:
            to_email: User's email address
            user_name: User's name for personalization
            persona_name: Display name of the persona that had the conversation
            conversation_id: UUID of the conversation
            messages: List of message dicts from the conversation
            ai_summary: Optional AI-generated summary of key topics
            username: User's username for persona link (optional)
            persona_url_name: Persona's URL-friendly name for link (optional)
            from_email: Optional custom sender email (for whitelabel). Defaults to settings.resend_from_email

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.api_key:
            self.logger.error("Cannot send email - Resend API key not configured")
            return False

        try:
            # HTML escape all user-controlled content for XSS prevention
            persona_name_escaped = html.escape(persona_name)
            user_name_escaped = html.escape(user_name)
            username_escaped = html.escape(username) if username else None
            persona_url_name_escaped = html.escape(persona_url_name) if persona_url_name else None

            # Extract first name
            first_name = user_name_escaped.split()[0] if user_name_escaped else "there"

            # Build conversation preview (first 5 messages) - already escapes content internally
            preview_html = self._build_conversation_preview(
                messages, persona_name_escaped, max_turns=5
            )

            # Calculate remaining messages
            total_messages = len(messages)
            preview_count = min(5, total_messages)
            remaining = total_messages - preview_count

            # Subject line (escaped for safety)
            subject = f"New conversation with your persona {persona_name_escaped}!"

            # Build summary section if provided (with improved UI and XSS protection)
            # Note: We sanitize but preserve apostrophes for readability
            summary_html = ""
            if ai_summary:
                # Sanitize for XSS but keep apostrophes readable
                ai_summary_sanitized = (
                    ai_summary.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                )
                # Convert newlines to <br> for proper formatting
                ai_summary_sanitized = ai_summary_sanitized.replace("\n", "<br>")

                # Dark mode compatible: Use explicit colors that won't be inverted
                # White background with dark text, inline styles for email client compatibility
                summary_html = f"""
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 25px 0;">
                    <tr>
                        <td style="background-color: #FFFBEB; border-left: 4px solid #FFC329; border-radius: 10px; padding: 20px;">
                            <h3 style="color: #1F2937 !important; margin: 0 0 12px 0; font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">📌 Key Topics Discussed</h3>
                            <p style="margin: 0; color: #374151 !important; font-size: 15px; line-height: 1.7;">{ai_summary_sanitized}</p>
                        </td>
                    </tr>
                </table>
                """

            # Build persona link if username and persona_url_name are provided
            # Validate parameters first
            persona_link = ""
            if username_escaped and persona_url_name_escaped:
                persona_link = f'<a href="{settings.frontend_url}/{username_escaped}/{persona_url_name_escaped}" style="color: #FFC329; text-decoration: none; font-weight: 600;">{persona_name_escaped}</a>'
                self.logger.info(
                    f"✅ Built persona link: {settings.frontend_url}/{username_escaped}/{persona_url_name_escaped}"
                )
            else:
                persona_link = f'<strong style="color: #FFC329;">{persona_name_escaped}</strong>'
                self.logger.warning(
                    f"⚠️ Persona link not created - username: {username}, persona_url_name: {persona_url_name}"
                )

            # Email HTML with improved brand colors and UI
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px 20px;">
                <!-- Header without background -->
                <h2 style="color: #121212; margin: 0 0 20px 0; font-size: 24px; font-weight: 700;">New Conversation Alert! 🎉</h2>

                <p style="font-size: 16px; line-height: 1.6; color: #334155; margin-top: 0;">Hi {first_name},</p>

                <p style="font-size: 16px; line-height: 1.6; color: #334155;">
                    Great news! Someone just had a meaningful <strong style="color: #121212;">{total_messages}-message conversation</strong> with your persona {persona_link}.
                </p>

                <h3 style="color: #121212; margin-top: 30px; margin-bottom: 15px; font-size: 18px; font-weight: 600;">Conversation Preview:</h3>
                <div style="background-color: #F8FAFC; padding: 20px; border-radius: 10px; margin: 15px 0; border: 2px solid #E2E8F0;">
                    {preview_html}
                    {f'<p style="color: #64748B; font-style: italic; margin-top: 15px; padding-top: 15px; border-top: 2px dashed #E2E8F0; text-align: center;">+ {remaining} more message{"s" if remaining != 1 else ""} in this conversation...</p>' if remaining > 0 else ''}
                </div>

                {summary_html}

                <!-- CTA Button -->
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{settings.frontend_url}/dashboard/conversations/{conversation_id}"
                       style="display: inline-block; background-color: #FFC329; color: #121212; padding: 16px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(255, 195, 41, 0.25);">
                        View Full Conversation →
                    </a>
                </div>

                <p style="font-size: 15px; line-height: 1.6; color: #334155; background-color: #F8FAFC; padding: 15px; border-radius: 8px; border-left: 4px solid #FFC329;">
                    💡 <strong style="color: #121212;">Pro tip:</strong> Visit your <a href="{settings.frontend_url}/dashboard" style="color: #FFC329; text-decoration: none; font-weight: 600;">dashboard</a> to improve your persona's responses and add more knowledge.
                </p>

                <!-- Footer -->
                <div style="margin-top: 40px; padding-top: 25px; border-top: 2px solid #E2E8F0;">
                    <p style="font-size: 16px; line-height: 1.8; margin-bottom: 10px; color: #121212;">
                        Best,<br>
                        <strong style="font-size: 17px;">The {settings.project_name} Team</strong>
                    </p>
                </div>

                <p style="font-size: 13px; line-height: 1.5; color: #94A3B8; margin-top: 30px; padding: 15px; background-color: #F8FAFC; border-radius: 6px;">
                    You're receiving this email because someone had a meaningful conversation with your persona. You can adjust your notification settings in your <a href="{settings.frontend_url}/dashboard/settings" style="color: #64748B; text-decoration: underline;">dashboard settings</a>.
                </p>
            </div>
            """

            # Prepare email parameters
            # Use custom from_email if provided (whitelabel), otherwise default
            sender = from_email or settings.resend_from_email
            params: resend.Emails.SendParams = {
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            # Send email
            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(f"📧 Sending conversation email from: {sender}")

            self.logger.info(
                f"✅ Individual conversation email sent to {to_email}: {email_response.get('id')} "
                f"(conversation: {conversation_id}, {total_messages} messages)"
            )
            return True

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "to_email": to_email,
                    "conversation_id": conversation_id,
                    "message_count": len(messages),
                },
                tags={
                    "component": "email",
                    "operation": "send_individual_conversation_email",
                    "email_type": "individual_conversation",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to send individual conversation email to {to_email}: {e}")
            return False

    async def send_structured_conversation_email(
        self,
        to_email: str,
        user_name: str,
        persona_name: str,
        conversation_id: str,
        structured_summary: dict,
        visitor_info: dict,
        conversation_type: str = "voice",
        message_count: int = 0,
        username: str | None = None,
        persona_url_name: str | None = None,
        from_email: str | None = None,
    ) -> bool:
        """
        Send a concise, structured conversation summary email.

        This email format is optimized for quick follow-up with:
        - Synopsis: Brief overview
        - Key Details: Visitor intent and requirements
        - Q&A Highlights: Important questions and answers
        - Follow-up: Urgency and next steps
        - Visitor Contact: Email, phone if provided

        Args:
            to_email: User's email address
            user_name: User's name for personalization
            persona_name: Display name of the persona
            conversation_id: UUID of the conversation
            structured_summary: Dict with synopsis, key_details, questions_answers, follow_up
            visitor_info: Dict with visitor's fullname, email, phone
            conversation_type: "voice" or "text"
            message_count: Total number of messages in conversation
            username: User's username for persona link
            persona_url_name: Persona's URL-friendly name
            from_email: Optional custom sender email (whitelabel)

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.api_key:
            self.logger.error("Cannot send email - Resend API key not configured")
            return False

        try:
            # HTML escape all user-controlled content
            persona_name_escaped = html.escape(persona_name)
            conv_type_label = "voice call" if conversation_type == "voice" else "chat"

            # Build visitor contact section
            visitor_html = self._build_visitor_contact_html(visitor_info)

            # Build structured summary sections
            synopsis = html.escape(structured_summary.get("synopsis", "No summary available."))

            # Key details section
            key_details_html = self._build_key_details_html(
                structured_summary.get("key_details", {})
            )

            # Q&A section
            qa_html = self._build_qa_html(structured_summary.get("questions_answers", []))

            # Follow-up section
            follow_up_html = self._build_follow_up_html(structured_summary.get("follow_up", {}))

            # Key topics as tags
            key_topics = structured_summary.get("key_topics", [])
            topics_html = ""
            if key_topics:
                topic_tags = " ".join(
                    [
                        f'<span style="display: inline-block; background-color: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 12px; font-size: 12px; margin: 2px;">{html.escape(str(topic))}</span>'
                        for topic in key_topics[:5]
                    ]
                )
                topics_html = f"""
                <div style="margin-bottom: 20px;">
                    {topic_tags}
                </div>
                """

            # Subject line
            subject = f"Conversation Summary: {persona_name_escaped}"

            # Build the email HTML
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px 20px;">

                <!-- Header -->
                <h2 style="color: #121212; margin: 0 0 8px 0; font-size: 22px; font-weight: 700;">New {conv_type_label} with {persona_name_escaped}</h2>
                <p style="color: #64748B; margin: 0 0 20px 0; font-size: 14px;">{message_count} messages</p>

                {topics_html}

                <!-- Visitor Contact Card (if available) -->
                {visitor_html}

                <!-- Synopsis -->
                <div style="background-color: #F8FAFC; border-left: 4px solid #FFC329; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-bottom: 24px;">
                    <h3 style="color: #121212; margin: 0 0 8px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Summary</h3>
                    <p style="color: #334155; margin: 0; font-size: 15px; line-height: 1.6;">{synopsis}</p>
                </div>

                {key_details_html}

                {qa_html}

                {follow_up_html}

                <!-- CTA Button -->
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{settings.frontend_url}/dashboard/conversations/{conversation_id}"
                       style="display: inline-block; background-color: #FFC329; color: #121212; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
                        View Full Conversation →
                    </a>
                </div>

                <!-- Footer -->
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E2E8F0;">
                    <p style="font-size: 13px; color: #94A3B8; margin: 0;">
                        This summary was generated by AI. <a href="{settings.frontend_url}/dashboard/conversations/{conversation_id}" style="color: #64748B;">View the full conversation</a> for complete context.
                    </p>
                </div>
            </div>
            """

            # Send email
            sender = from_email or settings.resend_from_email
            params: resend.Emails.SendParams = {
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            email_response = await asyncio.to_thread(self._send_email_sync, params)

            self.logger.info(
                f"✅ Structured conversation email sent to {to_email}: {email_response.get('id')} "
                f"(conversation: {conversation_id})"
            )
            return True

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "to_email": to_email,
                    "conversation_id": conversation_id,
                },
                tags={
                    "component": "email",
                    "operation": "send_structured_conversation_email",
                    "email_type": "structured_conversation",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to send structured conversation email: {e}")
            return False

    def _build_visitor_contact_html(self, visitor_info: dict) -> str:
        """Build visitor contact card HTML"""
        if not visitor_info:
            return ""

        fullname = visitor_info.get("fullname")
        email = visitor_info.get("email")
        phone = visitor_info.get("phone")

        # Only show if we have at least one piece of contact info
        if not any([fullname, email, phone]):
            return """
            <div style="background-color: #F1F5F9; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
                <p style="color: #64748B; margin: 0; font-size: 14px;">
                    ℹ️ Visitor did not provide contact information
                </p>
            </div>
            """

        contact_lines = []
        if fullname:
            contact_lines.append(
                f'<span style="font-weight: 600; color: #121212;">{html.escape(fullname)}</span>'
            )
        if email:
            contact_lines.append(
                f'<a href="mailto:{html.escape(email)}" style="color: #2563EB; text-decoration: none;">{html.escape(email)}</a>'
            )
        if phone:
            contact_lines.append(
                f'<a href="tel:{html.escape(phone)}" style="color: #2563EB; text-decoration: none;">{html.escape(phone)}</a>'
            )

        return f"""
        <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
            <h3 style="color: #065F46; margin: 0 0 8px 0; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">👤 Visitor Contact</h3>
            <p style="color: #334155; margin: 0; font-size: 15px; line-height: 1.8;">
                {" · ".join(contact_lines)}
            </p>
        </div>
        """

    def _build_key_details_html(self, key_details: dict) -> str:
        """Build key details section HTML"""
        if not key_details:
            return ""

        visitor_intent = key_details.get("visitor_intent")
        requirements = key_details.get("requirements", [])
        context_shared = key_details.get("context_shared", [])

        if not any([visitor_intent, requirements, context_shared]):
            return ""

        details_html = ""

        if visitor_intent:
            details_html += f"""
            <div style="margin-bottom: 12px;">
                <span style="color: #64748B; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">What they wanted:</span>
                <p style="color: #334155; margin: 4px 0 0 0; font-size: 14px;">{html.escape(str(visitor_intent))}</p>
            </div>
            """

        if requirements and len(requirements) > 0:
            req_list = "".join(
                [
                    f"<li style='margin-bottom: 4px;'>{html.escape(str(r))}</li>"
                    for r in requirements[:4]
                ]
            )
            details_html += f"""
            <div style="margin-bottom: 12px;">
                <span style="color: #64748B; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Requirements mentioned:</span>
                <ul style="color: #334155; margin: 4px 0 0 0; padding-left: 20px; font-size: 14px;">{req_list}</ul>
            </div>
            """

        if context_shared and len(context_shared) > 0:
            ctx_list = "".join(
                [
                    f"<li style='margin-bottom: 4px;'>{html.escape(str(c))}</li>"
                    for c in context_shared[:3]
                ]
            )
            details_html += f"""
            <div style="margin-bottom: 12px;">
                <span style="color: #64748B; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Background shared:</span>
                <ul style="color: #334155; margin: 4px 0 0 0; padding-left: 20px; font-size: 14px;">{ctx_list}</ul>
            </div>
            """

        if not details_html:
            return ""

        return f"""
        <div style="background-color: #FAFAFA; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
            <h3 style="color: #121212; margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">📋 Key Details</h3>
            {details_html}
        </div>
        """

    def _build_qa_html(self, questions_answers: list) -> str:
        """Build Q&A section HTML"""
        if not questions_answers or len(questions_answers) == 0:
            return ""

        qa_items = ""
        for qa in questions_answers[:4]:  # Limit to 4 Q&A pairs
            q = html.escape(str(qa.get("question", "")))
            a = html.escape(str(qa.get("answer", "")))
            if q and a:
                qa_items += f"""
                <div style="margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #E2E8F0;">
                    <p style="color: #1E40AF; margin: 0 0 6px 0; font-size: 14px; font-weight: 600;">Q: {q}</p>
                    <p style="color: #334155; margin: 0; font-size: 14px; line-height: 1.5;">A: {a}</p>
                </div>
                """

        if not qa_items:
            return ""

        return f"""
        <div style="margin-bottom: 24px;">
            <h3 style="color: #121212; margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">💬 Questions & Answers</h3>
            {qa_items}
        </div>
        """

    def _build_follow_up_html(self, follow_up: dict) -> str:
        """Build follow-up section HTML"""
        if not follow_up:
            return ""

        urgency = follow_up.get("urgency", "").lower()
        next_steps = follow_up.get("next_steps", [])
        notes = follow_up.get("notes")

        if not any([urgency, next_steps, notes]):
            return ""

        # Urgency badge colors
        urgency_colors = {
            "high": ("🔴", "#FEE2E2", "#991B1B"),
            "medium": ("🟡", "#FEF3C7", "#92400E"),
            "low": ("🟢", "#D1FAE5", "#065F46"),
        }
        urgency_icon, urgency_bg, urgency_text = urgency_colors.get(
            urgency, ("⚪", "#F1F5F9", "#64748B")
        )

        follow_up_html = ""

        if urgency:
            follow_up_html += f"""
            <div style="display: inline-block; background-color: {urgency_bg}; color: {urgency_text}; padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; margin-bottom: 12px;">
                {urgency_icon} {urgency.upper()} priority
            </div>
            """

        if next_steps and len(next_steps) > 0:
            steps_list = "".join(
                [
                    f"<li style='margin-bottom: 4px;'>{html.escape(str(s))}</li>"
                    for s in next_steps[:3]
                ]
            )
            follow_up_html += f"""
            <div style="margin-top: 8px;">
                <span style="color: #64748B; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Suggested next steps:</span>
                <ul style="color: #334155; margin: 4px 0 0 0; padding-left: 20px; font-size: 14px;">{steps_list}</ul>
            </div>
            """

        if notes:
            follow_up_html += f"""
            <div style="margin-top: 12px; padding: 12px; background-color: #FFFBEB; border-radius: 6px;">
                <p style="color: #92400E; margin: 0; font-size: 14px;">💡 {html.escape(str(notes))}</p>
            </div>
            """

        if not follow_up_html:
            return ""

        return f"""
        <div style="background-color: #F8FAFC; padding: 16px; border-radius: 8px; margin-bottom: 24px; border: 1px solid #E2E8F0;">
            <h3 style="color: #121212; margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">🎯 Follow-up</h3>
            {follow_up_html}
        </div>
        """

    def _build_conversation_preview(
        self, messages: list, persona_name: str, max_turns: int = 5
    ) -> str:
        """
        Build HTML preview of conversation messages with chat bubble style

        Layout:
        - Visitor messages: Left-aligned, light background
        - Persona messages: Right-aligned, dark background

        Args:
            messages: List of message dicts with 'role' and 'content'
            persona_name: Name of the persona
            max_turns: Maximum number of messages to include

        Returns:
            HTML string of conversation preview
        """
        preview_html = ""
        for i, msg in enumerate(messages[:max_turns]):
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "unknown")
            content = msg.get("content") or msg.get("text", "")

            # Truncate very long messages
            if len(content) > 300:
                content = content[:300] + "..."

            # First, decode any existing HTML entities (content may already be encoded)
            # This handles cases like &#x27; -> ' and &amp; -> &
            content = html.unescape(content)

            # Then sanitize for XSS but preserve apostrophes for readability
            # Only escape dangerous characters, keep ' as is
            content = (
                content.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

            # Chat bubble style: Visitor left, Persona right
            if role == "user":
                speaker = "Visitor"
                # Left-aligned visitor bubble - light gray background
                preview_html += f"""
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 12px;">
                    <tr>
                        <td width="85%" style="vertical-align: top;">
                            <div style="background-color: #F3F4F6; border-radius: 12px 12px 12px 0; padding: 14px 16px;">
                                <p style="margin: 0; font-weight: 600; color: #6B7280 !important; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">{speaker}</p>
                                <p style="margin: 8px 0 0 0; color: #1F2937 !important; font-size: 15px; line-height: 1.6;">{content}</p>
                            </div>
                        </td>
                        <td width="15%"></td>
                    </tr>
                </table>
                """
            elif role == "assistant":
                speaker = persona_name
                # Right-aligned persona bubble - dark slate background with yellow accent
                preview_html += f"""
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 12px;">
                    <tr>
                        <td width="15%"></td>
                        <td width="85%" style="vertical-align: top;">
                            <div style="background-color: #1E293B; border-radius: 12px 12px 0 12px; padding: 14px 16px; border-left: 3px solid #FFC329;">
                                <p style="margin: 0; font-weight: 600; color: #FFC329 !important; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">{speaker}</p>
                                <p style="margin: 8px 0 0 0; color: #F1F5F9 !important; font-size: 15px; line-height: 1.6;">{content}</p>
                            </div>
                        </td>
                    </tr>
                </table>
                """
            else:
                speaker = role.title()
                # Center-aligned system message
                preview_html += f"""
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 12px;">
                    <tr>
                        <td style="text-align: center;">
                            <div style="background-color: #F8FAFC; border-radius: 8px; padding: 10px 16px; display: inline-block;">
                                <p style="margin: 0; color: #64748B !important; font-size: 14px; line-height: 1.5;">{content}</p>
                            </div>
                        </td>
                    </tr>
                </table>
                """

        return preview_html
