"""
Conversation Service - Handles saving conversations from LiveKit and other sources

This service provides a clean interface for saving conversations to the database,
abstracting away the database logic from the agent code.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import attributes

from shared.database.models.database import Conversation, async_session_maker
from shared.database.models.user_session import UserSession
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversation persistence"""

    @staticmethod
    async def save_livekit_conversation(
        persona_id: UUID,
        session_token: str,
        conversation_history: List[dict],
        conversation_type: str = "voice",
        captured_lead_data: Optional[dict] = None,
    ) -> Optional[UUID]:
        """
        Save LiveKit conversation to database

        Args:
            persona_id: UUID of the persona
            session_token: Session token/ID
            conversation_history: List of message dicts with 'role' and 'content'
            conversation_type: "voice" or "text"
            captured_lead_data: Optional dict with keys 'contact_name', 'contact_email',
                'contact_phone' from DefaultCaptureHandler's in-memory state.
                Used as a fallback when the RPC/capture-lead endpoint didn't fire.

        Returns:
            Conversation UUID if saved successfully, None otherwise
        """
        try:
            if not session_token or not conversation_history:
                logger.warning(
                    f"⚠️ Skipping conversation save: session_token={bool(session_token)}, "
                    f"messages={len(conversation_history) if conversation_history else 0}"
                )
                return None

            logger.info(
                f"💾 Saving {conversation_type} conversation: {len(conversation_history)} messages "
                f"for persona {persona_id}"
            )

            # Debug: Log first and last message to detect duplicates in input
            if conversation_history:
                first_msg = conversation_history[0]
                last_msg = conversation_history[-1]
                logger.info(
                    f"📋 First message: {first_msg.get('role', 'unknown')}: {first_msg.get('content', '')[:50]}..."
                )
                logger.info(
                    f"📋 Last message: {last_msg.get('role', 'unknown')}: {last_msg.get('content', '')[:50]}..."
                )

            async with async_session_maker() as db_session:
                # Check if conversation exists
                logger.info(
                    f"🔍 Looking for existing conversation: persona_id={persona_id}, "
                    f"session_id={session_token}, type={conversation_type}"
                )
                stmt = select(Conversation).where(
                    Conversation.persona_id == persona_id,
                    Conversation.session_id == session_token,
                    Conversation.conversation_type == conversation_type,
                )
                result = await db_session.execute(stmt)
                conversation = result.scalar_one_or_none()

                if conversation:
                    logger.info(
                        f"✅ Found existing conversation {conversation.id} with {len(conversation.messages or [])} messages"
                    )
                else:
                    logger.info("❌ No existing conversation found - will create new one")

                # Format messages with timestamps
                formatted_messages = []
                for msg in conversation_history:
                    formatted_msg = {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message_type": conversation_type,
                    }
                    formatted_messages.append(formatted_msg)

                if conversation:
                    # Update existing conversation - deduplicate messages
                    existing_messages = conversation.messages or []

                    # Build set of existing message signatures to avoid duplicates
                    # Signature: (role, content) tuple
                    existing_signatures = {
                        (msg.get("role"), msg.get("content")) for msg in existing_messages
                    }

                    logger.info(
                        f"🔍 Existing conversation has {len(existing_signatures)} unique message signatures"
                    )

                    # Only add messages that don't already exist
                    new_messages = []
                    duplicate_count = 0
                    for msg in formatted_messages:
                        signature = (msg.get("role"), msg.get("content"))
                        if signature not in existing_signatures:
                            new_messages.append(msg)
                            logger.debug(
                                f"  ✅ New: {msg.get('role')}: {msg.get('content')[:50]}..."
                            )
                        else:
                            duplicate_count += 1
                            logger.info(
                                f"  ⏭️  Duplicate skipped: {msg.get('role')}: {msg.get('content')[:50]}..."
                            )

                    if new_messages:
                        existing_messages.extend(new_messages)
                        conversation.messages = existing_messages
                        conversation.updated_at = datetime.now(timezone.utc)
                        attributes.flag_modified(conversation, "messages")
                        logger.info(
                            f"📝 Updated conversation {conversation.id}: added {len(new_messages)} new messages, "
                            f"skipped {duplicate_count} duplicates, total now: {len(conversation.messages)}"
                        )
                    else:
                        logger.info(
                            f"⏭️  No new messages to add - all {len(formatted_messages)} messages already exist in conversation {conversation.id}"
                        )
                else:
                    # Create new conversation
                    conversation = Conversation(
                        persona_id=persona_id,
                        session_id=session_token,
                        conversation_type=conversation_type,
                        messages=formatted_messages,
                    )
                    db_session.add(conversation)
                    logger.info(
                        f"📝 Created new conversation with {len(formatted_messages)} messages"
                    )

                # Backfill lead capture data from session if available
                # This handles the race condition where /capture-lead runs
                # before the conversation row exists
                await ConversationService._backfill_lead_data_from_session(
                    db_session, conversation, session_token
                )

                # Backfill from DefaultCaptureHandler's in-memory data
                # This is the safety net for partial captures (e.g., got name+email
                # but not phone) or when the RPC to frontend never fired.
                # The inner method only fills gaps (won't overwrite existing fields).
                if captured_lead_data:
                    ConversationService._apply_captured_lead_data(conversation, captured_lead_data)

                await db_session.commit()
                logger.info(f"✅ {conversation_type.capitalize()} conversation saved to database")
                return conversation.id

        except Exception as e:
            logger.error(f"❌ Failed to save {conversation_type} conversation: {e}", exc_info=True)
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(persona_id),
                    "session_token": session_token,
                    "conversation_type": conversation_type,
                    "message_count": len(conversation_history) if conversation_history else 0,
                },
                tags={
                    "component": "conversation_service",
                    "operation": "save_livekit_conversation",
                    "severity": "high",
                    "user_facing": "false",
                },
            )
            return None

    @staticmethod
    async def _backfill_lead_data_from_session(
        db_session,
        conversation: Conversation,
        session_token: str,
    ) -> None:
        """
        Check if the session has lead capture data and backfill it onto the conversation.

        This handles the race condition where /capture-lead updates the session
        mid-conversation, but the conversation row doesn't exist yet. When the
        conversation is finally created at shutdown, this method pulls the lead
        data from the session and populates the conversation fields.

        Only backfills if the conversation doesn't already have user_email set
        (avoids overwriting data that was already set by /capture-lead UPDATE).
        """
        try:
            # Skip if conversation already has lead data
            if conversation.user_email:
                return

            stmt = select(UserSession).where(UserSession.session_token == session_token)
            result = await db_session.execute(stmt)
            user_session = result.scalar_one_or_none()

            if not user_session:
                return

            metadata = user_session.session_metadata or {}

            # Check if lead capture happened on this session
            if not metadata.get("email_provided"):
                return

            # Backfill from session data
            conversation.user_email = user_session.user_email
            conversation.user_fullname = metadata.get("fullname")
            conversation.user_phone = metadata.get("phone")

            # Link user_id if available
            authenticated_user_id = metadata.get("authenticated_user_id")
            if authenticated_user_id:
                conversation.user_id = UUID(authenticated_user_id)

            logger.info(
                f"🔗 [BACKFILL] Lead data applied to conversation from session: "
                f"email={user_session.user_email}, "
                f"name={metadata.get('fullname')}, "
                f"user_id={authenticated_user_id}"
            )

        except Exception as e:
            # Non-fatal — conversation is still saved, just without lead data
            logger.warning(f"⚠️ [BACKFILL] Failed to backfill lead data: {e}")
            capture_exception_with_context(
                e,
                extra={
                    "session_token": session_token,
                    "conversation_id": str(conversation.id) if conversation.id else None,
                },
                tags={
                    "component": "conversation_service",
                    "operation": "backfill_lead_data",
                    "severity": "low",
                    "user_facing": "false",
                },
            )

    @staticmethod
    def _apply_captured_lead_data(
        conversation: Conversation,
        captured_lead_data: Dict[str, str],
    ) -> None:
        """
        Apply DefaultCaptureHandler's in-memory captured fields to the conversation.

        This is a safety net for cases where:
        - The RPC to frontend never fired (partial capture, no phone)
        - The /capture-lead endpoint wasn't called
        - The session-based backfill had nothing to pull from

        Only sets fields that aren't already populated on the conversation.

        Args:
            conversation: The Conversation ORM object to update
            captured_lead_data: Dict with keys like 'contact_name', 'contact_email', 'contact_phone'
        """
        if not captured_lead_data:
            return

        applied = []

        name = captured_lead_data.get("contact_name")
        if name and not conversation.user_fullname:
            conversation.user_fullname = name
            applied.append(f"name={name}")

        email = captured_lead_data.get("contact_email")
        if email and not conversation.user_email:
            conversation.user_email = email
            applied.append(f"email={email}")

        phone = captured_lead_data.get("contact_phone")
        if phone and not conversation.user_phone:
            conversation.user_phone = phone
            applied.append(f"phone={phone}")

        if applied:
            logger.info(
                f"🔗 [BACKFILL] Lead data applied from DefaultCaptureHandler: {', '.join(applied)}"
            )
        else:
            logger.info(
                "🔗 [BACKFILL] DefaultCaptureHandler data skipped — "
                "conversation already has lead data"
            )
