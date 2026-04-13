"""
Conversation Repository - Database operations for conversations
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import Conversation

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation database operations"""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session

        Args:
            session: Database session
        """
        self.session = session

    async def get_by_id(self, conversation_id: UUID) -> Optional[Conversation]:
        """
        Get conversation by ID

        Args:
            conversation_id: UUID of the conversation

        Returns:
            Conversation if found, None otherwise
        """
        try:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {e}")
            return None

    async def get_by_user_id(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
        conversation_type: Optional[str] = None,
    ) -> List[Conversation]:
        """
        Get all conversations for a user (expert/owner) across all their personas

        This method gets conversations where the user OWNS the persona that was chatted with.
        NOT conversations where the user was the visitor/chat participant.

        Args:
            user_id: UUID of the user (expert/owner)
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            conversation_type: Filter by conversation type ('text' or 'voice'), None for all

        Returns:
            List of conversations ordered by most recent first
        """
        try:
            from shared.database.models.database import Persona

            # Join conversations with personas to filter by user_id (owner)
            stmt = (
                select(Conversation)
                .join(Persona, Conversation.persona_id == Persona.id)
                .where(Persona.user_id == user_id)
            )

            if conversation_type:
                stmt = stmt.where(Conversation.conversation_type == conversation_type)

            stmt = stmt.order_by(desc(Conversation.updated_at)).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting conversations for user {user_id}: {e}")
            return []

    async def get_by_persona_id(
        self,
        persona_id: UUID,
        limit: int = 100,
        offset: int = 0,
        conversation_type: Optional[str] = None,
    ) -> List[Conversation]:
        """
        Get all conversations for a persona

        Args:
            persona_id: UUID of the persona
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            conversation_type: Filter by conversation type ('text' or 'voice'), None for all

        Returns:
            List of conversations ordered by most recent first
        """
        try:
            stmt = select(Conversation).where(Conversation.persona_id == persona_id)

            if conversation_type:
                stmt = stmt.where(Conversation.conversation_type == conversation_type)

            stmt = stmt.order_by(desc(Conversation.updated_at)).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting conversations for persona {persona_id}: {e}")
            return []

    async def count_by_user_id(self, user_id: UUID, conversation_type: Optional[str] = None) -> int:
        """
        Count total conversations for a user (expert/owner) across all their personas

        Args:
            user_id: UUID of the user (expert/owner)
            conversation_type: Filter by conversation type ('text' or 'voice'), None for all

        Returns:
            Total count of conversations
        """
        try:
            from sqlalchemy import func

            from shared.database.models.database import Persona

            # Join with personas to count conversations where user owns the persona
            stmt = (
                select(func.count(Conversation.id))
                .join(Persona, Conversation.persona_id == Persona.id)
                .where(Persona.user_id == user_id)
            )

            if conversation_type:
                stmt = stmt.where(Conversation.conversation_type == conversation_type)

            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error counting conversations for user {user_id}: {e}")
            return 0

    async def count_by_persona_id(
        self, persona_id: UUID, conversation_type: Optional[str] = None
    ) -> int:
        """
        Count total conversations for a persona

        Args:
            persona_id: UUID of the persona
            conversation_type: Filter by conversation type ('text' or 'voice'), None for all

        Returns:
            Total count of conversations
        """
        try:
            from sqlalchemy import func

            stmt = select(func.count(Conversation.id)).where(Conversation.persona_id == persona_id)

            if conversation_type:
                stmt = stmt.where(Conversation.conversation_type == conversation_type)

            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error counting conversations for persona {persona_id}: {e}")
            return 0

    async def get_counts_by_user_id(self, user_id: UUID) -> dict:
        """
        Get total, text, and voice conversation counts in a single query.

        Args:
            user_id: UUID of the user (expert/owner)

        Returns:
            Dictionary with 'total', 'text', and 'voice' counts
        """
        try:
            from sqlalchemy import case, func

            from shared.database.models.database import Persona

            stmt = (
                select(
                    func.count(Conversation.id).label("total"),
                    func.count(case((Conversation.conversation_type == "text", 1))).label("text"),
                    func.count(case((Conversation.conversation_type == "voice", 1))).label("voice"),
                )
                .join(Persona, Conversation.persona_id == Persona.id)
                .where(Persona.user_id == user_id)
            )

            result = await self.session.execute(stmt)
            row = result.one()
            return {"total": row.total, "text": row.text, "voice": row.voice}
        except Exception as e:
            logger.error(f"Error getting conversation counts for user {user_id}: {e}")
            return {"total": 0, "text": 0, "voice": 0}

    async def get_counts_by_persona_id(self, persona_id: UUID) -> dict:
        """
        Get total, text, and voice conversation counts for a persona in a single query.

        Args:
            persona_id: UUID of the persona

        Returns:
            Dictionary with 'total', 'text', and 'voice' counts
        """
        try:
            from sqlalchemy import case, func

            stmt = select(
                func.count(Conversation.id).label("total"),
                func.count(case((Conversation.conversation_type == "text", 1))).label("text"),
                func.count(case((Conversation.conversation_type == "voice", 1))).label("voice"),
            ).where(Conversation.persona_id == persona_id)

            result = await self.session.execute(stmt)
            row = result.one()
            return {"total": row.total, "text": row.text, "voice": row.voice}
        except Exception as e:
            logger.error(f"Error getting conversation counts for persona {persona_id}: {e}")
            return {"total": 0, "text": 0, "voice": 0}

    async def get_workflow_data_for_conversations(
        self, conversation_ids: List[UUID]
    ) -> Dict[UUID, Dict[str, Any]]:
        """
        Get workflow session data for multiple conversations.

        This is used to enrich conversation list with:
        - workflow_session_id: UUID of the workflow session (for fetching lead evaluation)
        - extracted_fields: Lead capture data (contact_name, contact_email, etc.)

        Links via session_token: conversations.session_id = workflow_sessions.session_token

        Args:
            conversation_ids: List of conversation UUIDs

        Returns:
            Dictionary mapping conversation_id to workflow data:
            {
                conversation_id: {
                    "workflow_session_id": UUID,
                    "extracted_fields": {...}
                }
            }
        """
        if not conversation_ids:
            return {}

        try:
            from shared.database.models.workflow import WorkflowSession

            # Join conversations with workflow_sessions via conversation_id,
            # falling back to session_token match for older records where
            # conversation_id was not set (bug fix: it was always NULL before).
            stmt = (
                select(
                    Conversation.id.label("conversation_id"),
                    WorkflowSession.id.label("workflow_session_id"),
                    WorkflowSession.collected_data,
                    WorkflowSession.extracted_fields,
                    WorkflowSession.result_data,
                )
                .join(
                    WorkflowSession,
                    or_(
                        Conversation.id == WorkflowSession.conversation_id,
                        and_(
                            WorkflowSession.conversation_id.is_(None),
                            Conversation.session_id == WorkflowSession.session_token,
                        ),
                    ),
                )
                .where(
                    Conversation.id.in_(conversation_ids),
                )
            )

            result = await self.session.execute(stmt)
            rows = result.all()

            # Build mapping of conversation_id -> workflow data
            # Conversational workflows use extracted_fields; linear/scored use collected_data
            workflow_data = {}
            for row in rows:
                if row.conversation_id:
                    workflow_data[row.conversation_id] = {
                        "workflow_session_id": row.workflow_session_id,
                        "extracted_fields": row.extracted_fields or row.collected_data,
                        "result_data": row.result_data,
                    }

            logger.debug(
                f"Found workflow data for {len(workflow_data)}/{len(conversation_ids)} conversations"
            )
            return workflow_data

        except Exception as e:
            logger.error(f"Error getting workflow data for conversations: {e}")
            return {}
