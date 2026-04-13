"""OCR Service for extracting text from images using GPT-4o Vision."""

import base64
import logging
import re
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result of OCR extraction from an image."""

    extracted_text: str
    description: str
    method: str = "gpt4_vision"
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "extracted_text": self.extracted_text,
            "description": self.description,
            "method": self.method,
            "success": self.success,
            "error": self.error,
        }


class OCRService:
    """
    Service for extracting text from images using GPT-4o Vision.

    This service processes images uploaded in chat to extract:
    1. All visible text (OCR)
    2. A description of the image content
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4o"  # Using GPT-4o for vision capabilities
        self.logger = logging.getLogger(__name__)

    async def extract_text_from_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        filename: Optional[str] = None,
    ) -> OCRResult:
        """
        Extract text and description from an image using GPT-4o Vision.

        Args:
            image_bytes: Raw bytes of the image
            mime_type: MIME type of the image (e.g., 'image/png', 'image/jpeg')
            filename: Optional filename for logging

        Returns:
            OCRResult with extracted text and description
        """
        try:
            self.logger.info(
                f"Starting OCR extraction for image: {filename or 'unknown'} "
                f"({len(image_bytes)} bytes, {mime_type})"
            )

            # Convert image to base64
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Build the vision request
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this image thoroughly and provide:

1. **TEXT EXTRACTION**: Extract ALL text visible in the image, preserving the layout and structure as much as possible. Include:
   - Headers, titles, labels
   - Body text, paragraphs
   - Numbers, dates, figures
   - Text in tables, charts, or diagrams
   - Watermarks or stamps
   - Any handwritten text

2. **IMAGE DESCRIPTION**: Provide a concise description of what the image contains, including:
   - Type of document/image (e.g., receipt, form, screenshot, photo)
   - Key visual elements
   - Any charts, graphs, or diagrams explained
   - Overall context and purpose

Format your response EXACTLY as follows:

[EXTRACTED_TEXT]
<all text from the image here, preserving structure>

[DESCRIPTION]
<concise description of the image content>

If there is no text in the image, write "No text detected" in the EXTRACTED_TEXT section.""",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}",
                                    "detail": "high",  # Use high detail for better OCR
                                },
                            },
                        ],
                    }
                ],
                max_tokens=4096,
                temperature=0.1,  # Low temperature for more accurate extraction
            )

            content = response.choices[0].message.content
            self.logger.info(f"OCR response received: {len(content)} characters")

            # Parse the response
            extracted_text, description = self._parse_ocr_response(content)

            self.logger.info(
                f"OCR extraction completed: {len(extracted_text)} chars text, "
                f"{len(description)} chars description"
            )

            return OCRResult(
                extracted_text=extracted_text,
                description=description,
                method="gpt4_vision",
                success=True,
            )

        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            capture_exception_with_context(
                e,
                extra={
                    "filename": filename,
                    "mime_type": mime_type,
                    "image_size_bytes": len(image_bytes) if image_bytes else 0,
                },
                tags={
                    "component": "ocr_service",
                    "operation": "extract_text_from_image",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            return OCRResult(
                extracted_text="",
                description="",
                method="gpt4_vision",
                success=False,
                error=str(e),
            )

    def _parse_ocr_response(self, content: str) -> tuple[str, str]:
        """
        Parse the OCR response to extract text and description sections.

        Args:
            content: Raw response from GPT-4o

        Returns:
            Tuple of (extracted_text, description)
        """
        extracted_text = ""
        description = ""

        # Try to parse structured format
        text_match = re.search(
            r"\[EXTRACTED_TEXT\]\s*(.*?)\s*(?=\[DESCRIPTION\]|$)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        desc_match = re.search(
            r"\[DESCRIPTION\]\s*(.*?)$",
            content,
            re.DOTALL | re.IGNORECASE,
        )

        if text_match:
            extracted_text = text_match.group(1).strip()
        if desc_match:
            description = desc_match.group(1).strip()

        # If parsing failed, use the entire content as extracted text
        if not extracted_text and not description:
            self.logger.warning("Could not parse structured response, using full content")
            extracted_text = content
            description = "Image content (unstructured extraction)"

        return extracted_text, description

    async def extract_text_from_url(self, image_url: str) -> OCRResult:
        """
        Extract text from an image URL using GPT-4o Vision.

        Args:
            image_url: URL of the image to process

        Returns:
            OCRResult with extracted text and description
        """
        try:
            self.logger.info(f"Starting OCR extraction from URL: {image_url[:50]}...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this image thoroughly and provide:

1. **TEXT EXTRACTION**: Extract ALL text visible in the image, preserving structure.
2. **IMAGE DESCRIPTION**: Provide a concise description of the image content.

Format your response as:

[EXTRACTED_TEXT]
<all text from the image>

[DESCRIPTION]
<description of the image>""",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=4096,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            extracted_text, description = self._parse_ocr_response(content)

            return OCRResult(
                extracted_text=extracted_text,
                description=description,
                method="gpt4_vision",
                success=True,
            )

        except Exception as e:
            self.logger.error(f"OCR extraction from URL failed: {e}")
            capture_exception_with_context(
                e,
                extra={
                    "image_url": image_url[:100] if image_url else None,
                },
                tags={
                    "component": "ocr_service",
                    "operation": "extract_text_from_url",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            return OCRResult(
                extracted_text="",
                description="",
                method="gpt4_vision",
                success=False,
                error=str(e),
            )


# Singleton instance for convenience
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """Get the singleton OCR service instance."""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
