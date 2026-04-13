"""
S3 Avatar Upload Service - Async Implementation
Handles uploading user avatars from URLs to S3 storage using aioboto3
"""

import logging
import mimetypes
from typing import Optional

import aioboto3
import httpx
from botocore.exceptions import ClientError

from shared.config import settings

logger = logging.getLogger(__name__)

# Maximum avatar file size (10MB)
MAX_AVATAR_SIZE = 10 * 1024 * 1024


def is_s3_avatar_url(avatar_url: str) -> bool:
    """
    Check if avatar URL is already hosted on S3 (user-data bucket).

    Returns True if URL matches S3 pattern with the avatars path
    and contains the configured bucket name.
    """
    if not avatar_url:
        return False

    # Check for S3 URL patterns (both regional and non-regional)
    # Must contain both S3 indicators AND the avatars path
    is_s3 = ".s3" in avatar_url and "amazonaws.com" in avatar_url and "/avatars/" in avatar_url

    # Check if it's in our configured user-data bucket
    is_our_bucket = settings.user_data_bucket in avatar_url

    return is_s3 and is_our_bucket


def is_s3_url(url: str) -> bool:
    """
    Check if URL is hosted on S3 (any bucket/path)

    Returns True if URL matches S3 pattern:
    - https://*.s3.amazonaws.com/* (us-east-1 default)
    - https://*.s3.*.amazonaws.com/* (regional)
    """
    if not url:
        return False

    # Check for S3 URL patterns (both regional and non-regional)
    return ".s3" in url and "amazonaws.com" in url


def get_content_type_from_extension(extension: str) -> str:
    """Get content type from file extension"""
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return content_types.get(extension.lower(), "image/jpeg")


async def upload_avatar_from_url(
    avatar_url: str,
    user_id: str,
) -> Optional[str]:
    """
    Upload avatar from URL to S3 (fully async)

    Args:
        avatar_url: Source URL of the avatar image
        user_id: User UUID (used for S3 key naming)

    Returns:
        S3 URL if successful, None if failed

    Note: This function is non-blocking - failures are logged but don't raise exceptions
    """

    if not avatar_url:
        logger.warning("Empty avatar URL provided")
        return None

    # Skip if already on S3
    if is_s3_avatar_url(avatar_url):
        logger.info(f"Avatar already on S3, skipping upload: {avatar_url}")
        return avatar_url

    try:
        # Special handling for LinkedIn URLs
        is_linkedin_url = (
            "licdn.com" in avatar_url
            or "linkedin.com" in avatar_url
            or "profile-displayphoto" in avatar_url
        )

        # Download avatar image using httpx (async)
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            headers = {}

            if is_linkedin_url:
                # LinkedIn requires specific headers
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.linkedin.com/",
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                }
                logger.info(f"Downloading LinkedIn avatar with special headers: {avatar_url}")

            response = await http_client.get(avatar_url, headers=headers, follow_redirects=True)

            if response.status_code != 200:
                logger.warning(
                    f"Failed to download avatar (HTTP {response.status_code}): {avatar_url}"
                )
                return None

            # Check file size
            avatar_data = response.content
            if len(avatar_data) > MAX_AVATAR_SIZE:
                logger.warning(f"Avatar too large ({len(avatar_data)} bytes): {avatar_url}")
                return None

            # Determine file extension
            content_type = response.headers.get("Content-Type", "")
            extension = mimetypes.guess_extension(content_type) or ".jpg"

            # Generate S3 key: avatars/{user_id}.{ext}
            s3_key = f"avatars/{user_id}{extension}"

        # Upload to S3 using aioboto3 (async)
        # Production (ECS): Uses IAM role - credentials are optional
        # Local dev: Uses explicit credentials if provided
        session_kwargs = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        session = aioboto3.Session(**session_kwargs)

        async with session.client("s3") as s3_client:
            # Note: Don't set ContentLength explicitly - aioboto3 handles it automatically
            # Setting it manually causes "chunked can not be set if Content-Length header is set" error
            await s3_client.put_object(
                Bucket=settings.user_data_bucket,  # Use myclone-user-data-{env} bucket
                Key=s3_key,
                Body=avatar_data,
                ContentType=get_content_type_from_extension(extension),
            )

        # Generate S3 URL
        s3_url = (
            f"https://{settings.user_data_bucket}.s3."
            f"{settings.aws_region}.amazonaws.com/{s3_key}"
        )

        logger.info(
            "Avatar uploaded successfully to S3",
            extra={
                "user_id": user_id,
                "original_url": avatar_url,
                "s3_url": s3_url,
                "size_bytes": len(avatar_data),
            },
        )

        return s3_url

    except ClientError as e:
        logger.error(f"S3 upload failed for user {user_id}: {e}", exc_info=True)
        return None

    except httpx.HTTPError as e:
        logger.error(f"HTTP error downloading avatar for user {user_id}: {e}", exc_info=True)
        return None

    except Exception as e:
        logger.error(f"Unexpected error uploading avatar for user {user_id}: {e}", exc_info=True)
        return None
