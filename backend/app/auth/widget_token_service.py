"""
Widget token service for chat widget authentication
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database.models.widget_token import WidgetToken

logger = logging.getLogger(__name__)


class WidgetTokenService:
    """Service for widget token generation and validation"""

    TOKEN_PREFIX = "wgt_"
    TOKEN_TYPE = "widget"

    @staticmethod
    def generate_widget_token(user_id: UUID, expert_username: str) -> str:
        """
        Generate a new widget token (JWT with wgt_ prefix)

        Args:
            user_id: User's UUID
            expert_username: User's expert username

        Returns:
            Widget token string with wgt_ prefix
        """
        payload = {
            "user_id": str(user_id),
            "expert_username": expert_username,
            "token_type": WidgetTokenService.TOKEN_TYPE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "jti": secrets.token_hex(16),  # Unique token identifier
        }

        # Widget tokens don't expire - they must be explicitly revoked
        jwt_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        # Add wgt_ prefix
        return f"{WidgetTokenService.TOKEN_PREFIX}{jwt_token}"

    @staticmethod
    def verify_widget_token_format(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify widget token format and decode JWT payload

        Args:
            token: Widget token string (with or without wgt_ prefix)

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            # Remove wgt_ prefix if present
            if token.startswith(WidgetTokenService.TOKEN_PREFIX):
                jwt_token = token[len(WidgetTokenService.TOKEN_PREFIX) :]
            else:
                jwt_token = token

            # Decode JWT (no expiration check)
            payload = jwt.decode(
                jwt_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False},  # Don't verify expiration
            )

            # Verify token_type
            if payload.get("token_type") != WidgetTokenService.TOKEN_TYPE:
                logger.warning(f"Invalid token type: {payload.get('token_type')}")
                return None

            return payload

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid widget token: {e}")
            return None

    @staticmethod
    async def validate_widget_token(
        token: str, expected_username: str, session: AsyncSession
    ) -> Optional[WidgetToken]:
        """
        Validate widget token and check against database

        Args:
            token: Widget token string
            expected_username: Expected expert username from URL path
            session: Database session

        Returns:
            WidgetToken ORM object if valid and active, None otherwise
        """
        # 1. Verify token format and decode
        payload = WidgetTokenService.verify_widget_token_format(token)
        if not payload:
            return None

        # 2. Verify username matches expected
        token_username = payload.get("expert_username")
        if token_username != expected_username:
            logger.warning(
                f"Widget token username mismatch: {token_username} != {expected_username}"
            )
            return None

        # 3. Check token exists in database and is not revoked
        try:
            stmt = select(WidgetToken).where(WidgetToken.token == token)
            result = await session.execute(stmt)
            widget_token = result.scalar_one_or_none()

            if not widget_token:
                logger.warning("Widget token not found in database")
                return None

            if not widget_token.is_active:
                logger.warning(f"Widget token is revoked: {widget_token.id}")
                return None

            # Update last_used_at
            widget_token.last_used_at = datetime.now(timezone.utc)
            session.add(widget_token)
            await session.commit()

            return widget_token

        except Exception as e:
            logger.error(f"Error validating widget token: {e}")
            return None

    @staticmethod
    async def create_token(
        user_id: UUID,
        expert_username: str,
        name: str,
        description: Optional[str],
        session: AsyncSession,
    ) -> WidgetToken:
        """
        Create a new widget token

        Args:
            user_id: User's UUID
            expert_username: User's expert username
            name: Token name
            description: Optional description
            session: Database session

        Returns:
            New WidgetToken ORM object
        """
        # Generate token
        token_string = WidgetTokenService.generate_widget_token(user_id, expert_username)

        # Create new token
        new_token = WidgetToken(
            user_id=user_id,
            token=token_string,
            name=name,
            description=description,
        )

        session.add(new_token)
        await session.commit()
        await session.refresh(new_token)

        logger.info(f"Created widget token '{name}' for user {user_id}")
        return new_token

    @staticmethod
    async def get_all_tokens(user_id: UUID, session: AsyncSession) -> List[WidgetToken]:
        """
        Get all widget tokens for a user (including revoked)

        Args:
            user_id: User's UUID
            session: Database session

        Returns:
            List of WidgetToken ORM objects ordered by creation date (newest first)
        """
        stmt = (
            select(WidgetToken)
            .where(WidgetToken.user_id == user_id)
            .order_by(WidgetToken.created_at.desc())
        )
        result = await session.execute(stmt)
        tokens = result.scalars().all()

        return list(tokens)

    @staticmethod
    async def revoke_token(token_id: UUID, user_id: UUID, session: AsyncSession) -> bool:
        """
        Revoke a specific widget token

        Args:
            token_id: Token's UUID
            user_id: User's UUID (for authorization)
            session: Database session

        Returns:
            True if token was revoked, False if not found or already revoked
        """
        stmt = select(WidgetToken).where(
            WidgetToken.id == token_id,
            WidgetToken.user_id == user_id,
            WidgetToken.revoked_at.is_(None),
        )
        result = await session.execute(stmt)
        token = result.scalar_one_or_none()

        if not token:
            return False

        # Revoke the token
        token.revoked_at = datetime.now(timezone.utc)
        session.add(token)
        await session.commit()

        logger.info(f"Revoked widget token {token_id} for user {user_id}")
        return True
