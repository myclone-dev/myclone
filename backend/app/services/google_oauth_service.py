"""
Google OAuth service for authentication
"""

import logging
from typing import Any, Dict
from urllib.parse import urlencode

import httpx

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

# HTTP client timeout for Google API calls (10 seconds)
GOOGLE_API_TIMEOUT = 10.0


class GoogleOAuthService:
    """Service for Google OAuth authentication"""

    # Google OAuth endpoints
    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    # OAuth 2.0 constants (DO NOT MODIFY - defined by OAuth 2.0 spec)
    RESPONSE_TYPE_CODE = "code"  # OAuth 2.0 authorization code flow
    GRANT_TYPE_AUTH_CODE = "authorization_code"  # OAuth 2.0 grant type for code exchange

    # OpenID Connect scopes
    SCOPES = "openid profile email"  # Standard OIDC scopes for user info

    @staticmethod
    def get_authorization_url(state: str, redirect_uri: str) -> str:
        """
        Generate Google OAuth authorization URL

        Args:
            state: Random state string for CSRF protection
            redirect_uri: The callback URL

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "response_type": GoogleOAuthService.RESPONSE_TYPE_CODE,
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": GoogleOAuthService.SCOPES,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Force consent screen to get refresh token
        }
        return f"{GoogleOAuthService.AUTHORIZATION_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from Google
            redirect_uri: The callback URL (must match the one used in authorization)

        Returns:
            Token response from Google

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If Google returns an error response
        """
        try:
            async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
                response = await client.post(
                    GoogleOAuthService.TOKEN_URL,
                    data={
                        "grant_type": GoogleOAuthService.GRANT_TYPE_AUTH_CODE,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as e:
            logger.error(f"Timeout exchanging code for token: {e}")
            capture_exception_with_context(
                e,
                tags={
                    "component": "google_oauth",
                    "operation": "exchange_code_for_token",
                    "severity": "high",
                },
            )
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error exchanging code for token: {e.response.status_code}")
            capture_exception_with_context(
                e,
                extra={"status_code": e.response.status_code},
                tags={
                    "component": "google_oauth",
                    "operation": "exchange_code_for_token",
                    "severity": "high",
                },
            )
            raise

    @staticmethod
    async def get_user_info(access_token: str) -> Dict[str, Any]:
        """
        Fetch user information from Google

        Args:
            access_token: Google access token

        Returns:
            User profile information containing:
            - sub: Unique user identifier
            - email: User's email address
            - email_verified: Whether email is verified
            - name: Full name
            - given_name: First name
            - family_name: Last name
            - picture: Profile picture URL

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If Google returns an error response
        """
        try:
            async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
                response = await client.get(
                    GoogleOAuthService.USER_INFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching user info: {e}")
            capture_exception_with_context(
                e,
                tags={
                    "component": "google_oauth",
                    "operation": "get_user_info",
                    "severity": "high",
                },
            )
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching user info: {e.response.status_code}")
            capture_exception_with_context(
                e,
                extra={"status_code": e.response.status_code},
                tags={
                    "component": "google_oauth",
                    "operation": "get_user_info",
                    "severity": "high",
                },
            )
            raise
