"""
LinkedIn OAuth service for authentication
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
import jwt

from shared.config import settings

logger = logging.getLogger(__name__)


class LinkedInOAuthService:
    """Service for LinkedIn OAuth authentication"""

    # LinkedIn OAuth endpoints
    AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USER_INFO_URL = "https://api.linkedin.com/v2/userinfo"

    # OAuth 2.0 constants (DO NOT MODIFY - defined by OAuth 2.0 spec)
    RESPONSE_TYPE_CODE = "code"  # OAuth 2.0 authorization code flow
    GRANT_TYPE_AUTH_CODE = "authorization_code"  # OAuth 2.0 grant type for code exchange

    # OpenID Connect scopes
    SCOPES = "openid profile email"  # Standard OIDC scopes for user info

    @staticmethod
    def get_authorization_url(state: str, redirect_uri: str) -> str:
        """
        Generate LinkedIn OAuth authorization URL

        Args:
            state: Random state string for CSRF protection
            redirect_uri: The callback URL

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "response_type": LinkedInOAuthService.RESPONSE_TYPE_CODE,
            "client_id": settings.linkedin_client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": LinkedInOAuthService.SCOPES,
        }
        return f"{LinkedInOAuthService.AUTHORIZATION_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from LinkedIn
            redirect_uri: The callback URL (must match the one used in authorization)

        Returns:
            Token response from LinkedIn
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LinkedInOAuthService.TOKEN_URL,
                data={
                    "grant_type": LinkedInOAuthService.GRANT_TYPE_AUTH_CODE,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.linkedin_client_id,
                    "client_secret": settings.linkedin_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def get_user_info(access_token: str) -> Dict[str, Any]:
        """
        Fetch user information from LinkedIn

        Args:
            access_token: LinkedIn access token

        Returns:
            User profile information
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                LinkedInOAuthService.USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def create_jwt_token(user_id: str, email: str) -> str:
        """
        Create a JWT token for the user

        Args:
            user_id: User's UUID
            email: User's email

        Returns:
            JWT token string
        """
        expiration = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiration_days)

        payload = {
            "user_id": str(user_id),
            "email": email,
            "exp": expiration,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        return token

    @staticmethod
    def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None

    @staticmethod
    def generate_username_from_email(email: str) -> str:
        """
        Generate a username from email address

        Args:
            email: User's email address

        Returns:
            Generated username
        """
        # Take the part before @ and clean it up
        username = email.split("@")[0]
        # Remove any special characters except underscore and dash
        username = "".join(c if c.isalnum() or c in ["_", "-"] else "" for c in username)
        return username.lower()
