"""
Enhanced session tracking with email prompting and conversation merging
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user
from app.auth.optimized_middleware import require_auth_optimized, require_jwt_or_api_key
from shared.database.models.conversation_attachment import (
    ConversationAttachment,
    ExtractionMethod,
    ExtractionStatus,
)
from shared.database.models.database import Conversation, Persona, UserSession, get_session
from shared.database.models.persona import (
    EmailProvisionResponse,
    EmailRequest,
    LeadCaptureRequest,
    LeadCaptureResponse,
    SessionInitResponse,
    SpecialChatRequest,
    TrackedChatRequest,
)
from shared.database.models.user import User
from shared.database.repositories.persona_repository import PersonaRepository
from shared.generation.generator import ResponseGenerator
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.rag.rag_singleton import get_rag_manager
from shared.services.ocr_service import get_ocr_service
from shared.services.s3_service import get_s3_service
from shared.services.text_usage_service import TextUsageService


class VoiceTranscriptMessage(BaseModel):
    speaker: str  # 'user' or 'assistant'
    text: str
    timestamp: str
    isComplete: bool


class SaveVoiceTranscriptRequest(BaseModel):
    session_token: str
    transcript_messages: List[VoiceTranscriptMessage]


router = APIRouter(prefix="/api/v1", tags=["Enhanced Sessions"])
logger = logging.getLogger(__name__)

# Initialize response generator
response_generator = ResponseGenerator()

# Request deduplication tracking
_active_requests: Dict[str, asyncio.Event] = {}
_request_lock = asyncio.Lock()


@router.post("/personas/username/{username}/init-session", response_model=SessionInitResponse)
async def initialize_session(
    username: str,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """
    Initialize a session for a persona by username

    Supports both authenticated (JWT) and anonymous (API key) sessions:
    - If JWT token (myclone_token cookie) is present: creates identified session with user's email
    - If only API key: creates anonymous session with temporary email
    """
    try:
        # Get persona by User.username + persona_name
        persona = await PersonaRepository.get_by_username_and_persona(
            session, username, persona_name
        )
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Expert '{username}' (persona: {persona_name}) not found"
            )

        # Check authentication type
        auth_type = auth_result.get("type")
        auth_data = auth_result.get("data", {})

        # Determine session type based on authentication
        is_authenticated = auth_type == "jwt"
        session_token = str(uuid4())

        if is_authenticated:
            # JWT authenticated - use user's email
            authenticated_user = auth_data.get("user")
            user_email = authenticated_user.email
            session_metadata = {
                "message_count": 0,
                "email_prompted": False,
                "email_provided": True,
                "is_anonymous": False,
                "created_via": "username_session_init",
                "authenticated_user_id": str(authenticated_user.id),
                "auth_type": "jwt",
            }
            logger.info(f"✅ Creating authenticated session for {username} with user {user_email}")
        else:
            # API key or disabled auth - create anonymous session
            user_email = f"anon_{session_token[:8]}@session.local"
            session_metadata = {
                "message_count": 0,
                "email_prompted": False,
                "email_provided": False,
                "is_anonymous": True,
                "created_via": "username_session_init",
                "auth_type": auth_type,
            }
            logger.info(f"✅ Creating anonymous session for {username}: {session_token[:8]}...")

        # Insert new session
        user_session = UserSession(
            session_token=session_token,
            user_email=user_email,
            persona_id=persona.id,
            session_metadata=session_metadata,
            is_active=True,
        )

        session.add(user_session)
        await session.commit()
        # Refresh user_session to get updated data without holding connection
        await session.refresh(user_session)
        # Explicitly expunge from session to prevent connection leaks
        session.expunge(user_session)

        # 🔄 REFRESH RAG INDEX - Load latest embeddings from database
        try:
            logger.info(f"🔄 Refreshing RAG index for persona {persona.id} on session init...")
            rag_manager = await get_rag_manager()
            refresh_success = await rag_manager.refresh_persona_index(persona.id)
            if refresh_success:
                logger.info(f"✅ RAG index refreshed successfully for persona {persona.id}")
            else:
                logger.warning(f"⚠️ RAG index refresh failed for persona {persona.id}")
        except Exception as refresh_error:
            logger.error(f"❌ Error refreshing RAG index: {refresh_error}")
            # Don't fail session creation if refresh fails
            pass

        # Note: auth_token removed (no longer using session tokens with simplified auth)
        auth_token = None
        auth_expires_at = None

        return SessionInitResponse(
            session_token=session_token,
            auth_token=auth_token,
            persona_id=str(persona.id),
            persona_name=persona.persona_name,
            is_anonymous=not is_authenticated,
            auth_expires_at=auth_expires_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/personas/username/{username}/stream-chat")
async def stream_chat_with_tracking(
    username: str,
    request: TrackedChatRequest,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_auth_optimized),
):
    """
    Stream chat response with enhanced session tracking and email prompting

    **DEPRECATED**: This endpoint is deprecated and will be removed in a future version.
    Use LiveKit text-only mode for text chat instead.
    """
    try:
        # Create request hash for deduplication
        request_data = f"{request.session_token}:{request.message}:{request.temperature}"
        request_hash = hashlib.md5(request_data.encode()).hexdigest()[:12]

        # Check for duplicate request
        async with _request_lock:
            if request_hash in _active_requests:
                logger.warning(
                    f"🚫 Duplicate request detected, waiting for completion: {request_hash}"
                )
                # Wait for the existing request to complete
                await _active_requests[request_hash].wait()
                logger.info("🚫 Duplicate request completed, responding with 429")
                raise HTTPException(status_code=429, detail="Duplicate request, please wait")

            # Mark request as active
            _active_requests[request_hash] = asyncio.Event()
            logger.info(f"🔄 Processing new request: {request_hash}")

        try:
            # Get session by token
            stmt = select(UserSession).where(UserSession.session_token == request.session_token)
            result = await session.execute(stmt)
            user_session = result.scalar_one_or_none()

            if not user_session:
                raise HTTPException(status_code=404, detail="Session not found")

            if not user_session.is_valid:
                raise HTTPException(status_code=401, detail="Session expired or inactive")

            # Check text usage limit before allowing message
            text_usage_service = TextUsageService(session)
            can_send, remaining, limit = await text_usage_service.check_owner_text_limit(
                persona_id=user_session.persona_id
            )

            if not can_send:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "text_limit_exceeded",
                        "message": f"Monthly text chat limit reached ({limit} messages)",
                        "messages_used": limit - remaining if limit > 0 else 0,
                        "messages_limit": limit,
                    },
                )

            # Get current message count from metadata
            current_metadata = user_session.session_metadata or {}
            current_count = current_metadata.get("message_count", 0)
            new_count = current_count + 1

            # Update message count in session
            updated_metadata = current_metadata.copy()
            updated_metadata["message_count"] = new_count
            updated_metadata["last_message_at"] = datetime.utcnow().isoformat()

            stmt = (
                update(UserSession)
                .where(UserSession.session_token == request.session_token)
                .values(session_metadata=updated_metadata)
            )
            await session.execute(stmt)
            await session.commit()

            logger.info(f"💬 Message {new_count} from session {request.session_token[:8]}...")

            # Check if we should prompt for email (after 3rd message)
            should_prompt = (
                new_count == 3
                and not current_metadata.get("email_prompted", False)
                and current_metadata.get("is_anonymous", True)
            )

            # Fetch attachments if provided and build message with context
            message_with_context = request.message
            attachment_data = []  # For saving to conversation

            if request.attachment_ids:
                # Limit to 5 attachments
                attachment_ids_raw = request.attachment_ids[:5]
                logger.info(f"📎 Fetching {len(attachment_ids_raw)} attachments for message")

                # Validate UUIDs before querying (fix invalid UUID handling)
                from uuid import UUID as PyUUID

                valid_uuids = []
                for att_id in attachment_ids_raw:
                    try:
                        valid_uuids.append(PyUUID(att_id))
                    except (ValueError, TypeError) as uuid_error:
                        logger.warning(f"⚠️ Invalid attachment UUID '{att_id}': {uuid_error}")

                attachment_contexts = []

                if valid_uuids:
                    # Bulk fetch attachments (fix N+1 query)
                    stmt = select(ConversationAttachment).where(
                        ConversationAttachment.id.in_(valid_uuids),
                        ConversationAttachment.session_token == request.session_token,
                    )
                    result = await session.execute(stmt)
                    attachments = result.scalars().all()

                    for attachment in attachments:
                        if attachment.extracted_text:
                            # Build context from attachment
                            file_label = (
                                "PDF Document" if attachment.file_type == "pdf" else "Image"
                            )
                            attachment_contexts.append(
                                f"[{file_label}: {attachment.original_filename}]\n"
                                f"{attachment.extracted_text}"
                            )
                            # Store attachment info for conversation saving
                            attachment_data.append(
                                {
                                    "id": str(attachment.id),
                                    "filename": attachment.original_filename,
                                    "file_type": attachment.file_type,
                                    "file_size": attachment.file_size,
                                    "s3_url": attachment.s3_url,
                                }
                            )
                            logger.info(
                                f"✅ Loaded attachment: {attachment.original_filename} "
                                f"({len(attachment.extracted_text)} chars)"
                            )
                        else:
                            logger.warning(
                                f"⚠️ Attachment {attachment.id} has no extracted text "
                                f"(status: {attachment.extraction_status})"
                            )

                # Append attachment context to message
                if attachment_contexts:
                    attachment_section = "\n\n---\n**Attached Content:**\n\n" + "\n\n".join(
                        attachment_contexts
                    )
                    message_with_context = request.message + attachment_section
                    logger.info(
                        f"📎 Message augmented with {len(attachment_contexts)} attachment(s)"
                    )

            # Stream the chat response
            async def generate_tracked_response():
                full_response = ""
                sources = []
                try:
                    # Generate actual response using ResponseGenerator
                    response_data = await response_generator.generate_response(
                        session=session,
                        persona_id=user_session.persona_id,
                        message=message_with_context,  # Use message with attachment context
                        session_id=request.session_token,
                        temperature=request.temperature,
                        stream=True,
                    )

                    # Stream the AI-generated response and collect full response
                    async for chunk in response_data["response"]:
                        # Check if this is a sources chunk (from the modified streaming)
                        if isinstance(chunk, dict) and chunk.get("type") == "sources":
                            sources = chunk.get("sources", [])
                            # Send sources as a separate event
                            sources_data = {"type": "sources", "sources": sources}
                            yield f"data: {json.dumps(sources_data)}\n\n"
                        else:
                            # Regular content chunk
                            full_response += chunk
                            chunk_data = {"type": "content", "chunk": chunk}
                            yield f"data: {json.dumps(chunk_data)}\n\n"

                    # Save conversation after streaming is complete
                    if full_response:
                        # Use a separate session for conversation saving to avoid transaction conflicts
                        from shared.database.models.database import async_session_maker

                        async with async_session_maker() as conv_session:
                            try:
                                await response_generator.save_conversation(
                                    session=conv_session,
                                    persona_id=user_session.persona_id,
                                    session_id=request.session_token,
                                    user_message=request.message,
                                    assistant_response=full_response,
                                    sources=sources,  # Pass the collected sources
                                    attachments=attachment_data if attachment_data else None,
                                )
                                await conv_session.commit()

                                # Record text message usage after successful save
                                try:
                                    text_svc = TextUsageService(conv_session)
                                    await text_svc.record_message(user_session.persona_id)
                                    await conv_session.commit()
                                except Exception as usage_error:
                                    logger.error(f"Error recording text usage: {usage_error}")
                                    # Don't fail the chat if usage tracking fails
                            except Exception as conv_error:
                                logger.error(f"Error saving conversation: {conv_error}")
                                capture_exception_with_context(
                                    conv_error,
                                    extra={
                                        "session_token": request.session_token[:8],
                                        "persona_id": str(user_session.persona_id),
                                        "has_attachments": bool(attachment_data),
                                    },
                                    tags={
                                        "component": "chat",
                                        "operation": "save_conversation_streaming",
                                        "severity": "high",
                                        "user_facing": "false",
                                    },
                                )
                                await conv_session.rollback()
                            finally:
                                # Ensure session is properly closed
                                await conv_session.close()

                except Exception as e:
                    logger.error(f"Error generating response: {e}")
                    # Fallback to a simple error message
                    error_chunk = {
                        "type": "content",
                        "chunk": "I'm having trouble generating a response right now. Please try again.",
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"

                # Add email prompt if needed
                if should_prompt:
                    email_prompt = {
                        "type": "email_prompt",
                        "message": "💌 Want to save your conversation? Provide your email to continue later!",
                        "message_count": new_count,
                        "prompt_reason": "message_threshold",
                    }
                    yield f"data: {json.dumps(email_prompt)}\n\n"

                    # Mark as prompted in database
                    prompted_metadata = updated_metadata.copy()
                    prompted_metadata["email_prompted"] = True
                    prompted_metadata["email_prompted_at"] = datetime.utcnow().isoformat()

                    stmt = (
                        update(UserSession)
                        .where(UserSession.session_token == request.session_token)
                        .values(session_metadata=prompted_metadata)
                    )
                    await session.execute(stmt)
                    await session.commit()

                    logger.info(
                        f"📧 Email prompt sent to session {request.session_token[:8]} after {new_count} messages"
                    )

                # End stream
                yield f"data: {json.dumps({'type': 'complete', 'session_token': request.session_token})}\n\n"

            return StreamingResponse(
                generate_tracked_response(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream",
                },
            )

        finally:
            # Mark request as completed and clean up
            async with _request_lock:
                if request_hash in _active_requests:
                    _active_requests[request_hash].set()  # Signal completion
                    del _active_requests[request_hash]  # Remove from active requests
                    logger.info(f"✅ Request completed and cleaned up: {request_hash}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in tracked streaming chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/personas/username/{username}/special-stream-chat")
async def special_stream_chat(
    username: str,
    request: SpecialChatRequest,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_auth_optimized),
):
    """Stream chat response for special PDF evaluation (e.g., resume review) or regular chat if no PDF provided"""
    try:
        # Validate inputs
        if not request.message:
            raise HTTPException(status_code=400, detail="Please provide a message")

        # Get session by token
        stmt = select(UserSession).where(UserSession.session_token == request.session_token)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if not user_session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not user_session.is_valid:
            raise HTTPException(status_code=401, detail="Session expired or inactive")

        if request.pdf_url:
            logger.info(f"📄 Special chat request for PDF: {request.pdf_url[:50]}...")
        else:
            logger.info(
                f"💬 Special chat request (no PDF) for session {request.session_token[:8]}..."
            )

        # Stream the chat response
        async def generate_special_response():
            full_response = ""
            try:
                # Generate response using ResponseGenerator's special method
                response_data = await response_generator.generate_response_special(
                    session=session,
                    persona_id=user_session.persona_id,
                    message=request.message,
                    pdf_url=request.pdf_url,  # Can be None
                    session_id=request.session_token,
                    temperature=request.temperature,
                    stream=True,
                )

                # Stream the AI-generated response
                async for chunk in response_data["response"]:
                    full_response += chunk
                    chunk_data = {"type": "content", "chunk": chunk}
                    yield f"data: {json.dumps(chunk_data)}\n\n"

                # Save conversation after streaming is complete
                if full_response:
                    from shared.database.models.database import async_session_maker

                    # Build user message with optional PDF reference
                    pdf_url = None
                    markdown_text = None
                    user_msg = request.message
                    if request.pdf_url:
                        user_msg = f"{request.message} [PDF: {request.pdf_url}]"
                        pdf_url = request.pdf_url
                        markdown_text = response_data.get("markdown_text")

                    async with async_session_maker() as conv_session:
                        try:
                            await response_generator.save_conversation_special(
                                session=conv_session,
                                persona_id=user_session.persona_id,
                                session_id=request.session_token,
                                user_message=user_msg,
                                assistant_response=full_response,
                                markdown_content=markdown_text,
                                sources=[],
                                attachment_url=pdf_url,
                            )
                            await conv_session.commit()
                        except Exception as conv_error:
                            logger.error(f"Error saving conversation: {conv_error}")
                            await conv_session.rollback()
                        finally:
                            await conv_session.close()

            except Exception as e:
                logger.error(f"Error generating special response: {e}")
                error_chunk = {
                    "type": "content",
                    "chunk": "I'm having trouble processing your document. Please try again.",
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"

            # End stream
            yield f"data: {json.dumps({'type': 'complete', 'session_token': request.session_token})}\n\n"

        return StreamingResponse(
            generate_special_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in special streaming chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_token}/provide-email", response_model=EmailProvisionResponse)
async def provide_email(
    session_token: str,
    request: EmailRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    """
    Convert anonymous session to identified session with email

    This endpoint supports two flows:
    1. Authenticated user (JWT cookie present): Link session to authenticated user
    2. Anonymous user (no JWT): Just update session with email (legacy flow)

    For OTP authentication flow:
    - User enters email in popup
    - Frontend calls /auth/request-otp (creates/verifies user, sends OTP)
    - User enters OTP
    - Frontend calls /auth/verify-otp (sets JWT cookie)
    - Frontend calls this endpoint to link authenticated user to session
    """
    try:
        # Get current session
        stmt = select(UserSession).where(UserSession.session_token == session_token)
        result = await session.execute(stmt)
        current_session = result.scalar_one_or_none()

        if not current_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Determine user email (from authenticated user or request)
        if current_user:
            # Authenticated user flow (OTP or other auth methods)
            user_email = current_user.email
            user_id = current_user.id
            logger.info(f"🔐 Authenticated user linking session: {user_email} (user_id: {user_id})")
        else:
            # Legacy anonymous flow (no authentication)
            user_email = request.email
            user_id = None
            logger.info(f"📧 Anonymous email provision (legacy): {user_email}")

        # Check for existing user sessions with this email and persona
        existing_stmt = (
            select(UserSession)
            .where(
                UserSession.user_email == user_email,
                UserSession.persona_id == current_session.persona_id,
                ~UserSession.user_email.like("anon_%@session.local"),
            )
            .order_by(UserSession.created_at.desc())
        )

        existing_result = await session.execute(existing_stmt)
        existing_sessions = existing_result.scalars().all()

        has_previous_conversations = len(existing_sessions) > 0

        # Merge conversation histories from anonymous sessions
        if has_previous_conversations:
            # Update conversation records to use real email
            conversation_update_values = {"user_email": user_email}
            # Note: Conversation table doesn't have user_id column, only user_email

            conversation_update = (
                update(Conversation)
                .where(Conversation.session_id == current_session.session_token)
                .values(**conversation_update_values)
            )
            await session.execute(conversation_update)

            logger.info(
                f"🔗 Merged conversations for {user_email} from session {session_token[:8]}"
            )

        # Update session with real email, fullname, phone, and mark as identified
        original_email = current_session.user_email
        updated_metadata = current_session.session_metadata.copy()
        updated_metadata.update(
            {
                "email_provided": True,
                "email_provided_at": datetime.utcnow().isoformat(),
                "is_anonymous": False,
                "original_anonymous_email": original_email,
                "conversion_type": (
                    "anonymous_to_authenticated" if current_user else "anonymous_to_identified"
                ),
                "fullname": request.fullname,
                "phone": request.phone,
            }
        )

        # If authenticated user, add user_id to metadata
        if user_id:
            updated_metadata["authenticated_user_id"] = str(user_id)
            updated_metadata["auth_type"] = "jwt"

        # Get persona to check email capture requirements
        persona_stmt = select(Persona).where(Persona.id == current_session.persona_id)
        persona_result = await session.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")

        # Validate required fields based on persona settings
        if persona.email_capture_require_fullname and not request.fullname:
            raise HTTPException(status_code=400, detail="Full name is required for this persona")
        if persona.email_capture_require_phone and not request.phone:
            raise HTTPException(status_code=400, detail="Phone number is required for this persona")

        # Transaction: Update session and conversations atomically
        try:
            # Step 1: Update UserSession with email and metadata
            stmt = (
                update(UserSession)
                .where(UserSession.session_token == session_token)
                .values(user_email=user_email, session_metadata=updated_metadata)
            )
            await session.execute(stmt)

            # Step 2: Update conversation records with real email, fullname, phone, and user_id
            conversation_update_values = {
                "user_email": user_email,
                "user_fullname": request.fullname,
                "user_phone": request.phone,
            }
            # If authenticated user, also link via user_id (permanent link, survives email changes)
            if user_id:
                conversation_update_values["user_id"] = user_id

            conversation_update = (
                update(Conversation)
                .where(Conversation.session_id == current_session.session_token)
                .values(**conversation_update_values)
            )
            await session.execute(conversation_update)

            # Step 3: Commit both updates atomically
            await session.commit()

        except Exception as transaction_error:
            # Rollback on any error to ensure data consistency
            await session.rollback()
            capture_exception_with_context(
                transaction_error,
                extra={
                    "session_token": session_token,
                    "user_email": user_email,
                    "user_id": str(user_id) if user_id else None,
                },
                tags={
                    "component": "sessions",
                    "operation": "link_session_transaction",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            logger.error(
                f"Transaction failed while linking session {session_token}: {transaction_error}"
            )
            raise HTTPException(status_code=500, detail="Failed to link session. Please try again.")

        if current_user:
            logger.info(
                f"✅ Linked authenticated user to session: {user_email} (user_id: {user_id})"
            )
        else:
            logger.info(f"✅ Converted anonymous session to identified: {user_email}")

        return EmailProvisionResponse(
            success=True,
            email=user_email,
            previous_conversations=has_previous_conversations,
            merged_sessions=len(existing_sessions),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error providing email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_token}/capture-lead", response_model=LeadCaptureResponse)
async def capture_lead(
    session_token: str,
    request: LeadCaptureRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Capture lead info from AI-driven conversation and create/link a visitor user.

    This endpoint is called by the frontend after the AI agent captures
    name, email, and phone from the visitor during conversation. It:

    1. Creates a new visitor User (or finds existing by email)
    2. Links the session and conversations to the user
    3. Sets an HTTP-only JWT cookie for future recognition

    No OTP verification required — email_confirmed is set to False.
    """
    import secrets
    import string

    from app.services.linkedin_oauth_service import LinkedInOAuthService
    from shared.config import settings
    from shared.database.models.user import AccountType, OnboardingStatus
    from shared.database.repositories.user_repository import UserRepository

    try:
        # Step 1: Find and validate the session
        stmt = select(UserSession).where(UserSession.session_token == session_token)
        result = await session.execute(stmt)
        current_session = result.scalar_one_or_none()

        if not current_session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not current_session.is_valid:
            raise HTTPException(status_code=400, detail="Session is expired or inactive")

        # Step 2: Check if a user with this email already exists
        existing_user = await UserRepository.get_by_email(session, request.email)
        is_new_user = existing_user is None

        if existing_user:
            user = existing_user
            # Update fields that may have arrived late (e.g., phone on re-fire)
            if request.phone and not user.phone:
                user.phone = request.phone
            if request.fullname and not user.fullname:
                user.fullname = request.fullname
            logger.info(
                f"🔗 Found existing user for lead capture: {request.email} (user_id: {user.id})"
            )
        else:
            # Step 3: Create a new visitor user
            # Generate unique username
            username = None
            for _ in range(10):
                random_suffix = "".join(
                    secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)
                )
                candidate = f"visitor_{random_suffix}"
                if not await UserRepository.get_by_username(session, candidate):
                    username = candidate
                    break
            if not username:
                username = f"visitor_{str(uuid4())[:8]}"

            # Derive fullname from email if not provided
            fullname = request.fullname
            if not fullname:
                email_prefix = request.email.split("@")[0]
                fullname = email_prefix.replace(".", " ").replace("_", " ").title()

            user = await UserRepository.create_user(
                session=session,
                email=request.email,
                fullname=fullname,
                username=username,
                phone=request.phone,
                email_confirmed=False,
                account_type=AccountType.VISITOR,
                onboarding_status=OnboardingStatus.FULLY_ONBOARDED,
            )

            # Create free tier subscription
            from shared.database.models.tier_plan import SubscriptionStatus, UserSubscription

            try:
                free_tier_subscription = UserSubscription(
                    user_id=user.id,
                    tier_id=0,
                    status=SubscriptionStatus.ACTIVE,
                )
                session.add(free_tier_subscription)
                await session.flush()
            except Exception as sub_error:
                logger.error(f"Failed to create subscription for visitor {user.id}: {sub_error}")
                # Non-fatal — user is still created

            logger.info(
                f"👤 Created visitor user for lead capture: {request.email} (user_id: {user.id})"
            )

        # Step 4: Check for previous conversations with this persona
        existing_stmt = (
            select(UserSession)
            .where(
                UserSession.user_email == request.email,
                UserSession.persona_id == current_session.persona_id,
                ~UserSession.user_email.like("anon_%@session.local"),
            )
            .order_by(UserSession.created_at.desc())
        )
        existing_result = await session.execute(existing_stmt)
        existing_sessions = existing_result.scalars().all()
        has_previous_conversations = len(existing_sessions) > 0

        # Step 5: Update session and conversations atomically
        try:
            # Update UserSession
            original_email = current_session.user_email
            updated_metadata = (current_session.session_metadata or {}).copy()
            updated_metadata.update(
                {
                    "email_provided": True,
                    "email_provided_at": datetime.utcnow().isoformat(),
                    "is_anonymous": False,
                    "original_anonymous_email": original_email,
                    "conversion_type": "lead_capture",
                    "fullname": request.fullname,
                    "phone": request.phone,
                    "authenticated_user_id": str(user.id),
                    "auth_type": "lead_capture",
                }
            )

            session_update = (
                update(UserSession)
                .where(UserSession.session_token == session_token)
                .values(user_email=request.email, session_metadata=updated_metadata)
            )
            await session.execute(session_update)

            # Update Conversation records
            conversation_update = (
                update(Conversation)
                .where(Conversation.session_id == current_session.session_token)
                .values(
                    user_email=request.email,
                    user_fullname=request.fullname,
                    user_phone=request.phone,
                    user_id=user.id,
                )
            )
            await session.execute(conversation_update)

            await session.commit()

        except Exception as tx_error:
            await session.rollback()
            capture_exception_with_context(
                tx_error,
                extra={
                    "session_token": session_token,
                    "user_email": request.email,
                    "user_id": str(user.id),
                },
                tags={
                    "component": "sessions",
                    "operation": "capture_lead_transaction",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            logger.error(
                f"Transaction failed during lead capture for session {session_token}: {tx_error}"
            )
            raise HTTPException(status_code=500, detail="Failed to capture lead. Please try again.")

        # Step 6: Generate JWT and set cookie
        jwt_token = LinkedInOAuthService.create_jwt_token(
            user_id=str(user.id),
            email=user.email,
        )

        response.set_cookie(
            key="myclone_token",
            value=jwt_token,
            httponly=True,
            secure=settings.environment in ["production", "staging"],
            samesite="lax",
            max_age=60 * 60 * 24 * settings.jwt_expiration_days,
            domain=settings.cookie_domain,
        )

        logger.info(
            f"✅ Lead captured for session {session_token[:8]}: "
            f"{request.email} (user_id: {user.id}, new_user: {is_new_user})"
        )

        return LeadCaptureResponse(
            success=True,
            email=request.email,
            user_id=str(user.id),
            is_new_user=is_new_user,
            previous_conversations=has_previous_conversations,
            token=jwt_token,
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "session_token": session_token,
                "email": request.email,
            },
            tags={
                "component": "sessions",
                "operation": "capture_lead",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Error capturing lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_token}/status")
async def get_session_status(session_token: str, session: AsyncSession = Depends(get_session)):
    """Get current session status and metadata"""
    try:
        stmt = select(UserSession).where(UserSession.session_token == session_token)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if not user_session:
            raise HTTPException(status_code=404, detail="Session not found")

        metadata = user_session.session_metadata or {}

        return {
            "session_token": session_token,
            "user_email": user_session.user_email,
            "persona_id": str(user_session.persona_id),
            "is_active": user_session.is_active,
            "is_valid": user_session.is_valid,
            "is_anonymous": metadata.get("is_anonymous", True),
            "message_count": metadata.get("message_count", 0),
            "email_prompted": metadata.get("email_prompted", False),
            "email_provided": metadata.get("email_provided", False),
            "created_at": user_session.created_at.isoformat(),
            "last_accessed": (
                user_session.last_accessed.isoformat() if user_session.last_accessed else None
            ),
            "expires_at": user_session.expires_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_token}/refresh-index")
async def refresh_session_index(
    session_token: str,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_auth_optimized),
):
    """
    Refresh the RAG index and retriever for a specific session.

    This endpoint updates the vector index cache with the latest embeddings from the database
    while preserving the chat history and conversation memory for the session.

    Use this when you want to ensure the chat is using the most recent data without
    starting a new session or losing chat context.
    """
    try:
        # Get session by token
        stmt = select(UserSession).where(UserSession.session_token == session_token)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if not user_session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not user_session.is_valid:
            raise HTTPException(status_code=401, detail="Session expired or inactive")

        persona_id = user_session.persona_id

        logger.info(
            f"🔄 Manual refresh requested for session {session_token[:8]}, persona {persona_id}"
        )

        # Refresh the RAG index and retriever
        try:
            rag_manager = await get_rag_manager()
            refresh_success = await rag_manager.refresh_persona_index(persona_id)

            if refresh_success:
                logger.info(f"✅ RAG index refreshed successfully for session {session_token[:8]}")

                # Update session metadata to track the refresh
                current_metadata = user_session.session_metadata or {}
                updated_metadata = current_metadata.copy()
                updated_metadata["last_index_refresh"] = datetime.utcnow().isoformat()
                updated_metadata["index_refresh_count"] = (
                    updated_metadata.get("index_refresh_count", 0) + 1
                )

                stmt = (
                    update(UserSession)
                    .where(UserSession.session_token == session_token)
                    .values(session_metadata=updated_metadata)
                )
                await session.execute(stmt)
                await session.commit()

                return {
                    "success": True,
                    "message": "Index and retriever refreshed successfully",
                    "session_token": session_token,
                    "persona_id": str(persona_id),
                    "chat_history_preserved": True,
                    "refresh_timestamp": updated_metadata["last_index_refresh"],
                }
            else:
                logger.warning(f"⚠️ RAG index refresh failed for session {session_token[:8]}")
                return {
                    "success": False,
                    "message": "Failed to refresh index",
                    "session_token": session_token,
                    "persona_id": str(persona_id),
                    "chat_history_preserved": True,
                }

        except Exception as refresh_error:
            logger.error(f"❌ Error refreshing RAG index: {refresh_error}")
            raise HTTPException(
                status_code=500, detail=f"Error refreshing index: {str(refresh_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in refresh_session_index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/personas/username/{username}/save-voice-transcript")
async def save_voice_transcript(
    username: str,
    request: SaveVoiceTranscriptRequest,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """Save voice conversation transcript to database"""
    try:
        # Get persona by User.username + persona_name
        persona = await PersonaRepository.get_by_username_and_persona(
            session, username, persona_name
        )
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Expert '{username}' (persona: {persona_name}) not found"
            )

        # Get user session to get user email
        session_stmt = select(UserSession).where(UserSession.session_token == request.session_token)
        session_result = await session.execute(session_stmt)
        user_session = session_result.scalar_one_or_none()

        if not user_session:
            logger.warning(f"No user session found for token: {request.session_token}")
            user_email = None
        else:
            user_email = user_session.user_email

        # Convert and validate transcript messages
        transcript_messages = []
        for msg in request.transcript_messages:
            # Validate speaker field
            if msg.speaker not in ["user", "assistant", "agent"]:
                logger.warning(f"Invalid speaker type: {msg.speaker}, skipping message")
                continue

            # Sanitize text content
            import html

            sanitized_text = html.escape(msg.text) if msg.text else ""

            transcript_messages.append(
                {
                    "speaker": msg.speaker,
                    "text": sanitized_text,
                    "timestamp": msg.timestamp,
                    "isComplete": msg.isComplete,
                }
            )

        # Save voice conversation using the generator's method
        success = await response_generator.save_voice_conversation(
            session=session,
            persona_id=persona.id,
            session_id=request.session_token,
            transcript_messages=transcript_messages,
            user_email=user_email,
        )

        if success:
            return {
                "success": True,
                "message": f"Saved {len(transcript_messages)} transcript messages",
                "session_token": request.session_token,
                "conversation_type": "voice",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save voice transcript")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving voice transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/personas/username/{username}/voice-conversations/{session_token}")
async def get_voice_conversation(
    username: str,
    session_token: str,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """Get voice conversation from database for debugging"""
    try:
        # Get persona by User.username + persona_name
        persona = await PersonaRepository.get_by_username_and_persona(
            session, username, persona_name
        )
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Expert '{username}' (persona: {persona_name}) not found"
            )

        # Get voice conversation
        conv_stmt = select(Conversation).where(
            Conversation.persona_id == persona.id,
            Conversation.session_id == session_token,
            Conversation.conversation_type == "voice",
        )
        conv_result = await session.execute(conv_stmt)
        conversation = conv_result.scalar_one_or_none()

        if not conversation:
            return {"found": False, "message": "No voice conversation found for this session"}

        return {
            "found": True,
            "conversation_id": str(conversation.id),
            "session_id": conversation.session_id,
            "conversation_type": conversation.conversation_type,
            "user_email": conversation.user_email,
            "message_count": len(conversation.messages or []),
            "messages": conversation.messages or [],
            "metadata": conversation.conversation_metadata,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting voice conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ChatPDFUploadResponse(BaseModel):
    """Response model for chat PDF upload"""

    success: bool
    message: str
    s3_url: str
    filename: str
    file_size: int


@router.post("/sessions/{session_token}/upload-pdf", response_model=ChatPDFUploadResponse)
async def upload_chat_pdf(
    session_token: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload a PDF file as a chat attachment.

    This endpoint uploads a PDF to S3 and returns the S3 URL that can be
    used as a reference in chat messages.

    Args:
        session_token: The chat session token
        file: The PDF file to upload

    Returns:
        ChatPDFUploadResponse with S3 URL and file metadata
    """
    file_content = None
    file_size = None

    try:
        # Validate session exists
        stmt = select(UserSession).where(UserSession.session_token == session_token)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if not user_session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not user_session.is_valid:
            raise HTTPException(status_code=401, detail="Session expired or inactive")

        # Validate file type - only allow PDF
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension != ".pdf":
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed for chat attachments",
            )

        # Validate content type
        content_type = file.content_type or "application/pdf"
        if content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail="Invalid content type. Only PDF is allowed",
            )

        # Check file size before reading if available (performance optimization)
        max_size = 50 * 1024 * 1024  # 50MB
        if hasattr(file, "size") and file.size and file.size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is 50MB, got {file.size} bytes",
            )

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size after reading (fallback validation)
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is 50MB, got {file_size} bytes",
            )

        # Validate PDF magic bytes
        if not file_content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")

        # Generate unique filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"

        # Upload to S3 using thread-safe directory parameter
        s3_service = get_s3_service()
        await s3_service.ensure_bucket_exists()
        await s3_service.upload_file(
            file_content=file_content,
            user_id=session_token,  # Use session_token as user_id for grouping
            filename=safe_filename,
            content_type="application/pdf",
            directory="chat-attachments",  # Thread-safe: pass as parameter
        )

        # Generate public HTTPS URL for frontend rendering
        s3_key = f"chat-attachments/{session_token}/{safe_filename}"
        s3_public_url = s3_service.get_public_url(s3_key)

        logger.info(
            f"📎 PDF uploaded for chat session {session_token[:8]}: "
            f"{file.filename} ({file_size} bytes)"
        )

        return ChatPDFUploadResponse(
            success=True,
            message="PDF uploaded successfully",
            s3_url=s3_public_url,  # Return public HTTPS URL for frontend
            filename=file.filename,
            file_size=file_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "session_token": session_token[:8] if session_token else None,
                "filename": file.filename if file else None,
                "file_size": file_size,
            },
            tags={
                "component": "chat",
                "operation": "upload_pdf",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Error uploading chat PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload PDF file")


# =============================================================================
# CHAT ATTACHMENT UPLOAD (PDFs + Images) - Enhanced Version
# =============================================================================


def validate_ooxml_file(file_content: bytes, expected_type: str) -> bool:
    """
    Validate OOXML files (docx, xlsx, pptx) by checking ZIP structure and content types.

    OOXML files are ZIP archives containing XML files. We validate by:
    1. Checking it's a valid ZIP file
    2. Verifying [Content_Types].xml exists (required for all OOXML)
    3. Checking the content type declarations match the expected Office format

    Args:
        file_content: The raw file bytes
        expected_type: One of 'docx', 'xlsx', 'pptx'

    Returns:
        True if valid OOXML file of expected type, False otherwise
    """
    import io
    import zipfile

    # Content type identifiers for each Office format
    OOXML_CONTENT_TYPES = {
        "docx": [
            "application/vnd.openxmlformats-officedocument.wordprocessingml",
            "word/document.xml",
        ],
        "xlsx": [
            "application/vnd.openxmlformats-officedocument.spreadsheetml",
            "xl/workbook.xml",
        ],
        "pptx": [
            "application/vnd.openxmlformats-officedocument.presentationml",
            "ppt/presentation.xml",
        ],
    }

    if expected_type not in OOXML_CONTENT_TYPES:
        return False

    try:
        # Check if it's a valid ZIP file
        with zipfile.ZipFile(io.BytesIO(file_content), "r") as zf:
            # Check for [Content_Types].xml - required for all OOXML files
            if "[Content_Types].xml" not in zf.namelist():
                logger.warning("OOXML validation failed: [Content_Types].xml not found")
                return False

            # Read and check content types
            content_types_xml = zf.read("[Content_Types].xml").decode("utf-8")

            # Check for expected content type identifiers
            expected_identifiers = OOXML_CONTENT_TYPES[expected_type]
            for identifier in expected_identifiers:
                if identifier in content_types_xml:
                    return True

            # Also check if the main document file exists
            main_files = {
                "docx": "word/document.xml",
                "xlsx": "xl/workbook.xml",
                "pptx": "ppt/presentation.xml",
            }
            if main_files[expected_type] in zf.namelist():
                return True

            logger.warning(f"OOXML validation failed: Content types don't match {expected_type}")
            return False

    except zipfile.BadZipFile:
        logger.warning("OOXML validation failed: Not a valid ZIP file")
        return False
    except Exception as e:
        logger.warning(f"OOXML validation failed: {e}")
        return False


# Supported file types and their configurations
SUPPORTED_ATTACHMENT_TYPES = {
    # PDFs - processed via Marker API
    ".pdf": {
        "mime_types": ["application/pdf"],
        "max_size": 50 * 1024 * 1024,  # 50MB
        "extraction_method": ExtractionMethod.MARKER_API,
        "magic_bytes": b"%PDF-",
        "category": "pdf",
    },
    # Microsoft Word Documents - processed via Marker API
    ".doc": {
        "mime_types": ["application/msword"],
        "max_size": 50 * 1024 * 1024,  # 50MB
        "extraction_method": ExtractionMethod.MARKER_API,
        "magic_bytes": b"\xd0\xcf\x11\xe0",  # OLE compound document signature
        "category": "document",
    },
    ".docx": {
        "mime_types": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        "max_size": 50 * 1024 * 1024,  # 50MB
        "extraction_method": ExtractionMethod.MARKER_API,
        "magic_bytes": b"PK",  # DOCX is a ZIP-based format (OOXML)
        "category": "document",
        "ooxml_type": "docx",  # Requires deeper OOXML validation
    },
    # Microsoft Excel Spreadsheets - processed via Marker API
    ".xls": {
        "mime_types": ["application/vnd.ms-excel"],
        "max_size": 50 * 1024 * 1024,  # 50MB
        "extraction_method": ExtractionMethod.MARKER_API,
        "magic_bytes": b"\xd0\xcf\x11\xe0",  # OLE compound document signature
        "category": "spreadsheet",
    },
    ".xlsx": {
        "mime_types": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        "max_size": 50 * 1024 * 1024,  # 50MB
        "extraction_method": ExtractionMethod.MARKER_API,
        "magic_bytes": b"PK",  # XLSX is a ZIP-based format (OOXML)
        "category": "spreadsheet",
        "ooxml_type": "xlsx",  # Requires deeper OOXML validation
    },
    # Microsoft PowerPoint Presentations - processed via Marker API
    ".ppt": {
        "mime_types": ["application/vnd.ms-powerpoint"],
        "max_size": 50 * 1024 * 1024,  # 50MB
        "extraction_method": ExtractionMethod.MARKER_API,
        "magic_bytes": b"\xd0\xcf\x11\xe0",  # OLE compound document signature
        "category": "presentation",
    },
    ".pptx": {
        "mime_types": ["application/vnd.openxmlformats-officedocument.presentationml.presentation"],
        "max_size": 50 * 1024 * 1024,  # 50MB
        "extraction_method": ExtractionMethod.MARKER_API,
        "magic_bytes": b"PK",  # PPTX is a ZIP-based format (OOXML)
        "category": "presentation",
        "ooxml_type": "pptx",  # Requires deeper OOXML validation
    },
    # Images - processed via GPT-4o Vision OCR
    ".png": {
        "mime_types": ["image/png"],
        "max_size": 20 * 1024 * 1024,  # 20MB
        "extraction_method": ExtractionMethod.GPT4_VISION,
        "magic_bytes": b"\x89PNG",
        "category": "image",
    },
    ".jpg": {
        "mime_types": ["image/jpeg"],
        "max_size": 20 * 1024 * 1024,  # 20MB
        "extraction_method": ExtractionMethod.GPT4_VISION,
        "magic_bytes": b"\xff\xd8\xff",
        "category": "image",
    },
    ".jpeg": {
        "mime_types": ["image/jpeg"],
        "max_size": 20 * 1024 * 1024,  # 20MB
        "extraction_method": ExtractionMethod.GPT4_VISION,
        "magic_bytes": b"\xff\xd8\xff",
        "category": "image",
    },
}


class AttachmentUploadResponse(BaseModel):
    """Response model for attachment upload"""

    success: bool
    attachment_id: str
    s3_url: str
    filename: str
    file_type: str
    file_size: int
    mime_type: str
    extracted_text: str | None = None
    extraction_status: str
    extraction_method: str | None = None
    message: str


@router.post("/sessions/{session_token}/upload-attachment", response_model=AttachmentUploadResponse)
async def upload_chat_attachment(
    session_token: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload a file attachment (documents, images) for chat.

    This endpoint:
    1. Validates the file type
    2. Uploads to S3
    3. Extracts text:
       - Documents (PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX) → Marker API
       - Images (PNG, JPG, JPEG) → GPT-4o Vision OCR
    4. Saves attachment metadata to database
    5. Returns attachment ID for use in chat messages

    Supported file types:
    - PDF/DOC/DOCX/XLS/XLSX/PPT/PPTX: up to 50MB
    - PNG/JPG/JPEG: up to 20MB

    Max 5 attachments per message.

    Args:
        session_token: The chat session token
        file: The file to upload

    Returns:
        AttachmentUploadResponse with attachment ID and extracted text
    """
    file_content = None
    file_size = None
    attachment = None

    try:
        # Validate session exists
        stmt = select(UserSession).where(UserSession.session_token == session_token)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if not user_session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not user_session.is_valid:
            raise HTTPException(status_code=401, detail="Session expired or inactive")

        # Validate filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Get file extension and validate
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in SUPPORTED_ATTACHMENT_TYPES:
            supported = ", ".join(SUPPORTED_ATTACHMENT_TYPES.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{file_extension}'. Supported: {supported}",
            )

        file_config = SUPPORTED_ATTACHMENT_TYPES[file_extension]

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size
        if file_size > file_config["max_size"]:
            max_mb = file_config["max_size"] // (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size for {file_extension} is {max_mb}MB",
            )

        # Validate magic bytes (file signature)
        if not file_content.startswith(file_config["magic_bytes"]):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file format. File does not match {file_extension} signature",
            )

        # For OOXML formats (.docx, .xlsx, .pptx), perform deeper validation
        # to prevent ZIP-based attacks (e.g., renamed .zip, .jar, .apk files)
        if "ooxml_type" in file_config:
            ooxml_type = file_config["ooxml_type"]
            if not validate_ooxml_file(file_content, ooxml_type):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {file_extension} file. File structure does not match "
                    f"a valid Microsoft Office document.",
                )

        # Determine MIME type
        content_type = file.content_type or file_config["mime_types"][0]
        if content_type not in file_config["mime_types"]:
            content_type = file_config["mime_types"][0]

        # Generate unique filename with timestamp and UUID
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid4())[:8]
        safe_filename = f"{timestamp}_{unique_id}_{file.filename}"

        # Upload to S3
        s3_service = get_s3_service()
        await s3_service.ensure_bucket_exists()
        s3_path = await s3_service.upload_file(
            file_content=file_content,
            user_id=session_token,
            filename=safe_filename,
            content_type=content_type,
            directory="chat-attachments",
        )

        # Extract S3 key from path
        s3_key = f"chat-attachments/{session_token}/{safe_filename}"

        # Generate public HTTPS URL for frontend rendering
        s3_public_url = s3_service.get_public_url(s3_key)

        logger.info(
            f"📎 Attachment uploaded for session {session_token[:8]}: "
            f"{file.filename} ({file_size} bytes, {file_extension})"
        )

        # Create attachment record in database (status: pending)
        # s3_url = public HTTPS URL (for frontend rendering)
        # s3_internal_path stored in metadata (for backend operations like PDF parsing)
        attachment = ConversationAttachment(
            session_token=session_token,
            filename=safe_filename,
            original_filename=file.filename,
            file_type=file_extension.lstrip("."),
            file_size=file_size,
            mime_type=content_type,
            s3_url=s3_public_url,  # Public HTTPS URL for frontend
            s3_key=s3_key,
            extraction_status=ExtractionStatus.PROCESSING.value,
            extraction_method=file_config["extraction_method"].value,
            attachment_metadata={
                "category": file_config["category"],
                "s3_internal_path": s3_path,  # Internal s3:// path for backend operations
            },
        )
        session.add(attachment)
        await session.flush()  # Get the ID

        # Extract text based on file type
        extracted_text = None
        extraction_error = None

        try:
            if file_config["category"] in ("pdf", "document", "spreadsheet", "presentation"):
                # Use Marker API for PDF and Office document extraction
                category_name = file_config["category"].upper()
                logger.info(f"📄 Extracting text from {category_name} using Marker API...")
                try:
                    generator = ResponseGenerator()
                    extracted_text = await generator.parse_pdf_to_markdown(s3_path)
                    logger.info(
                        f"✅ {category_name} extraction complete: {len(extracted_text)} chars"
                    )
                except Exception as marker_error:
                    # Specific Sentry tracking for Office document extraction failures
                    logger.error(
                        f"❌ Marker API extraction failed for {category_name}: {marker_error}"
                    )
                    capture_exception_with_context(
                        marker_error,
                        extra={
                            "session_token": session_token[:8] if session_token else None,
                            "filename": file.filename if file else None,
                            "file_type": file_extension,
                            "file_size": file_size,
                            "s3_path": s3_path,
                            "category": file_config["category"],
                        },
                        tags={
                            "component": "chat",
                            "operation": "marker_api_extraction",
                            "file_category": file_config["category"],
                            "severity": "high",
                            "user_facing": "true",
                        },
                    )
                    raise  # Re-raise to be caught by outer handler

            elif file_config["category"] == "image":
                # Use GPT-4o Vision for image OCR
                logger.info("🖼️ Extracting text from image using GPT-4o Vision...")
                ocr_service = get_ocr_service()
                ocr_result = await ocr_service.extract_text_from_image(
                    image_bytes=file_content,
                    mime_type=content_type,
                    filename=file.filename,
                )

                if ocr_result.success:
                    # Combine extracted text and description
                    extracted_text = f"{ocr_result.extracted_text}\n\n[Image Description: {ocr_result.description}]"
                    logger.info(f"✅ OCR extraction complete: {len(extracted_text)} chars")

                    # Store additional metadata
                    attachment.attachment_metadata = {
                        **attachment.attachment_metadata,
                        "ocr_description": ocr_result.description,
                    }
                else:
                    extraction_error = ocr_result.error
                    logger.error(f"❌ OCR extraction failed: {extraction_error}")

            # Limit extracted text length to prevent DB bloat and OOM (max 50K chars)
            MAX_EXTRACTED_TEXT_LENGTH = 50_000
            if extracted_text and len(extracted_text) > MAX_EXTRACTED_TEXT_LENGTH:
                logger.warning(
                    f"⚠️ Truncating extracted text from {len(extracted_text):,} to "
                    f"{MAX_EXTRACTED_TEXT_LENGTH:,} chars for {file.filename}"
                )
                extracted_text = (
                    extracted_text[:MAX_EXTRACTED_TEXT_LENGTH] + "\n\n[... Text truncated ...]"
                )
                attachment.attachment_metadata = {
                    **attachment.attachment_metadata,
                    "text_truncated": True,
                    "original_length": len(extracted_text),
                }

            # Update attachment with extraction results
            attachment.extracted_text = extracted_text
            attachment.extraction_status = (
                ExtractionStatus.COMPLETED.value
                if extracted_text
                else ExtractionStatus.FAILED.value
            )
            attachment.extraction_error = extraction_error
            attachment.processed_at = datetime.utcnow()

        except Exception as extract_error:
            logger.error(f"❌ Text extraction failed: {extract_error}")
            capture_exception_with_context(
                extract_error,
                extra={
                    "session_token": session_token[:8] if session_token else None,
                    "filename": file.filename if file else None,
                    "file_type": file_extension,
                    "file_size": file_size,
                    "extraction_method": file_config["extraction_method"].value,
                },
                tags={
                    "component": "chat",
                    "operation": "text_extraction",
                    "file_category": file_config["category"],
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            attachment.extraction_status = ExtractionStatus.FAILED.value
            attachment.extraction_error = str(extract_error)
            attachment.processed_at = datetime.utcnow()

        await session.commit()

        return AttachmentUploadResponse(
            success=True,
            attachment_id=str(attachment.id),
            s3_url=s3_public_url,  # Return public HTTPS URL for frontend
            filename=file.filename,
            file_type=file_extension.lstrip("."),
            file_size=file_size,
            mime_type=content_type,
            extracted_text=extracted_text,
            extraction_status=attachment.extraction_status,
            extraction_method=attachment.extraction_method,
            message=f"{file_config['category'].upper()} uploaded and processed successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "session_token": session_token[:8] if session_token else None,
                "filename": file.filename if file else None,
                "file_size": file_size,
            },
            tags={
                "component": "chat",
                "operation": "upload_attachment",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Error uploading chat attachment: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload attachment")


class AttachmentInfo(BaseModel):
    """Attachment info for API responses"""

    id: str
    filename: str
    file_type: str
    file_size: int
    s3_url: str
    extraction_status: str
    uploaded_at: str


@router.get("/sessions/{session_token}/attachments", response_model=List[AttachmentInfo])
async def get_session_attachments(
    session_token: str,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """
    Get all attachments for a session.

    Args:
        session_token: The chat session token

    Returns:
        List of attachment info
    """
    try:
        # Validate session exists
        stmt = select(UserSession).where(UserSession.session_token == session_token)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if not user_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get attachments for this session
        stmt = (
            select(ConversationAttachment)
            .where(ConversationAttachment.session_token == session_token)
            .order_by(ConversationAttachment.uploaded_at.desc())
        )
        result = await session.execute(stmt)
        attachments = result.scalars().all()

        return [
            AttachmentInfo(
                id=str(a.id),
                filename=a.original_filename,
                file_type=a.file_type,
                file_size=a.file_size,
                s3_url=a.s3_url,
                extraction_status=a.extraction_status,
                uploaded_at=a.uploaded_at.isoformat() if a.uploaded_at else "",
            )
            for a in attachments
        ]

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "session_token": session_token[:8] if session_token else None,
            },
            tags={
                "component": "chat",
                "operation": "get_session_attachments",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"Error getting session attachments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get attachments")
