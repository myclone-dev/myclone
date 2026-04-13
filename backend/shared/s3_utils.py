"""
Shared S3 utilities for file upload/download operations.

Used by both API (upload files) and workers (download, process, upload results).
"""

import os
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import UUID

import aioboto3
from loguru import logger


class S3Client:
    """Async S3 client for file operations."""

    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        """Initialize S3 client.

        Args:
            bucket_name: S3 bucket name
            region: AWS region (default: us-east-1)
        """
        if not bucket_name:
            raise ValueError("bucket_name cannot be empty")

        self.bucket_name = bucket_name
        self.region = region
        self.session = aioboto3.Session()
        self._bucket_validated = False

    async def _validate_bucket_exists(self) -> None:
        """Validate that the S3 bucket exists and is accessible.

        Raises:
            Exception: If bucket doesn't exist or is not accessible
        """
        if self._bucket_validated:
            return

        try:
            async with self.session.client("s3", region_name=self.region) as s3:
                await s3.head_bucket(Bucket=self.bucket_name)

            self._bucket_validated = True
            logger.info(f"✅ S3 bucket validated: {self.bucket_name}")

        except Exception as e:
            logger.error(
                f"❌ S3 bucket validation failed: {self.bucket_name} - {e}. "
                f"Ensure bucket exists and IAM permissions are configured correctly."
            )
            raise

    def _get_voice_processing_path(
        self, user_id: Optional[UUID], job_id: str, filename: str, category: str = "input"
    ) -> str:
        """Generate S3 path for voice processing files.

        Args:
            user_id: User ID (optional)
            job_id: Job ID
            filename: File name
            category: File category (input, output/raw, output/segments, temp)

        Returns:
            S3 key path
        """
        if category == "temp":
            return f"voice-processing/temp/{job_id}/{filename}"

        user_path = str(user_id) if user_id else "anonymous"
        return f"voice-processing/{category}/{user_path}/{job_id}/{filename}"

    async def upload_file(
        self,
        file_obj: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload file to S3.

        Args:
            file_obj: File object to upload
            key: S3 key (path)
            content_type: MIME type (optional)

        Returns:
            S3 URI (s3://bucket/key)

        Raises:
            Exception: If upload fails
        """
        # Validate bucket on first operation
        await self._validate_bucket_exists()

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            async with self.session.client("s3", region_name=self.region) as s3:
                await s3.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    key,
                    ExtraArgs=extra_args if extra_args else None,
                )

            s3_uri = f"s3://{self.bucket_name}/{key}"
            logger.info(f"✅ Uploaded file to S3: {s3_uri}")
            return s3_uri

        except Exception as e:
            logger.error(f"❌ Failed to upload to S3: {key} - {e}")
            raise

    async def upload_voice_input(
        self,
        file_obj: BinaryIO,
        filename: str,
        job_id: str,
        user_id: Optional[UUID] = None,
    ) -> str:
        """Upload voice processing input file.

        Args:
            file_obj: File object
            filename: Original filename
            job_id: Job ID
            user_id: User ID (optional)

        Returns:
            S3 URI
        """
        key = self._get_voice_processing_path(user_id, job_id, filename, "input")
        return await self.upload_file(file_obj, key)

    async def download_file(self, key: str, local_path: Path) -> Path:
        """Download file from S3.

        Args:
            key: S3 key (path)
            local_path: Local file path to save to

        Returns:
            Local file path

        Raises:
            Exception: If download fails
        """
        # Validate bucket on first operation
        await self._validate_bucket_exists()

        try:
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            async with self.session.client("s3", region_name=self.region) as s3:
                await s3.download_file(self.bucket_name, key, str(local_path))

            logger.info(
                f"✅ Downloaded file from S3: s3://{self.bucket_name}/{key} -> {local_path}"
            )
            return local_path

        except Exception as e:
            logger.error(f"❌ Failed to download from S3: {key} - {e}")
            raise

    async def download_from_uri(self, s3_uri: str, local_path: Path) -> Path:
        """Download file from S3 URI.

        Args:
            s3_uri: S3 URI (s3://bucket/key)
            local_path: Local file path

        Returns:
            Local file path
        """
        # Parse S3 URI
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")

        parts = s3_uri[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")

        bucket, key = parts

        if bucket != self.bucket_name:
            logger.warning(
                f"S3 URI bucket ({bucket}) differs from client bucket ({self.bucket_name})"
            )

        return await self.download_file(key, local_path)

    async def copy_object(
        self,
        source_key: str,
        dest_key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """Copy object from source to destination within the same bucket (server-side copy).

        This is faster and cheaper than download+upload as the copy happens server-side
        without data transfer through the client.

        Args:
            source_key: Source S3 key (path within bucket)
            dest_key: Destination S3 key (path within bucket)
            metadata: Optional metadata for destination object
            content_type: Optional content type for destination object

        Returns:
            S3 URI of destination object (s3://bucket/dest_key)

        Raises:
            Exception: If copy fails (source not found, permission denied, etc.)
        """
        # Validate bucket on first operation
        await self._validate_bucket_exists()

        try:
            async with self.session.client("s3", region_name=self.region) as s3:
                copy_source = {"Bucket": self.bucket_name, "Key": source_key}

                # Build copy parameters
                copy_params = {
                    "CopySource": copy_source,
                    "Bucket": self.bucket_name,
                    "Key": dest_key,
                }

                # Add optional metadata
                if metadata:
                    copy_params["Metadata"] = metadata
                    copy_params["MetadataDirective"] = "REPLACE"
                else:
                    copy_params["MetadataDirective"] = "COPY"  # Preserve original metadata

                # Add optional content type
                if content_type:
                    copy_params["ContentType"] = content_type

                # Perform server-side copy
                await s3.copy_object(**copy_params)

            dest_uri = f"s3://{self.bucket_name}/{dest_key}"
            logger.info(f"✅ Server-side copy completed: {source_key} -> {dest_key}")
            return dest_uri

        except Exception as e:
            logger.error(f"❌ Failed to copy object in S3: {source_key} -> {dest_key} - {e}")
            raise

    async def copy_from_uri(
        self,
        source_uri: str,
        dest_key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """Copy object from S3 URI to destination key (server-side copy).

        Args:
            source_uri: Source S3 URI (s3://bucket/key)
            dest_key: Destination S3 key (path within bucket)
            metadata: Optional metadata for destination object
            content_type: Optional content type for destination object

        Returns:
            S3 URI of destination object

        Raises:
            ValueError: If source URI is invalid or from different bucket
            Exception: If copy fails
        """
        # Parse source URI
        if not source_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {source_uri}")

        parts = source_uri[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {source_uri}")

        source_bucket, source_key = parts

        # Ensure same bucket (cross-bucket copy requires additional permissions)
        if source_bucket != self.bucket_name:
            raise ValueError(
                f"Cross-bucket copy not supported. Source bucket ({source_bucket}) "
                f"differs from client bucket ({self.bucket_name})"
            )

        return await self.copy_object(source_key, dest_key, metadata, content_type)

    async def download_to_bytes(self, s3_uri: str) -> bytes:
        """Download file from S3 URI directly to memory as bytes.

        Args:
            s3_uri: S3 URI (s3://bucket/key)

        Returns:
            File content as bytes

        Raises:
            ValueError: If S3 URI is invalid
            Exception: If download fails
        """
        # Parse S3 URI
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")

        parts = s3_uri[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")

        bucket, key = parts

        if bucket != self.bucket_name:
            logger.warning(
                f"S3 URI bucket ({bucket}) differs from client bucket ({self.bucket_name})"
            )

        # Validate bucket on first operation
        await self._validate_bucket_exists()

        try:
            async with self.session.client("s3", region_name=self.region) as s3:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                content = await response["Body"].read()

            logger.info(f"✅ Downloaded {len(content)} bytes from S3: {s3_uri}")
            return content

        except Exception as e:
            logger.error(f"❌ Failed to download from S3: {s3_uri} - {e}")
            raise

    async def upload_voice_output(
        self,
        file_path: Path,
        job_id: str,
        output_type: str = "raw",
        user_id: Optional[UUID] = None,
    ) -> str:
        """Upload voice processing output file.

        Args:
            file_path: Local file path
            job_id: Job ID
            output_type: Output type (raw, segments)
            user_id: User ID (optional)

        Returns:
            S3 URI
        """
        filename = file_path.name
        key = self._get_voice_processing_path(user_id, job_id, filename, f"output/{output_type}")

        with open(file_path, "rb") as f:
            return await self.upload_file(f, key)

    async def list_objects(self, prefix: str) -> list[str]:
        """List objects with given prefix.

        Args:
            prefix: S3 key prefix

        Returns:
            List of S3 keys
        """
        try:
            async with self.session.client("s3", region_name=self.region) as s3:
                response = await s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

                if "Contents" not in response:
                    return []

                return [obj["Key"] for obj in response["Contents"]]

        except Exception as e:
            logger.error(f"❌ Failed to list objects: {prefix} - {e}")
            raise

    async def delete_object(self, key: str) -> None:
        """Delete object from S3.

        Args:
            key: S3 key
        """
        try:
            async with self.session.client("s3", region_name=self.region) as s3:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)

            logger.info(f"✅ Deleted object from S3: s3://{self.bucket_name}/{key}")

        except Exception as e:
            logger.error(f"❌ Failed to delete from S3: {key} - {e}")
            raise


def get_s3_client(bucket_name: Optional[str] = None, region: Optional[str] = None) -> S3Client:
    """Get S3 client instance.

    Args:
        bucket_name: Override default bucket (uses USER_DATA_BUCKET env var if not provided)
        region: AWS region (uses AWS_REGION env var if not provided)

    Returns:
        S3Client instance
    """
    if bucket_name is None:
        bucket_name = os.getenv("USER_DATA_BUCKET", "myclone-user-data-dev")

    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")

    return S3Client(bucket_name=bucket_name, region=region)
