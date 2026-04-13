"""
API Key authentication middleware for Expert Clone service
Simplified to use environment variable only (no database)
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.config import settings

logger = logging.getLogger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


class APIKeyAuth:
    """API Key authentication for service-to-service communication"""

    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        """Verify the provided API key against environment variable"""
        if settings.api_key and api_key == settings.api_key:
            logger.debug("API key validated against environment variable")
            return True
        return False

    @staticmethod
    def extract_api_key(request: Request) -> Optional[str]:
        """Extract API key from various request sources"""
        # Check Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix

        # Check X-API-Key header
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            return api_key_header

        # Check query parameter (less secure, for testing only)
        api_key_param = request.query_params.get("api_key")
        if api_key_param:
            logger.warning("API key provided via query parameter - consider using headers instead")
            return api_key_param

        return None


async def require_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to require valid API key for endpoint access"""

    # If API key requirement is disabled, allow all requests
    if not settings.require_api_key:
        logger.debug("API key requirement disabled - allowing request")
        return True

    # Extract API key from credentials
    if not credentials:
        logger.error("API key required but not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide key in Authorization header as 'Bearer <key>' or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = credentials.credentials

    # Verify API key against environment variable
    if not APIKeyAuth.verify_api_key(api_key):
        logger.error(f"Invalid API key provided: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"Valid API key provided: {api_key[:8]}...")
    return True


def optional_api_key(request: Request) -> Optional[str]:
    """Extract API key if provided, but don't require it"""
    return APIKeyAuth.extract_api_key(request)


# Convenience function for route protection
def protected_endpoint():
    """Decorator-style dependency for protecting endpoints"""
    return Depends(require_api_key)
