"""
User repository for database operations
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.user import AuthDetail, User
from shared.utils.encryption import TokenEncryption


class UserRepository:
    """Repository for user-related database operations"""

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID"""
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Optional[User]:
        """Get user by email"""
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(session: AsyncSession, username: str) -> Optional[User]:
        """Get user by username"""
        result = await session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_linkedin_id(session: AsyncSession, linkedin_id: str) -> Optional[User]:
        """Get user by LinkedIn ID"""
        result = await session.execute(select(User).where(User.linkedin_id == linkedin_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_platform_id(
        session: AsyncSession, platform: str, platform_user_id: str
    ) -> Optional[User]:
        """
        Get user by OAuth platform and platform user ID.

        This is the preferred method for looking up users by OAuth provider,
        as it uses the auth_details table which properly tracks all OAuth providers.

        Args:
            session: Database session
            platform: OAuth platform name (e.g., 'google', 'linkedin')
            platform_user_id: The user's ID on the platform (e.g., Google's 'sub' claim)

        Returns:
            User if found, None otherwise
        """
        result = await session.execute(
            select(User)
            .join(AuthDetail)
            .where(
                AuthDetail.platform == platform,
                AuthDetail.platform_user_id == platform_user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(
        session: AsyncSession,
        email: str,
        fullname: str,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        avatar: Optional[str] = None,
        linkedin_id: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        location: Optional[str] = None,
        email_confirmed: bool = True,
        account_type=None,  # AccountType enum, defaults to 'creator' at DB level
        onboarding_status=None,  # OnboardingStatus enum, defaults to 'NOT_STARTED' at DB level
    ) -> User:
        """Create a new user"""
        from shared.database.models.user import AccountType

        user = User(
            email=email,
            phone=phone,
            username=username,
            fullname=fullname,
            avatar=avatar,
            linkedin_id=linkedin_id,
            linkedin_url=linkedin_url,
            location=location,
            email_confirmed=email_confirmed,
            account_type=account_type or AccountType.CREATOR,
            onboarding_status=onboarding_status,  # If None, DB default (NOT_STARTED) will be used
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def update_user(session: AsyncSession, user: User, **kwargs) -> User:
        """Update user fields"""
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def get_auth_detail(
        session: AsyncSession, user_id: uuid.UUID, platform: str
    ) -> Optional[AuthDetail]:
        """Get auth detail for a user and platform"""
        result = await session.execute(
            select(AuthDetail).where(AuthDetail.user_id == user_id, AuthDetail.platform == platform)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def get_decrypted_tokens(auth_detail: AuthDetail) -> tuple[str, Optional[str]]:
        """
        Get decrypted access and refresh tokens from auth detail

        Args:
            auth_detail: AuthDetail object with encrypted tokens

        Returns:
            Tuple of (decrypted_access_token, decrypted_refresh_token)

        Usage:
            auth_detail = await UserRepository.get_auth_detail(session, user_id, "linkedin")
            access_token, refresh_token = UserRepository.get_decrypted_tokens(auth_detail)
        """
        access_token = TokenEncryption.decrypt_token(auth_detail.access_token)
        refresh_token = (
            TokenEncryption.decrypt_token(auth_detail.refresh_token)
            if auth_detail.refresh_token
            else None
        )
        return access_token, refresh_token

    @staticmethod
    async def create_or_update_auth_detail(
        session: AsyncSession,
        user_id: uuid.UUID,
        platform: str,
        platform_user_id: str,
        platform_username: str,
        avatar: str,
        access_token: str,
        token_expiry,
        refresh_token: Optional[str] = None,
        auth_metadata: Optional[dict] = None,
    ) -> AuthDetail:
        """
        Create or update OAuth auth detail for a user

        Note: This method is for OAuth authentication only (LinkedIn, Google, etc.)
        For password authentication, use create_password_auth() instead.
        """
        # Determine auth_type from platform (linkedin -> linkedin_oauth)
        auth_type = f"{platform}_oauth"

        # Check if auth detail exists (by auth_type, not platform)
        result = await session.execute(
            select(AuthDetail).where(
                AuthDetail.user_id == user_id, AuthDetail.auth_type == auth_type
            )
        )
        existing = result.scalar_one_or_none()

        # Encrypt tokens before storing
        encrypted_access_token = TokenEncryption.encrypt_token(access_token)
        encrypted_refresh_token = (
            TokenEncryption.encrypt_token(refresh_token) if refresh_token else None
        )

        if existing:
            # Update existing
            existing.platform = platform
            existing.platform_user_id = platform_user_id
            existing.platform_username = platform_username
            existing.avatar = avatar
            existing.access_token = encrypted_access_token
            existing.refresh_token = encrypted_refresh_token
            existing.token_expiry = token_expiry
            existing.auth_metadata = auth_metadata or {}

            await session.commit()
            await session.refresh(existing)
            return existing
        else:
            # Create new
            auth_detail = AuthDetail(
                user_id=user_id,
                auth_type=auth_type,
                platform=platform,
                platform_user_id=platform_user_id,
                platform_username=platform_username,
                avatar=avatar,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expiry=token_expiry,
                auth_metadata=auth_metadata or {},
            )
            session.add(auth_detail)
            await session.commit()
            await session.refresh(auth_detail)
            return auth_detail

    # Password Authentication Methods

    @staticmethod
    async def get_password_auth(session: AsyncSession, user_id: uuid.UUID) -> Optional[AuthDetail]:
        """
        Get password authentication record for a user

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            AuthDetail with auth_type='password' or None

        Usage:
            password_auth = await UserRepository.get_password_auth(session, user.id)
            if password_auth and password_auth.email_verified_at:
                # User has verified password auth
        """
        result = await session.execute(
            select(AuthDetail).where(
                AuthDetail.user_id == user_id, AuthDetail.auth_type == "password"
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_auth_by_reset_token(session: AsyncSession, token: str) -> Optional[AuthDetail]:
        """
        Get authentication record by password reset token

        Args:
            session: Database session
            token: Password reset or verification token

        Returns:
            AuthDetail with matching token or None

        Usage:
            auth = await UserRepository.get_auth_by_reset_token(session, token)
            if auth and auth.password_reset_expires > datetime.now(timezone.utc):
                # Token is valid
        """
        result = await session.execute(
            select(AuthDetail).where(
                AuthDetail.password_reset_token == token, AuthDetail.auth_type == "password"
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_password_auth(
        session: AsyncSession,
        user_id: uuid.UUID,
        hashed_password: str,
        verification_token: Optional[str] = None,
        verification_expires: Optional = None,
    ) -> AuthDetail:
        """
        Create password authentication record for a user

        Args:
            session: Database session
            user_id: User UUID
            hashed_password: Bcrypt password hash
            verification_token: Optional email verification token
            verification_expires: Optional token expiration datetime

        Returns:
            Created AuthDetail record

        Usage:
            auth = await UserRepository.create_password_auth(
                session, user.id, hashed_password, token, expires
            )
        """
        auth_detail = AuthDetail(
            user_id=user_id,
            auth_type="password",
            hashed_password=hashed_password,
            failed_login_attempts=0,
            email_verified_at=None,
            password_reset_token=verification_token,
            password_reset_expires=verification_expires,
        )
        session.add(auth_detail)
        await session.commit()
        await session.refresh(auth_detail)
        return auth_detail
