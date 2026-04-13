"""
Conversation Summary Email Service - Sends conversation summaries via email

This service handles:
1. Generating AI summaries for voice and text conversations
2. Sending summary emails to persona owners with visitor details
3. Running asynchronously to not block agent shutdown
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.conversation_summary_service import ConversationSummaryService
from app.services.custom_email_domain_service import CustomEmailDomainService
from app.services.email_service import EmailService
from shared.database.models.database import Conversation, Persona, async_session_maker
from shared.database.models.user import User
from shared.database.models.user_session import UserSession
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class ConversationSummaryEmailService:
    """Service for sending conversation summaries to persona owners via email"""

    def __init__(self):
        self.email_service = EmailService()
        self.summary_service = ConversationSummaryService()
        self.custom_email_domain_service = CustomEmailDomainService()
        self.logger = logging.getLogger(__name__)

    async def send_conversation_summary(
        self,
        persona_id: UUID,
        session_id: str,
        min_message_count: int = 3,
        conversation_type: str = "voice",
    ) -> bool:
        """
        Send conversation summary email to persona owner

        This method:
        1. Finds the conversation by persona_id, session_id, and type (voice or text)
        2. Skips if conversation is too short (< min_message_count messages)
        3. Generates structured AI summary of the conversation
        4. Stores summary in database for caching
        5. Sends concise email with structured summary and visitor details

        Args:
            persona_id: UUID of the persona the conversation was with
            session_id: Session token/ID for the conversation
            min_message_count: Minimum messages required to send summary (default: 3)
            conversation_type: Type of conversation - "voice" or "text" (default: "voice")

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            async with async_session_maker() as session:
                # Find the conversation
                conversation = await self._get_voice_conversation(
                    session, persona_id, session_id, conversation_type
                )

                if not conversation:
                    self.logger.warning(
                        f"No {conversation_type} conversation found for persona={persona_id}, session={session_id}"
                    )
                    return False

                # Check minimum message count
                messages = conversation.messages or []
                if len(messages) < min_message_count:
                    self.logger.info(
                        f"Skipping summary - only {len(messages)} messages "
                        f"(minimum: {min_message_count})"
                    )
                    return False

                # Check if email was already sent (deduplication)
                if conversation.summary_generated_at is not None:
                    self.logger.info(
                        f"📧 Skipping duplicate - summary email already sent for conversation "
                        f"{conversation.id} at {conversation.summary_generated_at}"
                    )
                    return False

                # Get persona and owner details
                persona = await self._get_persona_with_owner(session, persona_id)
                if not persona or not persona.user:
                    self.logger.error(f"Persona or owner not found for {persona_id}")
                    return False

                # Check if summary emails are enabled for this persona
                if not persona.send_summary_email_enabled:
                    self.logger.info(
                        f"📧 Skipping summary email - send_summary_email_enabled=False "
                        f"for persona {persona.name} ({persona_id})"
                    )
                    return False

                owner = persona.user
                if not owner.email:
                    self.logger.warning(
                        f"Persona owner {owner.id} has no email - cannot send summary"
                    )
                    return False

                # Generate structured AI summary (new format)
                structured_summary = await self._generate_structured_summary(
                    messages, persona.name, conversation_type
                )

                # Store summary in database for caching
                await self._store_summary_in_db(session, conversation, structured_summary)

                # Build visitor info from UserSession (primary source for email capture data)
                visitor_info = await self._build_visitor_info(session, session_id)

                # Get custom email sender config if available (whitelabel)
                sender_config = await self.custom_email_domain_service.get_sender_config(
                    session, owner.id
                )

                # Send structured email (new concise format)
                email_sent = await self._send_structured_summary_email(
                    owner=owner,
                    persona=persona,
                    conversation=conversation,
                    structured_summary=structured_summary,
                    visitor_info=visitor_info,
                    conversation_type=conversation_type,
                    message_count=len(messages),
                    sender_config=sender_config,
                )

                if email_sent:
                    self.logger.info(
                        f"✅ {conversation_type.capitalize()} conversation summary email sent to {owner.email} "
                        f"(conversation: {conversation.id}, {len(messages)} messages)"
                    )

                return email_sent

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(persona_id),
                    "session_id": session_id,
                    "conversation_type": conversation_type,
                },
                tags={
                    "component": "conversation_summary_email",
                    "operation": "send_conversation_summary",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(
                f"❌ Failed to send {conversation_type} conversation summary: {e}", exc_info=True
            )
            return False

    async def _get_voice_conversation(
        self,
        session: AsyncSession,
        persona_id: UUID,
        session_id: str,
        conversation_type: str = "voice",
    ) -> Optional[Conversation]:
        """Get conversation by persona_id, session_id, and type (voice or text)"""
        stmt = select(Conversation).where(
            Conversation.persona_id == persona_id,
            Conversation.session_id == session_id,
            Conversation.conversation_type == conversation_type,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_persona_with_owner(
        self,
        session: AsyncSession,
        persona_id: UUID,
    ) -> Optional[Persona]:
        """Get persona with eagerly loaded owner (user)"""
        from sqlalchemy.orm import selectinload

        stmt = select(Persona).options(selectinload(Persona.user)).where(Persona.id == persona_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _generate_summary(
        self,
        messages: list,
        persona_name: str,
    ) -> Optional[str]:
        """Generate AI summary of the conversation (legacy method)"""
        try:
            summary_result = await self.summary_service.generate_summary(
                messages=messages,
                conversation_type="voice",
                persona_name=persona_name,
            )

            # Combine summary with key topics for email
            summary = summary_result.get("summary", "")
            key_topics = summary_result.get("key_topics", "")

            if key_topics:
                return f"{summary}\n\nKey topics: {key_topics}"
            return summary

        except Exception as e:
            self.logger.warning(f"Failed to generate AI summary: {e}")
            return None

    async def _generate_structured_summary(
        self,
        messages: list,
        persona_name: str,
        conversation_type: str = "voice",
    ) -> dict:
        """Generate structured AI summary optimized for email notifications"""
        try:
            structured_summary = await self.summary_service.generate_structured_summary(
                messages=messages,
                conversation_type=conversation_type,
                persona_name=persona_name,
            )
            return structured_summary

        except Exception as e:
            self.logger.warning(f"Failed to generate structured AI summary: {e}")
            return {
                "synopsis": "Unable to generate summary.",
                "key_topics": [],
                "key_details": {},
                "questions_answers": [],
                "follow_up": {},
                "sentiment": "neutral",
            }

    async def _store_summary_in_db(
        self,
        session: AsyncSession,
        conversation: Conversation,
        structured_summary: dict,
    ) -> None:
        """Store the structured summary in the conversation record for caching"""
        from datetime import datetime, timezone

        try:
            # Store synopsis in ai_summary for backward compatibility
            conversation.ai_summary = structured_summary.get("synopsis", "")

            # Store full structured data in summary_metadata
            conversation.summary_metadata = {
                "synopsis": structured_summary.get("synopsis"),
                "key_topics": structured_summary.get("key_topics", []),
                "key_details": structured_summary.get("key_details", {}),
                "questions_answers": structured_summary.get("questions_answers", []),
                "follow_up": structured_summary.get("follow_up", {}),
                "sentiment": structured_summary.get("sentiment", "neutral"),
                "persona_name": None,  # Will be set if needed
                "message_count": len(conversation.messages or []),
            }

            conversation.summary_generated_at = datetime.now(timezone.utc)

            await session.commit()
            self.logger.info(
                f"📝 Stored structured summary in DB for conversation {conversation.id}"
            )

        except Exception as e:
            self.logger.warning(f"Failed to store summary in DB: {e}")
            # Don't fail the email send if DB storage fails
            await session.rollback()

    async def _send_structured_summary_email(
        self,
        owner: User,
        persona: Persona,
        conversation: Conversation,
        structured_summary: dict,
        visitor_info: dict,
        conversation_type: str,
        message_count: int,
        sender_config=None,
    ) -> bool:
        """Send the structured summary email"""
        # Use custom sender email if available (whitelabel)
        from_email = None
        if sender_config:
            from_email = sender_config.formatted_from
            self.logger.info(f"📧 Using custom email domain: {from_email}")

        return await self.email_service.send_structured_conversation_email(
            to_email=owner.email,
            user_name=owner.fullname or "User",
            persona_name=persona.name,
            conversation_id=str(conversation.id),
            structured_summary=structured_summary,
            visitor_info=visitor_info,
            conversation_type=conversation_type,
            message_count=message_count,
            username=owner.username,
            persona_url_name=persona.persona_name,
            from_email=from_email,
        )

    async def _build_visitor_info(
        self,
        session: AsyncSession,
        session_id: str,
    ) -> dict:
        """Extract visitor information from UserSession table, with workflow fallback.

        Priority order:
        1. UserSession (email capture popup) - visitor explicitly provided info
        2. Workflow extracted_fields (conversational workflow) - agent captured during conversation

        Args:
            session: Database session
            session_id: Session token to lookup UserSession

        Returns:
            dict with fullname, email, phone (any can be None)
        """
        visitor_info = {
            "fullname": None,
            "email": None,
            "phone": None,
        }

        if not session_id:
            return visitor_info

        # Source 1: UserSession (email capture popup)
        try:
            stmt = select(UserSession).where(UserSession.session_token == session_id)
            result = await session.execute(stmt)
            user_session = result.scalar_one_or_none()

            if user_session:
                metadata = user_session.session_metadata or {}

                # Only use visitor info if they explicitly provided it via email capture
                # The 'email_provided' flag is set when visitor submits the email form
                if metadata.get("email_provided", False):
                    # Get email from UserSession.user_email
                    if user_session.user_email:
                        # Skip anonymous placeholder emails
                        if not user_session.user_email.startswith("anon_"):
                            visitor_info["email"] = user_session.user_email
                            self.logger.info(
                                f"📧 Found visitor email in UserSession: {user_session.user_email}"
                            )

                    # Get fullname and phone from session_metadata
                    if metadata.get("fullname"):
                        visitor_info["fullname"] = metadata.get("fullname")
                    if metadata.get("phone"):
                        visitor_info["phone"] = metadata.get("phone")
                else:
                    self.logger.info(
                        "ℹ️ Visitor did not explicitly provide contact info (email_provided=False)"
                    )

        except Exception as e:
            self.logger.warning(f"Failed to lookup UserSession for visitor info: {e}")

        # Source 2: Workflow extracted_fields (fallback for conversational workflows)
        # If UserSession didn't have contact info, check if the workflow captured it
        if not visitor_info["email"] and not visitor_info["fullname"]:
            try:
                from shared.database.models.workflow import (
                    PersonaWorkflow,
                    WorkflowSession,
                )

                stmt = (
                    select(
                        WorkflowSession.extracted_fields,
                        PersonaWorkflow.workflow_config,
                    )
                    .join(
                        PersonaWorkflow,
                        WorkflowSession.workflow_id == PersonaWorkflow.id,
                    )
                    .where(WorkflowSession.session_token == session_id)
                    .where(WorkflowSession.extracted_fields.isnot(None))
                    .limit(1)
                )
                result = await session.execute(stmt)
                row = result.first()

                if row:
                    extracted = row.extracted_fields
                    workflow_config = row.workflow_config or {}

                    # Build field_type lookup from workflow config
                    # This lets us find email/phone/name fields regardless of field_id
                    all_fields = workflow_config.get("required_fields", []) + workflow_config.get(
                        "optional_fields", []
                    )
                    type_to_field_ids: dict[str, list[str]] = {}
                    for f in all_fields:
                        ft = f.get("field_type", "")
                        fid = f.get("field_id", "")
                        type_to_field_ids.setdefault(ft, []).append(fid)

                    def _get_value(field_data):
                        """Extract value from ExtractedFieldValue dict or plain value."""
                        if isinstance(field_data, dict) and "value" in field_data:
                            return field_data["value"]
                        return field_data

                    # Strategy 1: Convention-based (contact_name, contact_email, contact_phone)
                    name_val = _get_value(extracted.get("contact_name"))
                    email_val = _get_value(extracted.get("contact_email"))
                    phone_val = _get_value(extracted.get("contact_phone"))

                    # Strategy 2: field_type-based fallback (find first email/phone/text field)
                    if not email_val:
                        for fid in type_to_field_ids.get("email", []):
                            val = _get_value(extracted.get(fid))
                            if val:
                                email_val = val
                                break

                    if not phone_val:
                        for fid in type_to_field_ids.get("phone", []):
                            val = _get_value(extracted.get(fid))
                            if val:
                                phone_val = val
                                break

                    # For name, use field_type="name" from workflow config,
                    # then fall back to field_ids that look like person names.
                    # Avoid matching business_name, company_name, domain_name, etc.
                    if not name_val:
                        # First: check field_type="name" fields from workflow config
                        for fid in type_to_field_ids.get("name", []):
                            val = _get_value(extracted.get(fid))
                            if val:
                                name_val = val
                                break
                    if not name_val:
                        # Fallback: allowlist of known person-name field_id patterns
                        name_allowlist = (
                            "contact_name",
                            "full_name",
                            "fullname",
                            "visitor_name",
                            "caller_name",
                            "first_name",
                            "last_name",
                        )
                        for fid in name_allowlist:
                            val = _get_value(extracted.get(fid))
                            if val:
                                name_val = val
                                break

                    if name_val and not visitor_info["fullname"]:
                        visitor_info["fullname"] = name_val
                    if email_val and not visitor_info["email"]:
                        visitor_info["email"] = email_val
                    if phone_val and not visitor_info["phone"]:
                        visitor_info["phone"] = phone_val

                    if any([name_val, email_val, phone_val]):
                        self.logger.info(
                            "Enriched visitor info from workflow extracted_fields: "
                            f"has_name={bool(name_val)}, has_email={bool(email_val)}, has_phone={bool(phone_val)}"
                        )

            except Exception as e:
                self.logger.warning(
                    f"Failed to lookup workflow extracted_fields for visitor info: {e}"
                )

        return visitor_info

    async def _send_summary_email(
        self,
        session: AsyncSession,
        owner: User,
        persona: Persona,
        conversation: Conversation,
        messages: list,
        ai_summary: Optional[str],
        visitor_info: dict,
        sender_config=None,
    ) -> bool:
        """Send the summary email with visitor details

        Args:
            session: Database session
            owner: User who owns the persona
            persona: Persona that had the conversation
            conversation: The conversation record
            messages: List of messages in the conversation
            ai_summary: AI-generated summary
            visitor_info: Visitor contact information
            sender_config: Optional SenderConfig for custom email domain (whitelabel)
        """
        # Build enhanced AI summary with visitor info
        enhanced_summary = self._build_enhanced_summary(ai_summary, visitor_info)

        # Use custom sender email if available (whitelabel)
        from_email = None
        if sender_config:
            from_email = sender_config.formatted_from
            self.logger.info(f"📧 Using custom email domain for summary email: {from_email}")

        return await self.email_service.send_individual_conversation_email(
            to_email=owner.email,
            user_name=owner.fullname or "User",
            persona_name=persona.name,
            conversation_id=str(conversation.id),
            messages=messages,
            ai_summary=enhanced_summary,
            username=owner.username,
            persona_url_name=persona.persona_name,
            from_email=from_email,
        )

    def _build_enhanced_summary(
        self,
        ai_summary: Optional[str],
        visitor_info: dict,
    ) -> str:
        """Build enhanced summary including visitor details"""
        parts = []

        # Add visitor details section
        visitor_parts = []
        if visitor_info.get("fullname"):
            visitor_parts.append(f"👤 Name: {visitor_info['fullname']}")
        if visitor_info.get("email"):
            visitor_parts.append(f"📧 Email: {visitor_info['email']}")
        if visitor_info.get("phone"):
            visitor_parts.append(f"📱 Phone: {visitor_info['phone']}")

        if visitor_parts:
            parts.append("VISITOR DETAILS:\n" + "\n".join(visitor_parts))
        else:
            # Add note when no visitor details are available
            parts.append(
                "VISITOR DETAILS:\n"
                "ℹ️ Visitor did not provide contact information during this conversation."
            )

        # Add AI summary if available
        if ai_summary:
            parts.append(f"CONVERSATION SUMMARY:\n{ai_summary}")

        return "\n\n".join(parts) if parts else ""


# Async helper function for fire-and-forget usage from agents
async def send_conversation_summary_async(
    persona_id: UUID,
    session_id: str,
    min_message_count: int = 3,
    conversation_type: str = "voice",
) -> bool:
    """
    Fire-and-forget async function to send conversation summary email

    This function is designed to be called from the agent's shutdown callback
    without blocking the agent shutdown. It handles all errors internally.

    Args:
        persona_id: UUID of the persona
        session_id: Session token/ID for the conversation
        min_message_count: Minimum messages to trigger summary
        conversation_type: Type of conversation - "voice" or "text" (default: "voice")

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        service = ConversationSummaryEmailService()
        return await service.send_conversation_summary(
            persona_id=persona_id,
            session_id=session_id,
            min_message_count=min_message_count,
            conversation_type=conversation_type,
        )
    except Exception as e:
        logger.error(f"❌ Fire-and-forget conversation summary email failed: {e}")
        return False  # Return False on exception
