"""Centralized S3 service for uploading and downloading files across the application."""

import logging
import os
from typing import Optional

import aioboto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Service:
    """Service for interacting with S3 storage (supports LocalStack and AWS)."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: Optional[str] = None,
        directory: Optional[str] = None,
    ):
        """
        Initialize S3 service.

        Supports three deployment scenarios:
        1. LocalStack (local dev): endpoint_url with port 4566 or 'localstack' → uses unsigned requests
        2. Production with IAM role: no endpoint_url, no credentials → uses IAM role automatically
        3. Production with explicit credentials: no endpoint_url, has credentials → uses provided credentials

        Args:
            endpoint_url: S3 endpoint URL (for LocalStack). Empty/None = use real AWS S3
            bucket_name: S3 bucket name
            access_key_id: AWS access key ID (optional for LocalStack and IAM-based access)
            secret_access_key: AWS secret access key (optional for LocalStack and IAM-based access)
            region: AWS region
            directory: S3 directory prefix (default: from S3_DOCUMENT_PREFIX env or 'documents')
        """
        self.session = aioboto3.Session()
        self.endpoint_url = endpoint_url or os.getenv("AWS_ENDPOINT_URL", "")
        self.directory = directory or os.getenv("S3_DOCUMENT_PREFIX", "documents")
        self.bucket_name = bucket_name or os.getenv(
            "USER_DATA_BUCKET", "myclone-user-data-production"
        )
        self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        # Detect LocalStack usage (port 4566 or 'localstack' in URL)
        self.use_localstack = bool(
            self.endpoint_url
            and ("localstack" in self.endpoint_url.lower() or "4566" in self.endpoint_url)
        )

    def _get_client_kwargs(self):
        """
        Get client configuration kwargs for boto3/aioboto3.

        Deployment scenarios:
        1. LocalStack: Uses unsigned requests (no credentials needed)
        2. Production with IAM: Uses default credential chain (IAM role, no explicit credentials)
        3. Production with explicit credentials: Uses provided AWS access key/secret
        """
        kwargs = {"region_name": self.region}

        # Add endpoint_url only for LocalStack or custom endpoints
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url

        # Determine authentication strategy
        if self.use_localstack:
            # LocalStack: Use unsigned requests (no credentials needed)
            kwargs["config"] = Config(signature_version=UNSIGNED)
            logger.debug("Using unsigned requests for LocalStack (no credentials)")
        elif self.access_key_id and self.secret_access_key:
            # Production with explicit credentials: Use provided credentials from AWS_SECRETS JSON
            kwargs["aws_access_key_id"] = self.access_key_id
            kwargs["aws_secret_access_key"] = self.secret_access_key
            logger.debug("Using explicit AWS credentials from environment/secrets")
        else:
            # Production with IAM role: Let boto3 use default credential chain
            # This will automatically use the IAM role attached to EC2/ECS/Lambda
            logger.debug("Using IAM role for AWS S3 access (default credential chain)")

        return kwargs

    async def upload_file(
        self,
        file_content: bytes,
        user_id: str,
        filename: str,
        content_type: str = "application/octet-stream",
        directory: Optional[str] = None,
    ) -> str:
        """
        Upload a file to S3.

        Args:
            file_content: The file content as bytes
            user_id: The user ID (used in S3 key path)
            filename: The filename
            content_type: The content type of the file
            directory: Optional directory override (thread-safe alternative to modifying self.directory)

        Returns:
            The S3 path (s3://bucket/user-id/filename)
        """
        upload_directory = directory if directory is not None else self.directory
        s3_key = f"{upload_directory}/{user_id}/{filename}"

        try:
            async with self.session.client("s3", **self._get_client_kwargs()) as s3_client:
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=content_type,
                )

                s3_path = f"s3://{self.bucket_name}/{s3_key}"
                logger.info(f"Successfully uploaded file to S3: {s3_path}")
                return s3_path

        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise Exception(f"S3 upload failed: {str(e)}")

    async def download_file(self, s3_path: str, local_path: str) -> str:
        """
        Download a file from S3.

        Args:
            s3_path: The S3 path (s3://bucket/key)
            local_path: The local file path to save to

        Returns:
            The local file path
        """
        # Parse S3 path
        if not s3_path.startswith("s3://"):
            raise ValueError(f"Invalid S3 path: {s3_path}")

        # Extract bucket and key from s3://bucket/key
        path_parts = s3_path[5:].split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ""

        try:
            async with self.session.client("s3", **self._get_client_kwargs()) as s3_client:
                response = await s3_client.get_object(Bucket=bucket, Key=key)

                # Read the file content
                async with response["Body"] as stream:
                    content = await stream.read()

                # Write to local file
                with open(local_path, "wb") as f:
                    f.write(content)

                logger.info(f"Successfully downloaded file from S3: {s3_path} to {local_path}")
                return local_path

        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise Exception(f"S3 download failed: {str(e)}")

    async def delete_file(self, s3_path: str) -> bool:
        """
        Delete a file from S3.

        Args:
            s3_path: The S3 path (s3://bucket/key)

        Returns:
            True if successful, False otherwise
        """
        # Parse S3 path
        if not s3_path.startswith("s3://"):
            raise ValueError(f"Invalid S3 path: {s3_path}")

        path_parts = s3_path[5:].split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ""

        try:
            async with self.session.client("s3", **self._get_client_kwargs()) as s3_client:
                await s3_client.delete_object(Bucket=bucket, Key=key)
                logger.info(f"Successfully deleted file from S3: {s3_path}")
                return True

        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False

    async def file_exists(self, s3_path: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            s3_path: The S3 path (s3://bucket/key)

        Returns:
            True if file exists, False otherwise
        """
        # Parse S3 path
        if not s3_path.startswith("s3://"):
            raise ValueError(f"Invalid S3 path: {s3_path}")

        path_parts = s3_path[5:].split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ""

        try:
            async with self.session.client("s3", **self._get_client_kwargs()) as s3_client:
                await s3_client.head_object(Bucket=bucket, Key=key)
                return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return False
            logger.error(f"Error checking if file exists in S3: {e}")
            return False

    def get_public_url(self, s3_key: str) -> str:
        """
        Generate a public HTTPS URL for an S3 object.

        This URL format works for publicly accessible S3 buckets.
        For private buckets, use generate_presigned_url instead.

        Args:
            s3_key: The S3 object key (path within bucket)

        Returns:
            Public HTTPS URL: https://bucket.s3.region.amazonaws.com/key
        """
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

    async def generate_presigned_url(
        self,
        s3_key: str,
        expiration_seconds: int = 3600,
    ) -> Optional[str]:
        """
        Generate a presigned URL for secure, time-limited access to S3 objects.

        This is useful for private buckets where you want to grant temporary
        access to specific objects (e.g., voice recordings).

        Args:
            s3_key: The S3 object key (e.g., recordings/voice/{persona_id}/{session_id}.mp4)
            expiration_seconds: URL validity duration in seconds (default 1 hour)

        Returns:
            Presigned URL string or None if generation fails
        """
        from shared.monitoring.sentry_utils import capture_exception_with_context

        try:
            # For LocalStack, return a direct URL (presigned not needed in dev)
            if self.use_localstack:
                local_url = f"{self.endpoint_url}/{self.bucket_name}/{s3_key}"
                logger.debug(f"LocalStack: returning direct URL for {s3_key}")
                return local_url

            # Generate presigned URL for production
            async with self.session.client("s3", **self._get_client_kwargs()) as s3_client:
                url = await s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": s3_key},
                    ExpiresIn=expiration_seconds,
                )

                logger.info(
                    f"Generated presigned URL for {s3_key} (expires in {expiration_seconds}s)"
                )
                return url

        except ClientError as e:
            capture_exception_with_context(
                e,
                extra={"s3_key": s3_key, "expiration": expiration_seconds},
                tags={"service": "s3", "operation": "presigned_url"},
            )
            logger.error(f"Failed to generate presigned URL for {s3_key}: {e}")
            return None

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"s3_key": s3_key, "expiration": expiration_seconds},
                tags={"service": "s3", "operation": "presigned_url"},
            )
            logger.error(f"Unexpected error generating presigned URL for {s3_key}: {e}")
            return None

    async def ensure_bucket_exists(self) -> bool:
        """
        Ensure the bucket exists, create it if it doesn't.

        Returns:
            True if bucket exists or was created successfully
        """
        try:
            async with self.session.client("s3", **self._get_client_kwargs()) as s3_client:
                try:
                    await s3_client.head_bucket(Bucket=self.bucket_name)
                    logger.info(f"Bucket {self.bucket_name} already exists")
                    return True
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "404":
                        # Bucket doesn't exist, create it
                        await s3_client.create_bucket(Bucket=self.bucket_name)
                        logger.info(f"Created bucket {self.bucket_name}")
                        return True
                    else:
                        raise

        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            return False


# Singleton instance
_s3_service_instance: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get S3 service singleton instance."""
    global _s3_service_instance
    if _s3_service_instance is None:
        _s3_service_instance = S3Service()
    return _s3_service_instance


def create_s3_service(
    endpoint_url: Optional[str] = None,
    bucket_name: Optional[str] = None,
    access_key_id: Optional[str] = None,
    secret_access_key: Optional[str] = None,
    region: Optional[str] = None,
    directory: Optional[str] = None,
) -> S3Service:
    """
    Create a new S3 service instance with custom configuration.

    Args:
        endpoint_url: S3 endpoint URL
        bucket_name: S3 bucket name
        access_key_id: AWS access key ID
        secret_access_key: AWS secret access key
        region: AWS region
        directory: S3 directory prefix

    Returns:
        New S3Service instance
    """
    return S3Service(
        endpoint_url=endpoint_url,
        bucket_name=bucket_name,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        region=region,
        directory=directory,
    )
