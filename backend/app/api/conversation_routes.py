"""
Conversation API Routes - Endpoints for retrieving conversation history
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.conversation_models import (
    ConversationDetail,
    ConversationListResponse,
    ConversationPostProcessRequest,
    ConversationSummary,
    ConversationSummaryResult,
)
from app.auth.jwt_auth import get_user_or_service
from app.services.conversation_summary_service import ConversationSummaryService
from shared.database.models import ConversationAttachment, get_session
from shared.database.models.user import User
from shared.database.models.voice_session import RecordingStatus, VoiceSession
from shared.database.repositories.conversation_repository import ConversationRepository
from shared.monitoring.sentry_utils import add_breadcrumb, capture_exception_with_context
from shared.services.s3_service import get_s3_service

router = APIRouter(prefix="/api/v1", tags=["Conversations"])
logger = logging.getLogger(__name__)


def _normalize_key_topics(key_topics) -> str:
    """Normalize key_topics to string format.

    Handles both string and list formats for backwards compatibility
    with older generate_structured_summary data.
    """
    if isinstance(key_topics, list):
        return ", ".join(key_topics)
    return key_topics if key_topics else ""


def _create_conversation_summary(
    conversation, workflow_data: Optional[Dict[str, Any]] = None
) -> ConversationSummary:
    """
    Helper to create ConversationSummary from Conversation model.

    Args:
        conversation: Conversation model instance
        workflow_data: Optional workflow session data containing:
            - workflow_session_id: UUID of the workflow session
            - extracted_fields: Lead capture data (contact_name, contact_email, etc.)

    Returns:
        ConversationSummary with user info from conversation or workflow data
    """
    messages = conversation.messages or []
    message_count = len(messages)

    # Get last message preview
    last_message_preview = None
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, dict):
            # Try both 'content' and 'text' fields for compatibility
            text = last_msg.get("content") or last_msg.get("text")
            if text:
                last_message_preview = text[:100] + "..." if len(text) > 100 else text

    # Start with conversation's stored values
    user_email = conversation.user_email
    user_fullname = conversation.user_fullname
    user_phone = conversation.user_phone
    workflow_session_id = None

    # If workflow data exists, extract workflow_session_id and fill in missing fields
    if workflow_data:
        # Get workflow session ID
        ws_id = workflow_data.get("workflow_session_id")
        if ws_id:
            workflow_session_id = str(ws_id)

        # Get extracted fields for user info
        # Format: {"contact_name": {"value": "John"}, ...}
        extracted_fields = workflow_data.get("extracted_fields") or {}
        if not user_fullname and "contact_name" in extracted_fields:
            user_fullname = extracted_fields["contact_name"].get("value")
        if not user_email and "contact_email" in extracted_fields:
            user_email = extracted_fields["contact_email"].get("value")
        if not user_phone and "contact_phone" in extracted_fields:
            user_phone = extracted_fields["contact_phone"].get("value")

    return ConversationSummary(
        id=str(conversation.id),
        persona_id=str(conversation.persona_id),
        session_id=conversation.session_id,
        workflow_session_id=workflow_session_id,
        extracted_fields=workflow_data.get("extracted_fields") if workflow_data else None,
        result_data=workflow_data.get("result_data") if workflow_data else None,
        user_email=user_email,
        user_fullname=user_fullname,
        user_phone=user_phone,
        conversation_type=conversation.conversation_type,
        message_count=message_count,
        last_message_preview=last_message_preview,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _create_conversation_detail(
    conversation,
    workflow_data: Optional[Dict[str, Any]] = None,
    recording_data: Optional[Dict[str, Any]] = None,
) -> ConversationDetail:
    """
    Helper to create ConversationDetail from Conversation model.

    Args:
        conversation: Conversation model instance
        workflow_data: Optional workflow session data containing:
            - workflow_session_id: UUID of the workflow session
            - extracted_fields: Lead capture data (contact_name, contact_email, etc.)
        recording_data: Optional recording data for voice conversations containing:
            - recording_url: Presigned S3 URL for playback
            - recording_status: Status string (disabled, pending, active, completed, failed)
            - recording_duration_seconds: Duration in seconds

    Returns:
        ConversationDetail with user info from conversation or workflow data
    """
    messages = conversation.messages or []
    message_count = len(messages)

    # Start with conversation's stored values
    user_email = conversation.user_email
    user_fullname = conversation.user_fullname
    user_phone = conversation.user_phone
    workflow_session_id = None

    # If workflow data exists, extract workflow_session_id and fill in missing fields
    if workflow_data:
        # Get workflow session ID
        ws_id = workflow_data.get("workflow_session_id")
        if ws_id:
            workflow_session_id = str(ws_id)

        # Get extracted fields for user info
        # Format: {"contact_name": {"value": "John"}, ...}
        extracted_fields = workflow_data.get("extracted_fields") or {}
        if not user_fullname and "contact_name" in extracted_fields:
            user_fullname = extracted_fields["contact_name"].get("value")
        if not user_email and "contact_email" in extracted_fields:
            user_email = extracted_fields["contact_email"].get("value")
        if not user_phone and "contact_phone" in extracted_fields:
            user_phone = extracted_fields["contact_phone"].get("value")

    return ConversationDetail(
        id=str(conversation.id),
        persona_id=str(conversation.persona_id),
        session_id=conversation.session_id,
        workflow_session_id=workflow_session_id,
        extracted_fields=workflow_data.get("extracted_fields") if workflow_data else None,
        result_data=workflow_data.get("result_data") if workflow_data else None,
        user_email=user_email,
        user_fullname=user_fullname,
        user_phone=user_phone,
        conversation_type=conversation.conversation_type,
        messages=messages,
        conversation_metadata=conversation.conversation_metadata,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count,
        # Recording fields (voice conversations only)
        recording_url=recording_data.get("recording_url") if recording_data else None,
        recording_status=recording_data.get("recording_status") if recording_data else None,
        recording_duration_seconds=(
            recording_data.get("recording_duration_seconds") if recording_data else None
        ),
    )


@router.get(
    "/users/{user_id}/conversations",
    response_model=ConversationListResponse,
    summary="List all conversations for a user (expert/owner)",
    description="Retrieve a paginated list of all conversations across all personas owned by the user",
)
async def get_user_conversations(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    conversation_type: Optional[str] = Query(
        default=None, description="Filter by conversation type ('text' or 'voice')"
    ),
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Get all conversations for a user (expert/owner) across all their personas.

    This endpoint returns conversations where the user OWNS the persona that was chatted with.
    NOT conversations where the user was the visitor/chat participant.

    This endpoint returns a paginated list of conversations, ordered by most recent first.

    **Authentication**: Requires JWT token (OAuth via LinkedIn)

    **Parameters:**
    - **user_id**: User UUID (expert/owner) (URL parameter)
    - **limit**: Maximum number of conversations to return (1-500, default: 100)
    - **offset**: Number of conversations to skip for pagination (default: 0)
    - **conversation_type**: Optional filter for conversation type ('text' or 'voice')

    **Returns:**
    - List of conversation summaries with pagination metadata
    """
    try:
        # Validate UUID
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        # Authorization: Users can only access their own conversations, services can access any
        if isinstance(auth, User):
            if str(auth.id) != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access your own conversations",
                )
        # else: auth == "service" - admins/operators can access any user's conversations

        logger.info(
            f"Fetching conversations for user: {user_id} (limit={limit}, offset={offset}, type={conversation_type})"
        )

        # Validate conversation_type if provided
        if conversation_type and conversation_type not in ["text", "voice"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid conversation_type. Must be 'text' or 'voice'",
            )

        # Initialize repository with session
        repo = ConversationRepository(session)

        # Get conversations from repository
        conversations = await repo.get_by_user_id(
            user_id=user_uuid,
            limit=limit,
            offset=offset,
            conversation_type=conversation_type,
        )

        # Get all counts in a single query for performance
        counts = await repo.get_counts_by_user_id(user_id=user_uuid)
        text_count = counts["text"]
        voice_count = counts["voice"]

        # If filtering by type, get filtered total; otherwise use aggregate total
        if conversation_type:
            total = await repo.count_by_user_id(
                user_id=user_uuid, conversation_type=conversation_type
            )
        else:
            total = counts["total"]

        # Fetch workflow data for conversations (to enrich with lead capture info)
        conversation_ids = [conv.id for conv in conversations]
        workflow_data_map = await repo.get_workflow_data_for_conversations(conversation_ids)

        # Convert to summaries, enriching with workflow data where available
        conversation_summaries = [
            _create_conversation_summary(conv, workflow_data_map.get(conv.id))
            for conv in conversations
        ]

        # Determine if there are more results
        has_more = (offset + limit) < total

        logger.info(
            f"Found {len(conversations)} conversations for user {user_id} "
            f"(total: {total}, text: {text_count}, voice: {voice_count}, "
            f"with_workflow_data: {len(workflow_data_map)})"
        )

        return ConversationListResponse(
            conversations=conversation_summaries,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
            text_conversations=text_count,
            voice_conversations=voice_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversations for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get conversation details",
    description="Retrieve detailed information about a specific conversation including all messages",
)
async def get_conversation_by_id(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Get detailed information about a specific conversation.

    This endpoint returns the full conversation including all messages and metadata.

    **Authentication**: Requires JWT token (OAuth via LinkedIn)

    **Parameters:**
    - **conversation_id**: UUID of the conversation (URL parameter)

    **Returns:**
    - Complete conversation details including all messages
    """
    try:
        # Validate UUID
        try:
            conv_uuid = UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id format")

        logger.info(f"Fetching conversation: {conversation_id}")

        # Initialize repository with session
        repo = ConversationRepository(session)

        # Get conversation from repository
        conversation = await repo.get_by_id(conversation_id=conv_uuid)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Authorization: Users can only access their own persona's conversations, services can access any
        if isinstance(auth, User):
            from shared.database.repositories.persona_repository import PersonaRepository

            persona_repo = PersonaRepository(session)
            persona = await persona_repo.get_by_id(conversation.persona_id)
            if not persona or str(persona.user_id) != str(auth.id):
                raise HTTPException(
                    status_code=403,
                    detail="You can only access conversations for personas you own",
                )
        # else: auth == "service" - admins/operators can access any conversation

        # Fetch workflow data for this conversation (to enrich with lead capture info)
        workflow_data = None
        try:
            workflow_data_map = await repo.get_workflow_data_for_conversations([conv_uuid])
            workflow_data = workflow_data_map.get(conv_uuid)
        except Exception as e:
            logger.warning(f"Failed to fetch workflow data for conversation {conversation.id}: {e}")
            # Workflow data is optional - continue without it

        # Fetch recording data for voice conversations
        recording_data = None
        if conversation.conversation_type == "voice" and conversation.session_id:
            try:
                # Find voice session by caller_session_token (matches conversation.session_id)
                # Filter for sessions with recording data and order by recording_status
                # to prefer completed recordings over disabled/failed ones
                from sqlalchemy import and_, case, select

                voice_stmt = (
                    select(VoiceSession)
                    .where(
                        and_(
                            VoiceSession.caller_session_token == conversation.session_id,
                            VoiceSession.recording_s3_path.isnot(None),
                            VoiceSession.recording_s3_path != "",
                        )
                    )
                    .order_by(
                        # Priority ordering for recording status:
                        # - completed (0): Most reliable, has actual recording file
                        # - active (1): Recording in progress
                        # - starting (2): Recording initiation in progress
                        # - failed (3): Recording attempted but failed
                        # - else (4): Covers DISABLED, STOPPING, STOPPED
                        case(
                            (VoiceSession.recording_status == RecordingStatus.COMPLETED, 0),
                            (VoiceSession.recording_status == RecordingStatus.ACTIVE, 1),
                            (VoiceSession.recording_status == RecordingStatus.STARTING, 2),
                            (VoiceSession.recording_status == RecordingStatus.FAILED, 3),
                            else_=4,
                        )
                    )
                    .limit(1)
                )
                voice_result = await session.execute(voice_stmt)
                voice_session = voice_result.scalar_one_or_none()

                if voice_session and voice_session.recording_s3_path:
                    recording_data = {
                        "recording_status": (
                            voice_session.recording_status.value
                            if voice_session.recording_status
                            else None
                        ),
                        "recording_duration_seconds": voice_session.duration_seconds,
                        "recording_url": None,
                    }

                    # Generate presigned URL only for completed recordings
                    if voice_session.recording_status == RecordingStatus.COMPLETED:
                        s3_service = get_s3_service()
                        presigned_url = await s3_service.generate_presigned_url(
                            voice_session.recording_s3_path,
                            expiration_seconds=3600,  # 1 hour
                        )
                        recording_data["recording_url"] = presigned_url

                        add_breadcrumb(
                            message="Generated recording URL for conversation",
                            category="recording",
                            level="info",
                            data={
                                "conversation_id": str(conversation.id),
                                "has_url": bool(presigned_url),
                                "duration": voice_session.duration_seconds,
                            },
                        )

            except Exception as e:
                capture_exception_with_context(
                    e,
                    extra={
                        "conversation_id": str(conversation.id),
                        "session_id": conversation.session_id,
                    },
                    tags={"component": "conversation", "operation": "recording_lookup"},
                )
                logger.warning(f"Failed to fetch recording for conversation {conversation.id}: {e}")

        # Convert to detail model, enriching with workflow and recording data if available
        conversation_detail = _create_conversation_detail(
            conversation, workflow_data, recording_data
        )

        logger.info(
            f"Found conversation {conversation_id} with {conversation_detail.message_count} messages"
            f"{' (with workflow data)' if workflow_data else ''}"
            f"{' (with recording)' if recording_data and recording_data.get('recording_url') else ''}"
        )

        return conversation_detail

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/personas/{persona_id}/conversations",
    response_model=ConversationListResponse,
    summary="List all conversations for a persona",
    description="Retrieve a paginated list of all conversations for a specific persona",
)
async def get_persona_conversations(
    persona_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    conversation_type: Optional[str] = Query(
        default=None, description="Filter by conversation type ('text' or 'voice')"
    ),
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Get all conversations for a persona.

    This endpoint returns a paginated list of conversations for a specific persona,
    ordered by most recent first.

    **Authentication**: Requires JWT token (OAuth via LinkedIn)

    **Parameters:**
    - **persona_id**: UUID of the persona (URL parameter)
    - **limit**: Maximum number of conversations to return (1-500, default: 100)
    - **offset**: Number of conversations to skip for pagination (default: 0)
    - **conversation_type**: Optional filter for conversation type ('text' or 'voice')

    **Returns:**
    - List of conversation summaries with pagination metadata
    """
    try:
        # Validate UUID
        try:
            persona_uuid = UUID(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        # Authorization: Users can only access their own persona's conversations, services can access any
        from shared.database.repositories.persona_repository import PersonaRepository

        persona_repo = PersonaRepository(session)
        persona = await persona_repo.get_by_id(persona_uuid)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")

        if isinstance(auth, User):
            if str(persona.user_id) != str(auth.id):
                raise HTTPException(
                    status_code=403,
                    detail="You can only access conversations for personas you own",
                )
        # else: auth == "service" - admins/operators can access any persona's conversations

        # Validate conversation_type if provided
        if conversation_type and conversation_type not in ["text", "voice"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid conversation_type. Must be 'text' or 'voice'",
            )

        logger.info(
            f"Fetching conversations for persona: {persona_id} "
            f"(limit={limit}, offset={offset}, type={conversation_type})"
        )

        # Initialize repository with session
        repo = ConversationRepository(session)

        # Get conversations from repository
        conversations = await repo.get_by_persona_id(
            persona_id=persona_uuid,
            limit=limit,
            offset=offset,
            conversation_type=conversation_type,
        )

        # Get all counts in a single query for performance
        counts = await repo.get_counts_by_persona_id(persona_id=persona_uuid)
        text_count = counts["text"]
        voice_count = counts["voice"]

        # If filtering by type, get filtered total; otherwise use aggregate total
        if conversation_type:
            total = await repo.count_by_persona_id(
                persona_id=persona_uuid, conversation_type=conversation_type
            )
        else:
            total = counts["total"]

        # Fetch workflow data for conversations (to enrich with lead capture info)
        conversation_ids = [conv.id for conv in conversations]
        workflow_data_map = await repo.get_workflow_data_for_conversations(conversation_ids)

        # Convert to summaries, enriching with workflow data where available
        conversation_summaries = [
            _create_conversation_summary(conv, workflow_data_map.get(conv.id))
            for conv in conversations
        ]

        # Determine if there are more results
        has_more = (offset + limit) < total

        logger.info(
            f"Found {len(conversations)} conversations for persona {persona_id} "
            f"(total: {total}, text: {text_count}, voice: {voice_count}, "
            f"with_workflow_data: {len(workflow_data_map)})"
        )

        return ConversationListResponse(
            conversations=conversation_summaries,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
            text_conversations=text_count,
            voice_conversations=voice_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversations for persona {persona_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/conversations/{conversation_id}/summary",
    response_model=ConversationSummaryResult,
    summary="Get AI-generated conversation summary",
    description="Generate an AI-powered summary of a conversation including key topics and sentiment analysis",
)
async def get_conversation_summary(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Generate an AI-powered summary of a conversation.

    This endpoint analyzes the conversation messages and generates:
    - A concise summary of the conversation
    - Key topics discussed
    - Overall sentiment analysis

    **Authentication**: Requires JWT token (OAuth via LinkedIn)

    **Parameters:**
    - **conversation_id**: UUID of the conversation (URL parameter)

    **Returns:**
    - AI-generated conversation summary with metadata

    **Use Case:**
    This is useful for displaying conversation summaries in dashboard views,
    allowing users to quickly understand the content of their conversations
    without reading through all messages.
    """
    try:
        # Validate UUID
        try:
            conv_uuid = UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id format")

        logger.info(f"Generating summary for conversation: {conversation_id}")

        # Initialize repository with session
        repo = ConversationRepository(session)

        # Get conversation from repository
        conversation = await repo.get_by_id(conversation_id=conv_uuid)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Authorization: Users can only access their own persona's conversation summaries, services can access any
        from shared.database.repositories.persona_repository import PersonaRepository

        persona_repo = PersonaRepository(session)
        persona = await persona_repo.get_by_id(conversation.persona_id)

        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found for this conversation")

        if isinstance(auth, User):
            if str(persona.user_id) != str(auth.id):
                raise HTTPException(
                    status_code=403,
                    detail="You can only access conversations for personas you own",
                )
        # else: auth == "service" - admins/operators can access any conversation summary

        # Get conversation messages
        messages = conversation.messages or []
        message_count = len(messages)

        # Check if conversation has messages
        if message_count == 0:
            return ConversationSummaryResult(
                conversation_id=str(conversation.id),
                summary="This conversation has no messages yet.",
                key_topics="N/A",
                sentiment="neutral",
                message_count=0,
                conversation_type=conversation.conversation_type,
                generated_at=datetime.now(timezone.utc),
            )

        # Check if we have a cached summary
        # Smart cache invalidation based on message count changes
        cached_message_count = (
            conversation.summary_metadata.get("message_count", 0)
            if conversation.summary_metadata
            else 0
        )

        # Cache invalidation rules:
        # 1. No cache exists -> Generate new summary
        # 2. Message count changed significantly (>20% change or >5 new messages) -> Regenerate
        # 3. Otherwise -> Use cached summary
        has_valid_cache = bool(
            conversation.ai_summary
            and conversation.summary_generated_at
            and conversation.summary_metadata
        )

        if has_valid_cache:
            message_count_diff = message_count - cached_message_count
            percentage_change = (
                abs(message_count_diff) / cached_message_count * 100
                if cached_message_count > 0
                else 100
            )

            # Use cache if changes are minor (less than 20% change AND less than 5 new messages)
            should_use_cache = message_count_diff < 5 and percentage_change < 20

            if should_use_cache:
                logger.info(
                    f"✅ Using cached summary for conversation {conversation_id} "
                    f"(cached: {cached_message_count} msgs, current: {message_count} msgs, "
                    f"diff: {message_count_diff}, change: {percentage_change:.1f}%)"
                )
                metadata = conversation.summary_metadata
                return ConversationSummaryResult(
                    conversation_id=str(conversation.id),
                    summary=conversation.ai_summary,
                    key_topics=_normalize_key_topics(metadata.get("key_topics", "")),
                    sentiment=metadata.get("sentiment", "neutral"),
                    message_count=message_count,  # Return current count
                    conversation_type=conversation.conversation_type,
                    generated_at=conversation.summary_generated_at,
                )
            else:
                logger.info(
                    f"🔄 Cache invalidated for conversation {conversation_id} "
                    f"(cached: {cached_message_count} msgs, current: {message_count} msgs, "
                    f"diff: {message_count_diff}, change: {percentage_change:.1f}%)"
                )

        # Generate new summary
        logger.info(
            f"🤖 Generating new summary for conversation {conversation_id} "
            f"({'no cache' if not has_valid_cache else 'cache invalidated'})"
        )

        # Initialize summary service
        summary_service = ConversationSummaryService()

        # Generate summary
        try:
            summary_data = await summary_service.generate_summary(
                messages=messages,
                conversation_type=conversation.conversation_type,
                persona_name=persona.name,
                max_tokens=300,
            )

            # Cache the summary in database (normalize key_topics to ensure string format)
            generation_time = datetime.now(timezone.utc)
            normalized_key_topics = _normalize_key_topics(summary_data["key_topics"])
            conversation.ai_summary = summary_data["summary"]
            conversation.summary_metadata = {
                "key_topics": normalized_key_topics,
                "sentiment": summary_data["sentiment"],
                "message_count": message_count,
                "persona_name": persona.name,
            }
            conversation.summary_generated_at = generation_time
            await session.commit()

            logger.info(
                f"✅ Successfully generated and cached summary for conversation {conversation_id} "
                f"({message_count} messages, type: {conversation.conversation_type})"
            )

            return ConversationSummaryResult(
                conversation_id=str(conversation.id),
                summary=summary_data["summary"],
                key_topics=normalized_key_topics,
                sentiment=summary_data["sentiment"],
                message_count=message_count,
                conversation_type=conversation.conversation_type,
                generated_at=generation_time,
            )

        except Exception as summary_error:
            # Capture in Sentry with enhanced context
            capture_exception_with_context(
                summary_error,
                extra={
                    "conversation_id": str(conversation.id),
                    "message_count": message_count,
                    "conversation_type": conversation.conversation_type,
                    "persona_name": persona.name,
                    "persona_id": str(persona.id),
                    "error_type": type(summary_error).__name__,
                    "has_cached_summary": bool(conversation.ai_summary),
                },
                tags={
                    "component": "conversation_summary",
                    "operation": "generate_summary",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            logger.error(f"❌ Error generating summary: {summary_error}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate conversation summary. Please try again later.",
            )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "conversation_id": conversation_id,
            },
            tags={
                "component": "conversation_summary",
                "operation": "get_conversation_summary",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Error in conversation summary endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# =============================================================================
# CONVERSATION ATTACHMENTS - Dashboard Endpoints
# =============================================================================


from pydantic import BaseModel
from sqlalchemy import select


class ConversationAttachmentResponse(BaseModel):
    """Response model for conversation attachment"""

    id: str
    filename: str
    file_type: str
    file_size: int
    mime_type: str
    s3_url: str
    extraction_status: str
    extraction_method: str | None = None
    message_index: int | None = None
    uploaded_at: str
    processed_at: str | None = None
    metadata: dict = {}


class ConversationAttachmentsListResponse(BaseModel):
    """Response model for list of conversation attachments"""

    conversation_id: str
    attachments: List[ConversationAttachmentResponse]
    total_count: int


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=ConversationAttachmentsListResponse,
)
async def get_conversation_attachments(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: Union[User, dict] = Depends(get_user_or_service),
):
    """
    Get all attachments for a specific conversation.

    This endpoint retrieves all file attachments (PDFs, images) associated
    with a conversation for display in the dashboard.

    Args:
        conversation_id: UUID of the conversation

    Returns:
        ConversationAttachmentsListResponse with list of attachments
    """
    try:
        # Get conversation to verify it exists and get session_token
        repo = ConversationRepository(session)
        conversation = await repo.get_by_id(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get attachments by session_id (which is the session_token)
        if conversation.session_id:
            stmt = (
                select(ConversationAttachment)
                .where(ConversationAttachment.session_token == conversation.session_id)
                .order_by(ConversationAttachment.uploaded_at.asc())
            )
            result = await session.execute(stmt)
            attachments = result.scalars().all()
        else:
            attachments = []

        # Format response
        attachment_responses = [
            ConversationAttachmentResponse(
                id=str(a.id),
                filename=a.original_filename,
                file_type=a.file_type,
                file_size=a.file_size,
                mime_type=a.mime_type,
                s3_url=a.s3_url,
                extraction_status=a.extraction_status,
                extraction_method=a.extraction_method,
                message_index=a.message_index,
                uploaded_at=a.uploaded_at.isoformat() if a.uploaded_at else "",
                processed_at=a.processed_at.isoformat() if a.processed_at else None,
                metadata=a.attachment_metadata or {},
            )
            for a in attachments
        ]

        logger.info(f"Retrieved {len(attachments)} attachments for conversation {conversation_id}")

        return ConversationAttachmentsListResponse(
            conversation_id=str(conversation_id),
            attachments=attachment_responses,
            total_count=len(attachment_responses),
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={"conversation_id": str(conversation_id)},
            tags={
                "component": "conversation_attachments",
                "operation": "get_conversation_attachments",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"Error getting conversation attachments: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve attachments")


# =============================================================================
# Internal: Post-processing handoff from LiveKit agent
# =============================================================================


async def _run_postprocessing(
    persona_id: UUID,
    session_token: str,
    conversation_id: UUID,
    conversation_type: str,
    conversation_history: list,
    persona_name: str,
    workflow_session_id: UUID | None,
    workflow_extracted_fields: dict | None,
    workflow_context: dict | None,
    workflow_is_active: bool,
    captured_lead_data: dict | None,
):
    """Background task: AI summary, email, webhook, and lead scoring.

    Runs in the FastAPI process after the LiveKit agent has exited.
    All services create their own DB sessions.
    """
    from app.services.conversation_summary_email_service import (
        send_conversation_summary_async,
    )

    try:
        # 1. Best-effort workflow completion (>=70% progress)
        if workflow_session_id and workflow_is_active:
            try:
                from shared.database.models.database import async_session_maker
                from shared.database.repositories.workflow_repository import (
                    WorkflowRepository,
                )

                async with async_session_maker() as db_session:
                    workflow_repo = WorkflowRepository(db_session)
                    ws = await workflow_repo.get_session_by_id(workflow_session_id)

                    if (
                        ws
                        and ws.status == "in_progress"
                        and (ws.progress_percentage or 0) >= 70
                        and ws.extracted_fields
                    ):
                        from datetime import datetime as dt
                        from datetime import timezone as tz

                        logger.info(
                            f"Best-effort completion: session {ws.id} at "
                            f"{ws.progress_percentage}%"
                        )
                        ws.status = "completed"
                        ws.completed_at = dt.now(tz.utc)
                        ws.updated_at = dt.now(tz.utc)
                        await db_session.commit()
                        workflow_extracted_fields = ws.extracted_fields
            except Exception as e:
                logger.error(f"Best-effort workflow completion failed: {e}")
                capture_exception_with_context(
                    e,
                    extra={"workflow_session_id": str(workflow_session_id)},
                    tags={
                        "component": "conversation_postprocess",
                        "operation": "best_effort_completion",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )

        # 2. AI summary + email
        if session_token:
            try:
                email_sent = await send_conversation_summary_async(
                    persona_id=persona_id,
                    session_id=session_token,
                    min_message_count=3,
                    conversation_type=conversation_type,
                )
                logger.info(
                    f"Summary email {'sent' if email_sent else 'not sent'} "
                    f"for session {session_token}"
                )
            except Exception as e:
                logger.error(f"Summary email failed: {e}")
                capture_exception_with_context(
                    e,
                    extra={"session_token": session_token},
                    tags={
                        "component": "conversation_postprocess",
                        "operation": "send_summary_email",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )

        # 3. Webhook
        try:
            from shared.database.models.database import Conversation as ConversationModel
            from shared.database.models.database import async_session_maker

            summary_data = None
            async with async_session_maker() as db_session:
                conv = await db_session.get(ConversationModel, conversation_id)
                if conv and conv.summary_metadata:
                    summary_data = conv.summary_metadata

            if not summary_data and len(conversation_history) >= 3:
                summary_service = ConversationSummaryService()
                summary_data = await summary_service.generate_structured_summary(
                    messages=conversation_history,
                    conversation_type=conversation_type,
                    persona_name=persona_name,
                )

            lead_data = None
            if captured_lead_data:
                lead_data = {
                    "name": captured_lead_data.get("contact_name"),
                    "email": captured_lead_data.get("contact_email"),
                    "phone": captured_lead_data.get("contact_phone"),
                }

            from app.services.webhook_service import WebhookService

            webhook_service = WebhookService()
            try:
                await webhook_service.send_event(
                    persona_id=persona_id,
                    event_type="conversation.finished",
                    event_data={
                        "conversation_id": str(conversation_id),
                        "conversation_type": conversation_type,
                        "message_count": len(conversation_history),
                        "lead": lead_data,
                        "summary": summary_data,
                        "transcript": conversation_history,
                    },
                )
            finally:
                await webhook_service.close()
        except Exception as e:
            logger.error(f"Summary/webhook failed: {e}")
            capture_exception_with_context(
                e,
                extra={"conversation_id": str(conversation_id)},
                tags={
                    "component": "conversation_postprocess",
                    "operation": "summary_and_webhook",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )

        # 4. Lead scoring
        if workflow_session_id and workflow_extracted_fields:
            try:
                from livekit.services.lead_scoring_service import score_lead_background

                await score_lead_background(
                    session_id=workflow_session_id,
                    extracted_fields=workflow_extracted_fields,
                    workflow_context=workflow_context,
                )
            except Exception as e:
                logger.error(f"Lead scoring failed: {e}")
                capture_exception_with_context(
                    e,
                    extra={"workflow_session_id": str(workflow_session_id)},
                    tags={
                        "component": "conversation_postprocess",
                        "operation": "lead_scoring",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )

        logger.info(f"Post-processing complete for conversation {conversation_id}")

    except Exception as e:
        logger.error(f"Post-processing failed: {e}", exc_info=True)
        capture_exception_with_context(
            e,
            extra={
                "persona_id": str(persona_id),
                "conversation_id": str(conversation_id),
            },
            tags={
                "component": "conversation_postprocess",
                "operation": "run_postprocessing",
                "severity": "high",
                "user_facing": "false",
            },
        )


@router.post("/internal/conversation-postprocess", include_in_schema=False)
async def conversation_postprocess(
    request: ConversationPostProcessRequest,
    background_tasks: BackgroundTasks,
):
    """Internal endpoint called by LiveKit agent during shutdown.

    Accepts all data needed for post-processing and runs it as a background
    task so the agent process can exit immediately.
    """
    background_tasks.add_task(
        _run_postprocessing,
        persona_id=request.persona_id,
        session_token=request.session_token,
        conversation_id=request.conversation_id,
        conversation_type=request.conversation_type,
        conversation_history=request.conversation_history,
        persona_name=request.persona_name,
        workflow_session_id=request.workflow_session_id,
        workflow_extracted_fields=request.workflow_extracted_fields,
        workflow_context=request.workflow_context,
        workflow_is_active=request.workflow_is_active,
        captured_lead_data=request.captured_lead_data,
    )
    return {"status": "accepted"}
