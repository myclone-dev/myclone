"""
LinkedIn OAuth routes
"""

import logging
import secrets
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.email_service import EmailService
from app.services.linkedin_oauth_service import LinkedInOAuthService
from app.services.s3_avatar_service import is_s3_avatar_url, upload_avatar_from_url
from shared.config import settings
from shared.database.models.database import get_session
from shared.database.repositories.user_repository import UserRepository

router = APIRouter(prefix="/api/v1/auth/linkedin")
logger = logging.getLogger(__name__)


async def upload_avatar_background(user_id: str, linkedin_id: str, picture_url: str):
    """
    Background task to upload avatar to S3 and update user record.

    This runs after the OAuth callback completes, ensuring fast login UX.
    Creates its own database session since FastAPI background tasks run after response is sent.
    """
    try:
        logger.info(f"Background task: Uploading avatar for user {user_id}")

        s3_avatar_url = await upload_avatar_from_url(
            avatar_url=picture_url,
            user_id=linkedin_id,
        )

        if s3_avatar_url:
            logger.info(f"Background task: Successfully uploaded avatar to S3: {s3_avatar_url}")

            # Create new database session for background task
            from shared.database.models.database import get_session

            async for session in get_session():
                try:
                    # Convert user_id string to UUID
                    from uuid import UUID

                    user_uuid = UUID(user_id)

                    # Update user with S3 URL
                    user = await UserRepository.get_by_id(session, user_uuid)
                    if user:
                        await UserRepository.update_user(session, user, avatar=s3_avatar_url)
                        await session.commit()
                        logger.info(f"Background task: Updated user {user_id} with S3 avatar URL")
                    else:
                        logger.error(f"Background task: User {user_id} not found for avatar update")
                finally:
                    await session.close()
        else:
            logger.warning(f"Background task: Avatar upload failed for user {user_id}")

    except Exception as e:
        logger.error(f"Background task: Error uploading avatar for user {user_id}: {e}")


async def send_onboarding_email_background(email: str, fullname: str):
    """
    Background task to send onboarding email to new users.

    This runs after the OAuth callback completes, ensuring fast login UX.
    """
    try:
        logger.info(f"Background task: Sending onboarding email to {email}")

        # Initialize email service (similar to ElevenLabsService pattern)
        email_service = EmailService()
        success = await email_service.send_onboarding_email(to_email=email, fullname=fullname)

        if success:
            logger.info(f"Background task: Onboarding email sent successfully to {email}")
        else:
            logger.warning(f"Background task: Failed to send onboarding email to {email}")

    except Exception as e:
        logger.error(f"Background task: Error sending onboarding email to {email}: {e}")


@router.get("/login")
async def linkedin_login():
    """
    Initiate LinkedIn OAuth flow
    """
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Generate authorization URL
    auth_url = LinkedInOAuthService.get_authorization_url(
        state=state, redirect_uri=settings.linkedin_redirect_uri
    )

    logger.info(f"Initiating LinkedIn OAuth for state: {state}")

    # Create response with redirect
    response = RedirectResponse(url=auth_url)

    # Store state in cookie (browser will send it back with callback request)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.environment in ["production", "staging"],
        samesite="lax",
        max_age=600,  # 10 minutes
    )

    return response


