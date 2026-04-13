"""
Email/Password authentication routes

This module handles all authentication flows for email/password users:
- Registration with email verification
- Login with account lockout protection
- Password reset flow
- Email verification and resend
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.auth_models import (
    ErrorResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RequestOTPRequest,
    RequestOTPResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    VerifyEmailResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.auth.jwt_auth import get_current_user
from app.services.auth_rate_limiting_service import AuthRateLimitingService
from app.services.custom_email_domain_service import CustomEmailDomainService
from app.services.email_verification_service import EmailVerificationService
from app.services.linkedin_oauth_service import LinkedInOAuthService
from app.services.password_reset_service import PasswordResetService
from app.services.password_service import PasswordService
from shared.config import settings
from shared.database.models.database import get_session
from shared.database.models.user import AuthDetail, User
from shared.database.repositories.user_repository import UserRepository
from shared.monitoring.sentry_utils import capture_exception_with_context

router = APIRouter(prefix="/api/v1/auth")
logger = logging.getLogger(__name__)

# Initialize rate limiter (slowapi for IP-based limits)
limiter = Limiter(key_func=get_remote_address)

# Initialize services
password_service = PasswordService()
email_verification_service = EmailVerificationService()
password_reset_service = PasswordResetService()
auth_rate_limiting_service = AuthRateLimitingService()
custom_email_domain_service = CustomEmailDomainService()


async def _get_custom_sender_email(session: AsyncSession, user_id: uuid.UUID) -> str | None:
    """
    Get custom sender email for a user if they have a verified custom domain.

    Args:
        session: Database session
        user_id: User ID to look up custom domain for

    Returns:
        Formatted sender email if custom domain exists, None otherwise
    """
    try:
        sender_config = await custom_email_domain_service.get_sender_config(session, user_id)
        # Check if it's a custom domain (not the default)
        if (
            sender_config.from_email
            != settings.resend_from_email.split("<")[-1].rstrip(">").strip()
        ):
            logger.info(
                f"📧 Using custom email domain for user {user_id}: {sender_config.from_email}"
            )
            return sender_config.formatted_from
    except Exception as e:
        logger.warning(f"Failed to get custom sender for user {user_id}: {e}")
    return None


async def _get_custom_sender_by_username(session: AsyncSession, username: str) -> str | None:
    """
    Get custom sender email for a persona owner by their username.

    This is used for whitelabel emails - when a visitor requests an OTP
    while on a persona page, the email should come from the persona owner's
    custom domain (if they have one configured).

    Args:
        session: Database session
        username: Username of the persona owner

    Returns:
        Formatted sender email if custom domain exists, None otherwise
    """
    try:
        # Look up user by username
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"User not found for username: {username}")
            return None

        # Get their custom sender
        return await _get_custom_sender_email(session, user.id)
    except Exception as e:
        logger.warning(f"Failed to get custom sender for username {username}: {e}")
    return None


async def _create_otp_auth_for_user(
    session: AsyncSession,
    user: User,
    otp_data: RequestOTPRequest,
    account_type_label: str,
) -> RequestOTPResponse:
    """
    Create OTP auth for a user who doesn't have one yet and send OTP email.

    This helper handles the common logic for both VISITOR and CREATOR users
    who need OTP authentication created for the first time.

    Args:
        session: Database session
        user: The existing user requesting OTP
        otp_data: The OTP request data (email, persona_username, etc.)
        account_type_label: Label for logging ("visitor" or "creator")

    Returns:
        RequestOTPResponse on success

    Raises:
        HTTPException: If OTP auth creation fails
    """
    logger.info(
        f"{account_type_label.upper()} user without OTP auth requesting OTP: "
        f"{otp_data.email} - creating OTP auth"
    )

    # Generate OTP
    otp_code, otp_expires = email_verification_service.generate_otp_code()

    # Create new OTP AuthDetail
    auth_detail = AuthDetail(
        user_id=user.id,
        auth_type="otp",
        hashed_password=None,  # OTP auth has no password
        failed_login_attempts=0,
        email_verified_at=(
            datetime.now(timezone.utc) if user.email_confirmed else None
        ),  # Inherit verification if already confirmed
        email_verification_token=otp_code,
        email_verification_token_expires=otp_expires,
    )
    session.add(auth_detail)

    # Handle race condition: concurrent requests might try to create same auth_detail
    try:
        await session.commit()
    except Exception as commit_error:
        # Check if this is a unique constraint violation (race condition)
        if "uq_auth_details_user_auth_type" in str(commit_error):
            # Another request created the OTP auth - fetch it instead
            logger.warning(
                f"Race condition detected - OTP auth already created for {otp_data.email}, "
                "fetching existing record"
            )
            await session.rollback()
            result = await session.execute(
                select(AuthDetail)
                .where(
                    AuthDetail.user_id == user.id,
                    AuthDetail.auth_type == "otp",
                )
                .limit(1)
            )
            auth_detail = result.scalar_one_or_none()
            if not auth_detail:
                # Unexpected - should exist if constraint was violated
                raise HTTPException(status_code=500, detail="Failed to create OTP authentication")
            # Update with new OTP
            auth_detail.email_verification_token = otp_code
            auth_detail.email_verification_token_expires = otp_expires
            await session.commit()
        else:
            # Unexpected error - capture in Sentry and re-raise
            capture_exception_with_context(
                commit_error,
                extra={
                    "email": otp_data.email,
                    "user_id": str(user.id),
                    "account_type": user.account_type,
                },
                tags={
                    "component": "auth",
                    "operation": f"request_otp_{account_type_label}_auth_creation",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            raise

    # Send OTP email (with custom domain if available)
    # Prioritize persona owner's domain if persona_username provided (whitelabel)
    custom_sender = None
    if otp_data.persona_username:
        custom_sender = await _get_custom_sender_by_username(session, otp_data.persona_username)
    if not custom_sender:
        custom_sender = await _get_custom_sender_email(session, user.id)
    email_sent = await email_verification_service.send_otp_email(
        to_email=otp_data.email,
        fullname=user.fullname,
        otp_code=otp_code,
        purpose="login",
        from_email=custom_sender,
    )

    if not email_sent:
        logger.warning(f"Failed to send OTP email to {otp_data.email}")

    logger.info(
        f"OTP auth created and sent for {account_type_label.upper()} user: {otp_data.email}"
    )
    return RequestOTPResponse(
        success=True,
        message=f"Verification code sent to {otp_data.email}. Please check your inbox.",
        is_new_user=False,
        account_type=user.account_type,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    responses={
        200: {"model": RegisterResponse},
        400: {"model": ErrorResponse, "description": "Invalid request or weak password"},
        409: {"model": ErrorResponse, "description": "Email already exists"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Register new user with email and password",
)
@limiter.limit("5/hour")  # Limit to 5 registration attempts per hour per IP
async def register(
    request: Request,
    registration_data: RegisterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Register a new user with email and password

    Process:
    1. Validate email uniqueness
    2. Validate password strength
    3. Hash password with bcrypt
    4. Create user record
    5. Create AuthDetail record (auth_type='password')
    6. Generate email verification token
    7. Send verification email
    8. Return success (user must verify email before login)

    Security features:
    - Bcrypt password hashing (12 rounds)
    - Email verification required before login
    - Rate limiting (5 attempts per hour per IP)
    - Generic error messages (prevent email enumeration)
    """
    try:
        # Debug logging
        logger.info(
            f"Registration request - Email: {registration_data.email}, Password length: {len(registration_data.password)} chars, {len(registration_data.password.encode('utf-8'))} bytes"
        )

        # Step 1: Check if email already exists
        existing_user = await UserRepository.get_by_email(session, registration_data.email)
        if existing_user:
            # Check if this is a visitor account that can be upgraded to creator
            from shared.database.models.user import AccountType as AT

            if existing_user.account_type == AT.VISITOR:
                logger.info(
                    f"Upgrading visitor account to creator: {registration_data.email} (user_id={existing_user.id})"
                )
                # Visitor → Creator upgrade: set password, username, fullname, account_type
                is_valid, error_message = password_service.validate_password_strength(
                    registration_data.password
                )
                if not is_valid:
                    raise HTTPException(status_code=400, detail=error_message)

                hashed_password = await password_service.hash_password(registration_data.password)

                # Update user fields
                existing_user.account_type = AT.CREATOR
                existing_user.fullname = registration_data.fullname
                existing_user.email_confirmed = False  # Must verify email

                # Set username if provided (and different from visitor_* auto-generated)
                if registration_data.username:
                    # Check username uniqueness
                    username_taken = await UserRepository.get_by_username(
                        session, registration_data.username
                    )
                    if username_taken and username_taken.id != existing_user.id:
                        raise HTTPException(status_code=409, detail="Username already taken")
                    existing_user.username = registration_data.username

                # Reset onboarding for creator flow
                from shared.database.models.user import OnboardingStatus

                existing_user.onboarding_status = OnboardingStatus.NOT_STARTED

                # Create AuthDetail (visitors from lead capture don't have one)
                # Filter by password/otp auth_type to avoid matching OAuth records
                # and to prevent MultipleResultsFound if user has multiple auth rows
                existing_auth = await session.execute(
                    select(AuthDetail).where(
                        AuthDetail.user_id == existing_user.id,
                        AuthDetail.auth_type.in_(["password", "otp"]),
                    )
                )
                existing_auth_detail = existing_auth.scalar_one_or_none()

                verification_token, verification_expires = (
                    email_verification_service.generate_verification_token()
                )

                if existing_auth_detail:
                    # Update existing auth detail (e.g., OTP user upgrading)
                    existing_auth_detail.auth_type = "password"
                    existing_auth_detail.hashed_password = hashed_password
                    existing_auth_detail.email_verification_token = verification_token
                    existing_auth_detail.email_verification_token_expires = verification_expires
                else:
                    auth_detail = AuthDetail(
                        user_id=existing_user.id,
                        auth_type="password",
                        hashed_password=hashed_password,
                        failed_login_attempts=0,
                        email_verified_at=None,
                        email_verification_token=verification_token,
                        email_verification_token_expires=verification_expires,
                    )
                    session.add(auth_detail)

                # Ensure free tier subscription exists (lead capture may have already created one)
                from shared.database.models.tier_plan import (
                    SubscriptionStatus,
                    UserSubscription,
                )

                existing_sub = await session.execute(
                    select(UserSubscription).where(UserSubscription.user_id == existing_user.id)
                )
                if not existing_sub.scalar_one_or_none():
                    free_tier_subscription = UserSubscription(
                        user_id=existing_user.id,
                        tier_id=0,
                        status=SubscriptionStatus.ACTIVE,
                    )
                    session.add(free_tier_subscription)

                await session.commit()

                # Send verification email
                email_sent = await email_verification_service.send_verification_email(
                    to_email=registration_data.email,
                    fullname=registration_data.fullname,
                    verification_token=verification_token,
                )
                if not email_sent:
                    logger.warning(
                        f"Failed to send verification email to upgraded visitor {registration_data.email}"
                    )

                logger.info(
                    f"✅ Visitor upgraded to creator: {registration_data.email} (user_id={existing_user.id})"
                )
                return RegisterResponse(
                    message="Registration successful! Please check your email to verify your account.",
                    email=registration_data.email,
                )

            # Non-visitor duplicate: security — return success to prevent email enumeration
            logger.warning(f"Registration attempted for existing email: {registration_data.email}")
            return RegisterResponse(
                message="Registration successful! Please check your email to verify your account.",
                email=registration_data.email,
            )

        # Step 2: Validate password strength
        is_valid, error_message = password_service.validate_password_strength(
            registration_data.password
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Step 3: Hash password
        hashed_password = await password_service.hash_password(registration_data.password)

        # Step 4: Create user record
        from shared.database.models.user import AccountType, OnboardingStatus

        account_type = AccountType(registration_data.account_type)

        # Visitors are auto-onboarded (skip creator onboarding flow)
        onboarding_status = (
            OnboardingStatus.FULLY_ONBOARDED
            if account_type == AccountType.VISITOR
            else None  # None = use DB default (NOT_STARTED) for creators
        )

        # Generate random username for visitors if not provided
        username = registration_data.username
        if account_type == AccountType.VISITOR and username is None:
            import secrets
            import string

            # Generate unique username: visitor_<8_random_chars>
            max_attempts = 10
            for attempt in range(max_attempts):
                random_suffix = "".join(
                    secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)
                )
                generated_username = f"visitor_{random_suffix}"

                # Check if username is unique
                existing = await UserRepository.get_by_username(session, generated_username)
                if not existing:
                    username = generated_username
                    logger.info(f"Generated random username for visitor: {username}")
                    break
            else:
                # Fallback: use UUID if all attempts failed (very unlikely)
                username = f"visitor_{str(uuid.uuid4())[:8]}"
                logger.warning(
                    f"Failed to generate unique username after {max_attempts} attempts, using UUID-based: {username}"
                )

        user = await UserRepository.create_user(
            session=session,
            email=registration_data.email,
            fullname=registration_data.fullname,
            username=username,
            email_confirmed=False,  # Must verify email before login
            account_type=account_type,
            onboarding_status=onboarding_status,
        )

        # Step 5: Create AuthDetail record for password authentication
        verification_token, verification_expires = (
            email_verification_service.generate_verification_token()
        )

        auth_detail = AuthDetail(
            user_id=user.id,
            auth_type="password",
            hashed_password=hashed_password,
            failed_login_attempts=0,
            email_verified_at=None,  # Not verified yet
            # Store verification token temporarily (will be cleared after verification)
            email_verification_token=verification_token,
            email_verification_token_expires=verification_expires,
        )
        session.add(auth_detail)

        # Step 5.5: Create default free tier subscription for new user
        from shared.database.models.tier_plan import SubscriptionStatus, UserSubscription

        try:
            free_tier_subscription = UserSubscription(
                user_id=user.id,
                tier_id=0,  # Free tier
                status=SubscriptionStatus.ACTIVE,
            )
            session.add(free_tier_subscription)
            await session.flush()  # Validate before commit
            logger.info(f"Created free tier subscription for user: {registration_data.email}")
        except Exception as e:
            logger.error(f"Failed to create subscription for user {user.id}: {e}")
            await session.rollback()
            raise HTTPException(status_code=500, detail="Failed to create user account")

        await session.commit()
        await session.refresh(auth_detail)

        # Step 6: Send verification email
        email_sent = await email_verification_service.send_verification_email(
            to_email=registration_data.email,
            fullname=registration_data.fullname,
            verification_token=verification_token,
        )

        if not email_sent:
            logger.warning(
                f"Failed to send verification email to {registration_data.email}, but user created"
            )

        logger.info(f"User registered successfully: {registration_data.email}")
        return RegisterResponse(
            message="Registration successful! Please check your email to verify your account.",
            email=registration_data.email,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"email": registration_data.email, "fullname": registration_data.fullname},
            tags={
                "component": "auth",
                "operation": "register",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Registration failed for {registration_data.email}: {e}")
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")


@router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
    responses={
        200: {"model": VerifyEmailResponse},
        400: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Token not found"},
    },
    summary="Verify user email address",
)
async def verify_email(
    response: Response,
    token: str = Query(..., description="Verification token from email"),
    session: AsyncSession = Depends(get_session),
):
    """
    Verify user email address with token

    Process:
    1. Find AuthDetail by verification token
    2. Check token expiration (24 hours)
    3. Mark email as verified
    4. Clear verification token
    5. Update user email_confirmed status
    6. Auto-login: generate JWT and set cookie
    7. Return success with user data

    Security:
    - Token expires after 24 hours
    - Token is single-use (cleared after verification)
    - User is auto-logged in after verification
    """
    try:
        # Find AuthDetail by verification token
        result = await session.execute(
            select(AuthDetail)
            .where(AuthDetail.email_verification_token == token, AuthDetail.auth_type == "password")
            .limit(1)
        )
        auth_detail = result.scalar_one_or_none()

        if not auth_detail:
            raise HTTPException(status_code=404, detail="Invalid verification token")

        # Check token expiration
        if (
            not auth_detail.email_verification_token_expires
            or auth_detail.email_verification_token_expires < datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=400,
                detail="Verification token has expired. Please request a new verification email.",
            )

        # Mark email as verified
        auth_detail.email_verified_at = datetime.now(timezone.utc)
        auth_detail.email_verification_token = None
        auth_detail.email_verification_token_expires = None

        # Update user email_confirmed status
        user = await UserRepository.get_by_id(session, auth_detail.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.email_confirmed = True

        await session.commit()
        await session.refresh(user)

        # Generate JWT token for auto-login
        jwt_token = LinkedInOAuthService.create_jwt_token(
            user_id=str(user.id),
            email=user.email,
        )

        # Set HTTP-only cookie for auto-login
        response.set_cookie(
            key="myclone_token",
            value=jwt_token,
            httponly=True,
            secure=settings.environment in ["production", "staging"],
            samesite="lax",
            max_age=60 * 60 * 24 * settings.jwt_expiration_days,
            domain=settings.cookie_domain,
        )

        logger.info(f"Email verified successfully for user: {user.email}")

        # Create response
        response_data = VerifyEmailResponse(
            message="Email verified successfully! You are now logged in.",
            user_id=str(user.id),
            email=user.email,
            fullname=user.fullname,
            account_type=user.account_type,
            token=jwt_token,
        )

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"token": token},
            tags={
                "component": "auth",
                "operation": "verify_email",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Email verification failed: {e}")
        raise HTTPException(status_code=500, detail="Email verification failed. Please try again.")


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        200: {"model": LoginResponse},
        400: {"model": ErrorResponse, "description": "Invalid credentials"},
        401: {"model": ErrorResponse, "description": "Email not verified"},
        403: {"model": ErrorResponse, "description": "Account locked"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Login with email/username and password",
)
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Login with email or username and password

    Process:
    1. Find user by email or username
    2. Find password AuthDetail for user
    3. Check account lockout status
    4. Check email verification status
    5. Verify password
    6. On success: Reset failed attempts, generate JWT, set cookie
    7. On failure: Increment failed attempts, lock after 5 failures

    Security features:
    - Account lockout after 5 failed attempts (15 minutes)
    - Email verification required
    - Bcrypt password verification
    - HTTP-only cookie for JWT
    - Generic error messages (prevent user enumeration)
    """
    try:
        # Step 1: Find user by email or username
        result = await session.execute(
            select(User)
            .where(or_(User.email == request.email, User.username == request.email))
            .limit(1)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Generic error to prevent email/username enumeration
            raise HTTPException(status_code=400, detail="Invalid credentials")

        # Step 2: Find password AuthDetail
        result = await session.execute(
            select(AuthDetail)
            .where(AuthDetail.user_id == user.id, AuthDetail.auth_type == "password")
            .limit(1)
        )
        auth_detail = result.scalar_one_or_none()

        if not auth_detail:
            # User exists but has no password auth (OAuth only)
            raise HTTPException(status_code=400, detail="Invalid credentials")

        # Step 3: Check account lockout
        lockout_info = await auth_rate_limiting_service.get_lockout_info(auth_detail)
        if lockout_info:
            raise HTTPException(
                status_code=403,
                detail=f"Account locked due to too many failed login attempts. Try again in {lockout_info['remaining_minutes']} minute(s).",
            )

        # Step 4: Check email verification
        if not auth_detail.email_verified_at:
            raise HTTPException(
                status_code=401,
                detail="Email not verified. Please check your email and verify your account before logging in.",
            )

        # Step 5: Verify password
        is_valid = await password_service.verify_password(
            request.password, auth_detail.hashed_password
        )

        if not is_valid:
            # Record failed attempt
            attempts = await auth_rate_limiting_service.record_failed_login(session, auth_detail)

            # Check if account is now locked
            if attempts >= settings.max_failed_login_attempts:
                raise HTTPException(
                    status_code=403,
                    detail=f"Account locked due to too many failed login attempts. Try again in {settings.account_lockout_duration_minutes} minutes.",
                )

            # Generic error
            raise HTTPException(status_code=400, detail="Invalid credentials")

        # Step 6: Success - Reset failed attempts
        await auth_rate_limiting_service.reset_failed_attempts(session, auth_detail)

        # Generate JWT token
        jwt_token = LinkedInOAuthService.create_jwt_token(
            user_id=str(user.id),
            email=user.email,
        )

        # Set HTTP-only cookie
        response.set_cookie(
            key="myclone_token",
            value=jwt_token,
            httponly=True,
            secure=settings.environment in ["production", "staging"],
            samesite="lax",
            max_age=60 * 60 * 24 * settings.jwt_expiration_days,
            domain=settings.cookie_domain,
        )

        logger.info(f"User logged in successfully: {user.email}")

        return LoginResponse(
            message="Login successful",
            user_id=str(user.id),
            email=user.email,
            fullname=user.fullname,
            account_type=user.account_type,
            token=jwt_token,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"email": request.email},
            tags={
                "component": "auth",
                "operation": "login",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Login failed for {request.email}: {e}")
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    responses={
        200: {"model": ForgotPasswordResponse},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Request password reset",
)
@limiter.limit("3/hour")  # Limit to 3 requests per hour per IP
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Request password reset email

    Process:
    1. Find user by email (return generic success if not found - security)
    2. Find password AuthDetail (return generic success if OAuth only - security)
    3. Generate reset token (1 hour expiration)
    4. Store token in AuthDetail
    5. Send password reset email
    6. Return generic success (always, regardless of email existence)

    Security features:
    - Generic success message (prevent email enumeration)
    - Token expires after 1 hour
    - Rate limiting (3 requests per hour per IP)
    - Single-use token
    """
    try:
        # Generic success message (security: don't reveal if email exists)
        success_message = (
            "If an account with this email exists, a password reset link has been sent."
        )

        logger.info(f"🔐 [FORGOT-PASSWORD] Starting password reset flow for: {forgot_data.email}")

        # Find user by email
        user = await UserRepository.get_by_email(session, forgot_data.email)
        if not user:
            # Don't reveal email doesn't exist
            logger.info(
                f"🔐 [FORGOT-PASSWORD] User not found for email: {forgot_data.email} - returning generic success"
            )
            return ForgotPasswordResponse(message=success_message)

        logger.info(
            f"🔐 [FORGOT-PASSWORD] User found: {user.id} ({user.email}) - checking password auth"
        )

        # Find password AuthDetail
        result = await session.execute(
            select(AuthDetail)
            .where(AuthDetail.user_id == user.id, AuthDetail.auth_type == "password")
            .limit(1)
        )
        auth_detail = result.scalar_one_or_none()

        if not auth_detail:
            # User has OAuth only, no password auth
            logger.info(
                f"🔐 [FORGOT-PASSWORD] No password auth found for user {user.id} - OAuth-only user - returning generic success"
            )
            return ForgotPasswordResponse(message=success_message)

        logger.info(
            f"🔐 [FORGOT-PASSWORD] Password auth found for user {user.id} - generating reset token"
        )

        # Generate reset token
        reset_token, reset_expires = password_reset_service.generate_reset_token()
        logger.info(
            f"🔐 [FORGOT-PASSWORD] Reset token generated for user {user.id} - expires at {reset_expires}"
        )

        # Store token
        auth_detail.password_reset_token = reset_token
        auth_detail.password_reset_expires = reset_expires
        await session.commit()
        logger.info(f"🔐 [FORGOT-PASSWORD] Reset token stored in database for user {user.id}")

        # Send password reset email
        logger.info(
            f"📧 [FORGOT-PASSWORD] Attempting to send password reset email to {forgot_data.email}"
        )
        email_sent = await password_reset_service.send_password_reset_email(
            to_email=forgot_data.email,
            fullname=user.fullname,
            reset_token=reset_token,
        )

        if not email_sent:
            logger.error(
                f"❌ [FORGOT-PASSWORD] Email service returned False for {forgot_data.email} - email NOT sent!"
            )
        else:
            logger.info(
                f"✅ [FORGOT-PASSWORD] Email service returned True for {forgot_data.email} - email sent successfully"
            )

        logger.info(f"🔐 [FORGOT-PASSWORD] Password reset flow completed for: {forgot_data.email}")
        return ForgotPasswordResponse(message=success_message)

    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"email": forgot_data.email},
            tags={
                "component": "auth",
                "operation": "forgot_password",
                "severity": "medium",
                "user_facing": "false",
            },
        )
        logger.error(f"Forgot password failed for {forgot_data.email}: {e}")
        # Return success anyway (security)
        return ForgotPasswordResponse(
            message="If an account with this email exists, a password reset link has been sent."
        )


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={
        200: {"model": ResetPasswordResponse},
        400: {"model": ErrorResponse, "description": "Invalid token or weak password"},
        404: {"model": ErrorResponse, "description": "Token not found or expired"},
    },
    summary="Reset password with token",
)
async def reset_password(
    request: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Reset password with token from email

    Process:
    1. Find AuthDetail by reset token
    2. Validate token expiration (1 hour)
    3. Validate new password strength
    4. Hash new password
    5. Update password
    6. Clear reset token
    7. Send password changed confirmation email
    8. Return success

    Security features:
    - Token expires after 1 hour
    - Single-use token (cleared after use)
    - Password strength validation
    - Confirmation email sent
    """
    try:
        # Find AuthDetail by reset token
        result = await session.execute(
            select(AuthDetail)
            .where(
                AuthDetail.password_reset_token == request.token,
                AuthDetail.auth_type == "password",
            )
            .limit(1)
        )
        auth_detail = result.scalar_one_or_none()

        if not auth_detail:
            raise HTTPException(status_code=404, detail="Invalid reset token")

        # Check token expiration
        if (
            not auth_detail.password_reset_expires
            or auth_detail.password_reset_expires < datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=400,
                detail="Reset token has expired. Please request a new password reset.",
            )

        # Validate new password strength
        is_valid, error_message = password_service.validate_password_strength(request.new_password)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Hash new password
        hashed_password = await password_service.hash_password(request.new_password)

        # Update password
        auth_detail.hashed_password = hashed_password
        auth_detail.password_reset_token = None
        auth_detail.password_reset_expires = None
        auth_detail.last_password_change = datetime.now(timezone.utc)

        await session.commit()

        # Get user for confirmation email
        user = await UserRepository.get_by_id(session, auth_detail.user_id)

        # Send password changed confirmation email
        if user:
            await password_reset_service.send_password_changed_email(
                to_email=user.email,
                fullname=user.fullname,
            )

        logger.info(f"Password reset successfully for user: {auth_detail.user_id}")
        return ResetPasswordResponse(
            message="Password reset successful. You can now login with your new password."
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"token": request.token},
            tags={
                "component": "auth",
                "operation": "reset_password",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Password reset failed: {e}")
        raise HTTPException(status_code=500, detail="Password reset failed. Please try again.")


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    responses={
        200: {"model": ResendVerificationResponse},
        400: {"model": ErrorResponse, "description": "Email already verified"},
        404: {"model": ErrorResponse, "description": "User not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Resend email verification",
)
@limiter.limit("3/hour")  # Limit to 3 requests per hour per IP
async def resend_verification(
    request: Request,
    resend_data: ResendVerificationRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Resend email verification email

    Process:
    1. Find user by email
    2. Check if already verified
    3. Find password AuthDetail
    4. Generate new verification token
    5. Update token in AuthDetail
    6. Send verification email
    7. Return success

    Security features:
    - Rate limiting (3 requests per hour per IP)
    - Generic error messages
    - New token generated each time
    """
    try:
        # Find user by email
        user = await UserRepository.get_by_email(session, resend_data.email)
        if not user:
            # Generic message (security: don't reveal email doesn't exist)
            return ResendVerificationResponse(
                message="Verification email has been sent. Please check your inbox."
            )

        # Check if already verified
        if user.email_confirmed:
            raise HTTPException(
                status_code=400, detail="Email is already verified. You can login now."
            )

        # Find password AuthDetail
        result = await session.execute(
            select(AuthDetail)
            .where(AuthDetail.user_id == user.id, AuthDetail.auth_type == "password")
            .limit(1)
        )
        auth_detail = result.scalar_one_or_none()

        if not auth_detail:
            # User has OAuth only (should not happen)
            logger.warning(
                f"Verification resend requested for OAuth-only user: {resend_data.email}"
            )
            return ResendVerificationResponse(
                message="Verification email has been sent. Please check your inbox."
            )

        # Generate new verification token
        verification_token, verification_expires = (
            email_verification_service.generate_verification_token()
        )

        # Update token
        auth_detail.email_verification_token = verification_token
        auth_detail.email_verification_token_expires = verification_expires
        await session.commit()

        # Send verification email
        email_sent = await email_verification_service.send_verification_resend_email(
            to_email=resend_data.email,
            fullname=user.fullname,
            verification_token=verification_token,
        )

        if not email_sent:
            logger.warning(f"Failed to send verification resend email to {resend_data.email}")

        logger.info(f"Verification email resent to: {resend_data.email}")
        return ResendVerificationResponse(
            message="Verification email has been sent. Please check your inbox."
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"email": resend_data.email},
            tags={
                "component": "auth",
                "operation": "resend_verification",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"Resend verification failed for {resend_data.email}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to resend verification email. Please try again."
        )


@router.post(
    "/logout",
    responses={
        200: {"description": "Successfully logged out"},
    },
    summary="Logout user (clear auth cookie)",
)
async def logout(response: Response):
    """
    Logout user by clearing the HTTP-only authentication cookie

    This endpoint works for all authentication methods (LinkedIn OAuth, email/password, etc.).
    The frontend cannot directly delete HTTP-only cookies (that's the security feature),
    so this endpoint must be called to properly clear the session.

    Process:
    1. Server clears the `myclone_token` cookie
    2. Cookie is deleted from browser
    3. User is logged out

    Returns:
        Success message
    """
    # Clear the authentication cookie
    response.delete_cookie(
        key="myclone_token",
        domain=settings.cookie_domain,
    )

    logger.info("User logged out successfully")
    return {"message": "Logged out successfully"}


@router.post(
    "/set-password",
    response_model=SetPasswordResponse,
    responses={
        200: {"model": SetPasswordResponse},
        400: {"model": ErrorResponse, "description": "Invalid request or weak password"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        409: {"model": ErrorResponse, "description": "Password already set"},
    },
    summary="Set password for OAuth users",
)
async def set_password(
    request: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Allow OAuth users to add password authentication

    This endpoint enables existing OAuth users (LinkedIn, Google, etc.) to add
    email/password authentication to their account, allowing them to login
    with either method.

    Process:
    1. Verify user is authenticated (JWT required)
    2. Check if user already has password auth
    3. Validate password strength
    4. Hash password with bcrypt
    5. Create AuthDetail with auth_type='password'
    6. Mark email as verified (inherit from OAuth verification)
    7. Send confirmation email
    8. Return success

    Requirements:
    - User must be logged in (JWT cookie required)
    - Password must meet strength requirements
    - User cannot already have password auth

    After completion:
    - User will have both OAuth and password authentication
    - User can login with either method
    - Independent lockout tracking per auth method

    Security features:
    - Requires active authentication
    - Password strength validation
    - Bcrypt hashing (12 rounds)
    - Email verification inherited from OAuth
    - Confirmation email sent
    """
    try:
        # Step 1: Check if user already has password auth
        existing_password_auth = await UserRepository.get_password_auth(session, current_user.id)

        if existing_password_auth:
            raise HTTPException(
                status_code=409,
                detail="Password authentication is already set up for this account. Use forgot-password to reset it.",
            )

        # Step 2: Validate password strength
        is_valid, error_message = password_service.validate_password_strength(request.password)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Step 3: Hash password
        hashed_password = await password_service.hash_password(request.password)

        # Step 4: Create AuthDetail for password authentication
        # Email is already verified through OAuth, so set email_verified_at immediately
        auth_detail = AuthDetail(
            user_id=current_user.id,
            auth_type="password",
            hashed_password=hashed_password,
            failed_login_attempts=0,
            email_verified_at=datetime.now(timezone.utc),  # Inherit verification from OAuth
            password_reset_token=None,
            password_reset_expires=None,
        )
        session.add(auth_detail)
        await session.commit()
        await session.refresh(auth_detail)

        # Step 5: Send confirmation email
        email_sent = await password_reset_service.send_password_set_confirmation_email(
            to_email=current_user.email,
            fullname=current_user.fullname,
        )

        if not email_sent:
            logger.warning(
                f"Failed to send password set confirmation email to {current_user.email}"
            )

        logger.info(f"Password authentication added for OAuth user: {current_user.email}")
        return SetPasswordResponse(
            message="Password set successfully! You can now login with email and password."
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"user_id": str(current_user.id), "email": current_user.email},
            tags={
                "component": "auth",
                "operation": "set_password",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"Set password failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to set password. Please try again.")


@router.post(
    "/request-otp",
    response_model=RequestOTPResponse,
    responses={
        200: {"model": RequestOTPResponse},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Request OTP for passwordless authentication (unified registration + login)",
)
@limiter.limit("6/hour")  # Max 6 OTP requests per hour per IP
async def request_otp(
    request: Request,
    otp_data: RequestOTPRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Request OTP for VISITOR user authentication (handles both new and returning users)

    This is a unified endpoint that handles both registration and login:
    - If user doesn't exist: Create new VISITOR user with auth_type='otp'
    - If user exists: Send OTP to existing user for login

    Process:
    1. Check if user exists with this email
    2. If new: Create VISITOR user with auth_type='otp' (no password)
    3. If existing: Find OTP AuthDetail
    4. Generate 6-digit OTP (5-minute expiry)
    5. Store OTP in email_verification_token field
    6. Send OTP email
    7. Return success with is_new_user flag

    Security features:
    - Rate limiting (3 requests per hour per IP)
    - OTP expires after 5 minutes
    - Max 3 verification attempts per OTP
    - Cryptographically secure OTP generation

    Note: This endpoint is specifically for VISITOR users (passwordless auth).
    CREATOR users should use /register endpoint with password.
    """
    try:
        # Step 1: Check if user exists
        existing_user = await UserRepository.get_by_email(session, otp_data.email)

        if existing_user:
            # Existing user - send OTP for login
            logger.info(f"Existing user requesting OTP: {otp_data.email}")

            # Find OTP AuthDetail
            result = await session.execute(
                select(AuthDetail)
                .where(AuthDetail.user_id == existing_user.id, AuthDetail.auth_type == "otp")
                .limit(1)
            )
            auth_detail = result.scalar_one_or_none()

            if not auth_detail:
                # User exists but doesn't have OTP auth - create it
                # Works for both VISITOR and CREATOR users
                account_label = "visitor" if existing_user.account_type == "visitor" else "creator"
                return await _create_otp_auth_for_user(
                    session=session,
                    user=existing_user,
                    otp_data=otp_data,
                    account_type_label=account_label,
                )

            # Generate OTP
            otp_code, otp_expires = email_verification_service.generate_otp_code()

            # Store OTP in email_verification_token field (reusing for OTP)
            auth_detail.email_verification_token = otp_code
            auth_detail.email_verification_token_expires = otp_expires
            auth_detail.failed_login_attempts = 0  # Reset attempts on new OTP request

            await session.commit()

            # Send OTP email (with custom domain if available)
            # Prioritize persona owner's domain if persona_username provided (whitelabel)
            custom_sender = None
            if otp_data.persona_username:
                custom_sender = await _get_custom_sender_by_username(
                    session, otp_data.persona_username
                )
            if not custom_sender:
                custom_sender = await _get_custom_sender_email(session, existing_user.id)
            email_sent = await email_verification_service.send_otp_email(
                to_email=otp_data.email,
                fullname=existing_user.fullname,
                otp_code=otp_code,
                purpose="login",
                from_email=custom_sender,
            )

            if not email_sent:
                logger.warning(f"Failed to send OTP email to {otp_data.email}")

            logger.info(f"OTP sent to existing user: {otp_data.email}")
            return RequestOTPResponse(
                success=True,
                message=f"Verification code sent to {otp_data.email}. Please check your inbox.",
                is_new_user=False,
                account_type=existing_user.account_type,
            )

        else:
            # New user - create VISITOR account with OTP auth
            logger.info(f"New user requesting OTP: {otp_data.email}")

            # Use provided fullname or fallback to email prefix
            fullname = otp_data.fullname
            if not fullname:
                # Extract name from email (before @) and capitalize
                email_prefix = otp_data.email.split("@")[0]
                # Replace dots/underscores with spaces and title case
                fullname = email_prefix.replace(".", " ").replace("_", " ").title()
                logger.info(f"No fullname provided - using email-based name: {fullname}")

            # Step 2: Create VISITOR user
            # Generate random username for visitor
            import secrets
            import string

            from shared.database.models.user import AccountType, OnboardingStatus

            max_attempts = 10
            username = None
            for attempt in range(max_attempts):
                random_suffix = "".join(
                    secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)
                )
                generated_username = f"visitor_{random_suffix}"

                # Check if username is unique
                existing = await UserRepository.get_by_username(session, generated_username)
                if not existing:
                    username = generated_username
                    logger.info(f"Generated random username for visitor: {username}")
                    break
            else:
                # Fallback: use UUID if all attempts failed
                username = f"visitor_{str(uuid.uuid4())[:8]}"
                logger.warning(
                    f"Failed to generate unique username after {max_attempts} attempts, using UUID-based: {username}"
                )

            user = await UserRepository.create_user(
                session=session,
                email=otp_data.email,
                fullname=fullname,  # Use email-based fallback if not provided
                username=username,
                phone=otp_data.phone,  # Optional phone number
                email_confirmed=False,  # Will be confirmed on OTP verification
                account_type=AccountType.VISITOR,
                onboarding_status=OnboardingStatus.FULLY_ONBOARDED,  # Visitors are auto-onboarded
            )

            # Step 3: Create AuthDetail with auth_type='otp' (no password)
            otp_code, otp_expires = email_verification_service.generate_otp_code()

            auth_detail = AuthDetail(
                user_id=user.id,
                auth_type="otp",
                hashed_password=None,  # OTP auth has no password
                failed_login_attempts=0,
                email_verified_at=None,  # Not verified yet
                email_verification_token=otp_code,  # Store OTP code
                email_verification_token_expires=otp_expires,
            )
            session.add(auth_detail)

            # Step 4: Create default free tier subscription
            from shared.database.models.tier_plan import SubscriptionStatus, UserSubscription

            try:
                free_tier_subscription = UserSubscription(
                    user_id=user.id,
                    tier_id=0,  # Free tier
                    status=SubscriptionStatus.ACTIVE,
                )
                session.add(free_tier_subscription)
                await session.flush()  # Validate before commit
                logger.info(f"Created free tier subscription for visitor: {otp_data.email}")
            except Exception as e:
                logger.error(f"Failed to create subscription for visitor {user.id}: {e}")
                await session.rollback()
                raise HTTPException(status_code=500, detail="Failed to create user account")

            await session.commit()
            await session.refresh(auth_detail)

            # Step 5: Send OTP email (with persona owner's custom domain if provided)
            # Use "email_capture" purpose if source is email_capture (from conversation),
            # otherwise use "verification" for regular signup
            custom_sender = None
            if otp_data.persona_username:
                custom_sender = await _get_custom_sender_by_username(
                    session, otp_data.persona_username
                )
            email_purpose = (
                "email_capture" if otp_data.source == "email_capture" else "verification"
            )
            email_sent = await email_verification_service.send_otp_email(
                to_email=otp_data.email,
                fullname=fullname,  # Use email-based fallback if not provided
                otp_code=otp_code,
                purpose=email_purpose,
                from_email=custom_sender,
            )

            if not email_sent:
                logger.warning(f"Failed to send OTP email to {otp_data.email}, but user created")

            logger.info(f"VISITOR user created and OTP sent: {otp_data.email}")
            return RequestOTPResponse(
                success=True,
                message=f"Verification code sent to {otp_data.email}. Please check your inbox.",
                is_new_user=True,
                account_type="visitor",  # Always visitor for new OTP users
            )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"email": otp_data.email, "fullname": otp_data.fullname},
            tags={
                "component": "auth",
                "operation": "request_otp",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"OTP request failed for {otp_data.email}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to send verification code. Please try again."
        )


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    responses={
        200: {"model": VerifyOTPResponse},
        400: {"model": ErrorResponse, "description": "Invalid or expired OTP"},
        403: {"model": ErrorResponse, "description": "Too many failed attempts"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Verify OTP and login",
)
async def verify_otp(
    otp_data: VerifyOTPRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Verify OTP code and authenticate user

    Process:
    1. Find user by email
    2. Find OTP AuthDetail
    3. Verify OTP code from email_verification_token field
    4. Check expiry (5 minutes) and attempts (max 3)
    5. On success: Mark email as verified, clear OTP, generate JWT
    6. On failure: Increment failed attempts, lock after 3 failures
    7. Set HTTP-only cookie and return user data

    Security features:
    - OTP expires after 5 minutes
    - Max 3 verification attempts per OTP
    - Account lockout after 3 failed attempts (must request new OTP)
    - HTTP-only cookie for JWT
    - Single-use OTP (cleared after successful verification)

    After successful verification:
    - User is logged in with JWT cookie
    - Email is marked as verified
    - OTP is cleared (single-use)
    - Failed attempts reset to 0
    """
    try:
        # Step 1: Find user by email
        user = await UserRepository.get_by_email(session, otp_data.email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Step 2: Find OTP AuthDetail
        result = await session.execute(
            select(AuthDetail)
            .where(AuthDetail.user_id == user.id, AuthDetail.auth_type == "otp")
            .limit(1)
        )
        auth_detail = result.scalar_one_or_none()

        if not auth_detail:
            raise HTTPException(
                status_code=400,
                detail="Invalid verification code",
            )

        # Step 3: Check if too many failed attempts
        if auth_detail.failed_login_attempts >= 3:
            raise HTTPException(
                status_code=403,
                detail="Too many failed attempts. Please request a new verification code.",
            )

        # Step 4: Check if OTP exists
        if not auth_detail.email_verification_token:
            raise HTTPException(
                status_code=400,
                detail="No verification code found. Please request a new one.",
            )

        # Step 5: Check OTP expiration
        if (
            not auth_detail.email_verification_token_expires
            or auth_detail.email_verification_token_expires < datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=400,
                detail="Verification code has expired. Please request a new one.",
            )

        # Step 6: Verify OTP code
        if auth_detail.email_verification_token != otp_data.otp_code:
            # Record failed attempt
            auth_detail.failed_login_attempts += 1
            await session.commit()

            remaining_attempts = 3 - auth_detail.failed_login_attempts
            if remaining_attempts > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid verification code. {remaining_attempts} attempt(s) remaining.",
                )
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Too many failed attempts. Please request a new verification code.",
                )

        # Step 7: Success - Mark email as verified and clear OTP
        auth_detail.email_verified_at = datetime.now(timezone.utc)
        auth_detail.email_verification_token = None
        auth_detail.email_verification_token_expires = None
        auth_detail.failed_login_attempts = 0  # Reset attempts

        # Update user email_confirmed status
        user.email_confirmed = True

        await session.commit()
        await session.refresh(user)

        # Step 8: Generate JWT token
        jwt_token = LinkedInOAuthService.create_jwt_token(
            user_id=str(user.id),
            email=user.email,
        )

        # Set HTTP-only cookie
        response.set_cookie(
            key="myclone_token",
            value=jwt_token,
            httponly=True,
            secure=settings.environment in ["production", "staging"],
            samesite="lax",
            max_age=60 * 60 * 24 * settings.jwt_expiration_days,
            domain=settings.cookie_domain,
        )

        logger.info(f"OTP verified and user logged in: {user.email}")

        return VerifyOTPResponse(
            success=True,
            message="Email verified successfully! You are now logged in.",
            user_id=str(user.id),
            email=user.email,
            fullname=user.fullname,
            account_type=user.account_type,
            token=jwt_token,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"email": otp_data.email},
            tags={
                "component": "auth",
                "operation": "verify_otp",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"OTP verification failed for {otp_data.email}: {e}")
        raise HTTPException(status_code=500, detail="Verification failed. Please try again.")