@router.get("/callback")
async def linkedin_callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: str = Query(...),
    oauth_state: Optional[str] = Cookie(None),
    session: AsyncSession = Depends(get_session),
):
    """
    Handle LinkedIn OAuth callback

    This endpoint:
    1. Validates the state parameter (compares query param with cookie)
    2. Exchanges code for access token
    3. Fetches user info from LinkedIn
    4. Creates or updates user in database
    5. Schedules avatar upload in background (non-blocking)
    6. Creates JWT token
    7. Sets HTTP-only cookie
    8. Redirects to frontend

    Performance optimizations:
    - Avatar upload runs in background (no blocking)
    - Skips upload if user already has S3 avatar URL
    """

    # Validate state: query param must match cookie value
    if not oauth_state or state != oauth_state:
        logger.error(f"Invalid OAuth state. Query: {state}, Cookie: {oauth_state}")
        raise HTTPException(
            status_code=400, detail="Invalid state parameter - CSRF validation failed"
        )

    try:
        # Exchange code for access token
        token_response = await LinkedInOAuthService.exchange_code_for_token(
            code=code, redirect_uri=settings.linkedin_redirect_uri
        )

        access_token = token_response["access_token"]
        expires_in = token_response.get("expires_in", 5184000)  # Default 60 days
        refresh_token = token_response.get("refresh_token")

        # Get user info from LinkedIn
        user_info = await LinkedInOAuthService.get_user_info(access_token)

        linkedin_id = user_info.get("sub")
        email = user_info.get("email")
        fullname = user_info.get("name")
        given_name = user_info.get("given_name", "")
        family_name = user_info.get("family_name", "")
        picture = user_info.get("picture")

        if not linkedin_id or not email or not fullname:
            logger.error("LinkedIn user info missing required fields")
            raise HTTPException(
                status_code=400, detail="Failed to get user information from LinkedIn"
            )

        # Check if user exists
        user = await UserRepository.get_by_linkedin_id(session, linkedin_id)

        # Determine if we need to upload avatar (non-blocking check)
        should_upload_avatar = False
        is_new_user = False

        if not user:
            # Check if email already exists (user might have signed up differently)
            user = await UserRepository.get_by_email(session, email)

            if user:
                # Update existing user with LinkedIn info
                user = await UserRepository.update_user(
                    session,
                    user,
                    linkedin_id=linkedin_id,
                )
                # Check if user's current avatar is NOT an S3 URL
                should_upload_avatar = picture and not is_s3_avatar_url(user.avatar or "")
            else:
                # New user - always upload avatar in background
                user = await UserRepository.create_user(
                    session=session,
                    email=email,
                    fullname=fullname,
                    avatar=picture,  # Start with LinkedIn URL, will be updated by background task
                    linkedin_id=linkedin_id,
                )

                # Create default free tier subscription for new LinkedIn user
                from shared.database.models.tier_plan import SubscriptionStatus, UserSubscription

                try:
                    free_tier_subscription = UserSubscription(
                        user_id=user.id,
                        tier_id=0,  # Free tier
                        status=SubscriptionStatus.ACTIVE,
                    )
                    session.add(free_tier_subscription)
                    await session.flush()  # Validate before commit
                    logger.info(f"Created free tier subscription for LinkedIn user: {email}")
                except Exception as e:
                    logger.error(f"Failed to create subscription for user {user.id}: {e}")
                    await session.rollback()
                    raise HTTPException(status_code=500, detail="Authentication failed")

                should_upload_avatar = bool(picture)
                is_new_user = True  # Flag to send onboarding email
        else:
            # Existing user with LinkedIn ID
            # Check if user's current avatar is NOT an S3 URL
            logger.info(f"Checking existing user avatar: '{user.avatar}'")
            is_s3 = is_s3_avatar_url(user.avatar or "")
            logger.info(f"is_s3_avatar_url returned: {is_s3}")

            if picture and not is_s3:
                should_upload_avatar = True
                logger.info(f"User {user.id} has non-S3 avatar, scheduling upload")
            else:
                logger.info(
                    f"User {user.id} already has S3 avatar ({user.avatar}), skipping upload"
                )

        # Schedule background avatar upload if needed (non-blocking)
        if should_upload_avatar:
            logger.info(f"Scheduling background avatar upload for user {user.id}")
            background_tasks.add_task(
                upload_avatar_background,
                user_id=str(user.id),
                linkedin_id=linkedin_id,
                picture_url=picture,
            )
        else:
            logger.info(f"Skipping avatar upload for user {user.id} (already has S3 URL)")

        # Send onboarding email to new users (non-blocking)
        if is_new_user:
            logger.info(f"Scheduling onboarding email for new user {user.id} ({email})")
            background_tasks.add_task(
                send_onboarding_email_background,
                email=email,
                fullname=fullname,
            )

        # Store or update auth details
        token_expiry = datetime.now(dt_timezone.utc) + timedelta(seconds=expires_in)

        await UserRepository.create_or_update_auth_detail(
            session=session,
            user_id=user.id,
            platform="linkedin",
            platform_user_id=linkedin_id,
            platform_username=user_info.get("email", ""),
            avatar=user.avatar
            or "",  # Use current avatar (will be updated by background task if needed)
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            auth_metadata={
                "given_name": given_name,
                "family_name": family_name,
                "locale": user_info.get("locale"),
            },
        )

        # Create JWT token
        jwt_token = LinkedInOAuthService.create_jwt_token(user_id=str(user.id), email=user.email)

        # Redirect to frontend - let frontend handle routing based on user state
        redirect_url = f"{settings.frontend_url}/"

        # Create response with redirect
        response = RedirectResponse(url=redirect_url)

        # Set HTTP-only cookie with JWT token
        response.set_cookie(
            key="myclone_token",
            value=jwt_token,
            httponly=True,
            secure=settings.environment
            in ["production", "staging"],  # HTTPS for deployed environments
            samesite="lax",
            max_age=60 * 60 * 24 * settings.jwt_expiration_days,  # Match JWT expiration
            domain=settings.cookie_domain,
        )

        # Delete OAuth state cookie (no longer needed)
        response.delete_cookie(key="oauth_state")

        logger.info(f"Successfully authenticated user: {user.email}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during LinkedIn OAuth callback: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.post("/logout")
async def logout():
    """Logout user by clearing the auth cookie"""
    response = Response(content="Logged out successfully")
    response.delete_cookie(
        key="myclone_token",
        domain=settings.cookie_domain,
    )
    return response


@router.get("/verify")
async def verify_token(
    auth_token: Optional[str] = Query(None),
):
    """
    Verify JWT token (for testing purposes)

    In production, this should be protected or removed
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="No token provided")

    payload = LinkedInOAuthService.verify_jwt_token(auth_token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "valid": True,
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "expires_at": payload.get("exp"),
    }
