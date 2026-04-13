"""PDF Parser using Marker.io API for converting PDFs to enriched chunks."""

import asyncio
import json
import os
import re
import time
from typing import Dict, List, Optional

import aiohttp
from loguru import logger
from openai import AsyncOpenAI
from utils.progress import ProgressTracker

from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.voice_processing.errors import ErrorCode, VoiceProcessingError
from shared.voice_processing.models import ProcessingStage


class MarkdownPDFParser:
    """
    Parse a PDF into markdown format using Marker.io API and create enriched chunks
    with image descriptions.
    """

    def __init__(
        self,
        marker_api_key: str,
        openai_api_key: str,
        progress_tracker: Optional[ProgressTracker] = None,
    ):
        self.marker_api_key = marker_api_key
        self.openai_api_key = openai_api_key
        self.endpoint = "https://www.datalab.to/api/v1/marker"
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.progress_tracker = progress_tracker

    def _get_parsed_data_path(self, pdf_path: str, output_dir: str = "./output") -> str:
        """Get the path for cached parsed markdown data"""
        filename = os.path.splitext(os.path.basename(pdf_path))[0]
        return os.path.join(output_dir, f"{filename}_markdown.json")

    async def _save_parsed_data(
        self, parsed_data: Dict, pdf_path: str, output_dir: str = "./output"
    ) -> None:
        """Save parsed PDF markdown data to cache file"""
        os.makedirs(output_dir, exist_ok=True)
        cache_path = self._get_parsed_data_path(pdf_path, output_dir)

        # Add metadata
        cache_data = {
            "timestamp": time.time(),
            "pdf_path": pdf_path,
            "pdf_size": os.path.getsize(pdf_path),
            "pdf_mtime": os.path.getmtime(pdf_path),
            "parsed_data": parsed_data,
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"Saved markdown data to: {cache_path}")

    async def _load_parsed_data(
        self, pdf_path: str, output_dir: str = "./output"
    ) -> Optional[Dict]:
        """Load cached parsed markdown data if available and valid"""
        cache_path = self._get_parsed_data_path(pdf_path, output_dir)

        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Validate cache is still valid
            current_pdf_size = os.path.getsize(pdf_path)
            current_pdf_mtime = os.path.getmtime(pdf_path)

            if (
                cache_data.get("pdf_size") == current_pdf_size
                and cache_data.get("pdf_mtime") == current_pdf_mtime
            ):
                logger.info(f"Using cached markdown data from: {cache_path}")
                return cache_data["parsed_data"]
            else:
                logger.warning("Cached data is outdated, will re-parse PDF")
                return None

        except Exception as e:
            logger.warning(f"Error loading cached data: {e}, will re-parse PDF")
            return None

    async def _download_pdf(self, pdf_url: str, output_path: str) -> str:
        """Download PDF from URL to local file"""
        if self.progress_tracker:
            self.progress_tracker.start_stage(ProcessingStage.DOWNLOAD, "Downloading PDF file")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url) as response:
                    response.raise_for_status()

                    # Get total size for progress tracking
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    with open(output_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0 and self.progress_tracker:
                                progress = (downloaded / total_size) * 20  # 20% of total progress
                                self.progress_tracker.update_progress(
                                    progress, f"Downloaded {downloaded}/{total_size} bytes"
                                )

            if self.progress_tracker:
                self.progress_tracker.complete_stage("PDF download completed")

            return output_path

        except Exception as e:
            raise VoiceProcessingError(
                message=f"Failed to download PDF: {str(e)}",
                error_code=ErrorCode.DOWNLOAD_FAILED,
                is_retryable=True,
            )

    async def parse_pdf_to_markdown(
        self,
        pdf_path: str,
        output_dir: str = "./output",
        force: bool = False,
        content_type: str = "application/pdf",
    ) -> Dict:
        """
        Upload PDF or Office document file to Marker API and get markdown response.
        Uses cached data if available unless force=True.
        Returns parsed document structure with markdown content.

        Args:
            pdf_path: Path to document file (PDF, DOCX, PPTX, XLSX)
            output_dir: Directory for output files
            force: Force re-parsing even if cached
            content_type: MIME type of the document (e.g., application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document)
        """
        # Check for cached data unless force is True
        if not force:
            cached_data = await self._load_parsed_data(pdf_path, output_dir)
            if cached_data:
                # Don't start/complete a stage here - let the caller manage the progress tracker
                # Just log that we're using cached data
                logger.info("Using cached PDF data")
                return cached_data

        if self.progress_tracker:
            self.progress_tracker.start_stage(
                ProcessingStage.PDF_PARSING, "Processing PDF with Marker API"
            )

        logger.info("Processing PDF with Marker API for markdown output...")

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-API-Key": self.marker_api_key}

                with open(pdf_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field(
                        "file",
                        f,
                        filename=os.path.basename(pdf_path),
                        content_type=content_type,  # Use dynamic content_type for all document formats
                    )
                    data.add_field("output_format", "markdown")
                    data.add_field("paginate", "false")
                    data.add_field("extract_images", "true")

                    async with session.post(self.endpoint, data=data, headers=headers) as response:
                        response.raise_for_status()
                        submit_result = await response.json()

                if not submit_result.get("success"):
                    raise VoiceProcessingError(
                        message=f"Marker API submission failed: {submit_result.get('error', 'Unknown error')}",
                        error_code=ErrorCode.PROCESSING_ERROR,
                        is_retryable=True,
                    )

                request_check_url = submit_result["request_check_url"]

                # Poll for results
                timeout = 300
                poll_interval = 2
                elapsed = 0

                while elapsed < timeout:
                    async with session.get(request_check_url, headers=headers) as result_response:
                        result_response.raise_for_status()
                        result = await result_response.json()

                    status = result.get("status")
                    if status == "complete":
                        # Save the parsed data for future use
                        await self._save_parsed_data(result, pdf_path, output_dir)

                        if self.progress_tracker:
                            self.progress_tracker.update_progress(40, "PDF parsing completed")
                            self.progress_tracker.complete_stage("PDF parsed successfully")

                        return result
                    elif status == "error":
                        raise VoiceProcessingError(
                            message=f"Marker API conversion failed: {result.get('error', 'Unknown error')}",
                            error_code=ErrorCode.PROCESSING_ERROR,
                            is_retryable=False,
                        )

                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                    if self.progress_tracker:
                        progress = 20 + (elapsed / timeout) * 20  # 20-40% of total progress
                        self.progress_tracker.update_progress(
                            progress, f"Processing PDF... ({elapsed}s)"
                        )

                raise VoiceProcessingError(
                    message=f"Marker API timed out after {timeout} seconds",
                    error_code=ErrorCode.TIMEOUT,
                    is_retryable=True,
                )

        except aiohttp.ClientError as e:
            # Capture network error in Sentry
            capture_exception_with_context(
                e,
                extra={
                    "pdf_path": pdf_path,
                    "output_dir": output_dir,
                    "content_type": content_type,
                    "operation": "marker_api_parse",
                },
                tags={
                    "component": "voice_worker",
                    "operation": "pdf_parsing",
                    "parser_type": "marker_api",
                    "severity": "high",
                    "error_type": "network_error",
                },
            )
            raise VoiceProcessingError(
                message=f"Network error during PDF parsing: {str(e)}",
                error_code=ErrorCode.NETWORK_ERROR,
                is_retryable=True,
            )

    def _extract_images_info(self, parsed_pdf: Dict) -> List[Dict]:
        """Extract image information from the parsed PDF response"""
        images = []

        # Check if there's image data in the response
        if "images" in parsed_pdf:
            images_data = parsed_pdf["images"]
            if isinstance(images_data, dict):
                for img_key, img_data in images_data.items():
                    image_info = {
                        "id": img_key,
                        "data": img_data,
                        "description": f"Image {img_key}",
                    }
                    images.append(image_info)

        # Also check JSON structure for more detailed image info
        if "json" in parsed_pdf and parsed_pdf["json"]:
            json_data = parsed_pdf["json"]

            def extract_images_from_json(json_obj, images_list):
                """Recursively extract image info from JSON structure"""
                if isinstance(json_obj, dict):
                    block_type = json_obj.get("block_type", "")

                    if block_type in ["Picture", "Figure", "PictureGroup"]:
                        image_info = {
                            "id": json_obj.get("id", f"img_{len(images_list)}"),
                            "block_type": block_type,
                            "page": json_obj.get("page", 1),
                            "bbox": json_obj.get("bbox", []),
                            "html": json_obj.get("html", ""),
                            "images": json_obj.get("images", []),
                        }

                        # Extract description from HTML if available
                        html_content = json_obj.get("html", "")
                        description = self._extract_image_description(
                            html_content, block_type, image_info["id"]
                        )
                        image_info["description"] = description

                        images_list.append(image_info)

                    # Process children recursively
                    children = json_obj.get("children")
                    if children and isinstance(children, list):
                        for child in children:
                            if child:
                                extract_images_from_json(child, images_list)

                elif isinstance(json_obj, list):
                    for item in json_obj:
                        if item:
                            extract_images_from_json(item, images_list)

            extract_images_from_json(json_data, images)

        return images

    def _extract_image_description(self, html_content: str, block_type: str, image_id: str) -> str:
        """Extract or generate meaningful description for an image"""
        description = ""

        if html_content:
            # Look for alt text
            alt_match = re.search(r'alt="([^"]*)"', html_content)
            if alt_match:
                description = alt_match.group(1).strip()

            # Look for figcaption
            if not description:
                caption_match = re.search(
                    r"<figcaption[^>]*>(.*?)</figcaption>", html_content, re.DOTALL
                )
                if caption_match:
                    description = re.sub(r"<[^>]+>", "", caption_match.group(1)).strip()

            # Look for any meaningful text content
            if not description:
                text_content = re.sub(r"<img[^>]*>", "", html_content)
                text_content = re.sub(r"<[^>]+>", " ", text_content).strip()
                text_content = re.sub(r"\s+", " ", text_content)
                if text_content and len(text_content) > 3:
                    description = text_content[:100] + ("..." if len(text_content) > 100 else "")

        # Generate fallback description based on type and position
        if not description:
            if block_type == "Picture":
                if "logo" in image_id.lower() or "0" in image_id.split("/")[-1]:
                    description = "Company logo or branding image"
                else:
                    description = "Business or financial related image"
            elif block_type == "Figure":
                description = "Chart, graph, or financial figure"
            elif block_type == "PictureGroup":
                description = "Group of related images or diagram"
            else:
                description = "Visual content"

        return description

    async def _generate_image_descriptions_with_ai(
        self, images: List[Dict], markdown_content: str
    ) -> List[Dict]:
        """Use OpenAI to generate better descriptions for images based on context"""
        enhanced_images = []

        # Only start a new stage if no stage is currently active
        need_to_complete_stage = False
        if self.progress_tracker:
            if self.progress_tracker.current_stage is None:
                self.progress_tracker.start_stage(
                    ProcessingStage.CHUNK_ENRICHMENT, "Enhancing image descriptions with AI"
                )
                need_to_complete_stage = True

        for i, image in enumerate(images):
            try:
                # Get context around the image from markdown
                image_id = image.get("id", "")
                current_description = image.get("description", "")

                # Find nearby context in markdown (look for image references)
                context_window = ""
                if image_id in markdown_content:
                    # Find the position of the image reference
                    img_pos = markdown_content.find(image_id)
                    if img_pos != -1:
                        # Get text before and after the image
                        start = max(0, img_pos - 500)
                        end = min(len(markdown_content), img_pos + 500)
                        context_window = markdown_content[start:end]

                # Use AI to enhance description
                prompt = f"""
                Based on the context of a financial/business document, provide a brief, descriptive caption for this image.

                Current description: {current_description}
                Document context near image: {context_window[:300] if context_window else "No specific context available"}
                Image type: {image.get('block_type', 'Image')}

                Provide a single, concise description (max 50 words) that would be useful for document understanding:
                """

                response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are helping to describe images in business/financial documents. Be concise and factual.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=100,
                    temperature=0.3,
                )

                ai_description = response.choices[0].message.content.strip()

                # Update the image with enhanced description
                enhanced_image = image.copy()
                enhanced_image["ai_description"] = ai_description
                enhanced_image["final_description"] = (
                    ai_description if ai_description else current_description
                )
                enhanced_images.append(enhanced_image)

                if self.progress_tracker:
                    progress = 50 + (i / len(images)) * 10  # 50-60% of total progress
                    self.progress_tracker.update_progress(
                        progress, f"Enhanced {i+1}/{len(images)} image descriptions"
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to enhance description for image {image.get('id', 'unknown')}: {e}"
                )
                # Capture in Sentry but continue processing
                capture_exception_with_context(
                    e,
                    extra={
                        "image_id": image.get("id", "unknown"),
                        "image_block_type": image.get("block_type"),
                        "image_page": image.get("page"),
                        "current_description": current_description,
                    },
                    tags={
                        "component": "voice_worker",
                        "operation": "image_enhancement",
                        "parser_type": "openai_vision",
                        "severity": "medium",
                    },
                )
                # Keep original description
                enhanced_image = image.copy()
                enhanced_image["final_description"] = image.get("description", "Image content")
                enhanced_images.append(enhanced_image)

        # Only complete the stage if we started it
        if self.progress_tracker and need_to_complete_stage:
            self.progress_tracker.complete_stage(f"Enhanced {len(images)} image descriptions")

        return enhanced_images

    def _create_chunks(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split markdown text into semantic chunks using paragraph and sentence boundaries.
        """
        if self.progress_tracker:
            self.progress_tracker.start_stage(
                ProcessingStage.CHUNK_CREATION, "Creating semantic chunks from text"
            )

        # First split by markdown sections (headers)
        sections = []
        current_section = []

        lines = text.split("\n")
        for line in lines:
            if line.startswith("#") and current_section:
                # New section found, save current section
                sections.append("\n".join(current_section))
                current_section = [line]
            else:
                current_section.append(line)

        # Add the last section
        if current_section:
            sections.append("\n".join(current_section))

        # Now create chunks from sections
        chunks = []
        current_chunk = []
        current_word_count = 0

        for section in sections:
            section_words = section.split()
            section_word_count = len(section_words)

            # If single section exceeds chunk size, split it further
            if section_word_count > chunk_size:
                # Process current chunk if it has content
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_word_count = 0

                # Split large section by paragraphs
                paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]

                for paragraph in paragraphs:
                    paragraph_words = paragraph.split()
                    paragraph_word_count = len(paragraph_words)

                    if current_word_count + paragraph_word_count > chunk_size and current_chunk:
                        chunks.append(" ".join(current_chunk))

                        # Create overlap
                        overlap_words = 0
                        overlap_content = []
                        for i in range(len(current_chunk) - 1, -1, -1):
                            word_count = len(current_chunk[i].split())
                            if overlap_words + word_count <= overlap:
                                overlap_content.insert(0, current_chunk[i])
                                overlap_words += word_count
                            else:
                                break

                        current_chunk = overlap_content + [paragraph]
                        current_word_count = sum(len(p.split()) for p in current_chunk)
                    else:
                        current_chunk.append(paragraph)
                        current_word_count += paragraph_word_count

            # If adding this section would exceed chunk size
            elif current_word_count + section_word_count > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))

                # Create overlap
                overlap_words = min(overlap, current_word_count)
                if overlap_words > 0:
                    chunk_text = " ".join(current_chunk)
                    words = chunk_text.split()
                    overlap_text = " ".join(words[-overlap_words:])
                    current_chunk = [overlap_text, section]
                else:
                    current_chunk = [section]
                current_word_count = sum(len(s.split()) for s in current_chunk)
            else:
                # Add section to current chunk
                current_chunk.append(section)
                current_word_count += section_word_count

        # Add final chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        if self.progress_tracker:
            self.progress_tracker.complete_stage(f"Created {len(chunks)} chunks")

        return chunks

    async def _enrich_chunk(self, chunk_text: str) -> Dict:
        """
        Call OpenAI GPT-4o-mini to get summary and keywords for a given chunk.
        """
        prompt = f"""
        You are enriching markdown text for knowledge-base vectorization.
        Return a 1-sentence summary and 5 keywords in JSON format.

        Example output:
        {{
          "summary": "...",
          "keywords": ["...", "...", "..."]
        }}

        Text:
        {chunk_text[:4000]}
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates structured summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=150,
                temperature=0.3,
            )

            content = response.choices[0].message.content
            enriched = json.loads(content)
        except Exception as e:
            logger.warning(f"OpenAI enrichment failed: {e}")
            # Capture in Sentry for monitoring
            capture_exception_with_context(
                e,
                extra={
                    "chunk_length": len(chunk_text),
                    "chunk_preview": chunk_text[:200],
                    "operation": "chunk_enrichment",
                },
                tags={
                    "component": "voice_worker",
                    "operation": "chunk_enrichment",
                    "parser_type": "openai_gpt",
                    "severity": "medium",
                },
            )
            enriched = {"summary": "", "keywords": []}

        return enriched

    def _add_image_descriptions_to_markdown(self, markdown_content: str, images: List[Dict]) -> str:
        """
        Add image descriptions to the markdown content where image references are found.
        """
        enhanced_markdown = markdown_content

        for image in images:
            image_id = image.get("id", "")
            description = image.get("final_description", image.get("description", ""))

            if image_id and description:
                # Look for image references in markdown and add descriptions
                patterns = [
                    rf"!\[([^\]]*)\]\([^)]*{re.escape(image_id)}[^)]*\)",
                    rf"<img[^>]*{re.escape(image_id)}[^>]*>",
                    rf"{re.escape(image_id)}",
                ]

                for pattern in patterns:
                    if re.search(pattern, enhanced_markdown):
                        # Add description after the image reference
                        enhanced_markdown = re.sub(
                            pattern,
                            lambda m: f"{m.group(0)}\n\n*Image Description: {description}*\n",
                            enhanced_markdown,
                            count=1,
                        )
                        break

        return enhanced_markdown

    async def process_pdf_to_chunks(
        self,
        pdf_path: str,
        output_dir: str = "./output",
        chunk_size: int = 1000,
        overlap: int = 200,
        force: bool = False,
        enhance_images: bool = False,
        document_id: Optional[str] = None,
        s3_uri: Optional[str] = None,  # Add S3 URI parameter
        content_type: str = "application/pdf",  # Add content_type parameter
    ) -> List[Dict]:
        """
        Complete pipeline: Document (PDF/DOCX/PPTX/XLSX) -> Markdown -> Enhanced Chunks

        Args:
            pdf_path: Path to document file (PDF, DOCX, PPTX, XLSX)
            output_dir: Directory for output files
            chunk_size: Target chunk size in words
            overlap: Overlap between chunks in words
            force: Force re-parsing even if cached
            enhance_images: Use AI to enhance image descriptions
            document_id: Optional document ID to update in database
            s3_uri: Optional S3 URI where the document is stored
            content_type: MIME type of the document

        Returns:
            List of enriched chunk dictionaries with standardized metadata
        """
        # Start an overall processing stage if no stage is active
        if self.progress_tracker:
            if self.progress_tracker.current_stage is None:
                self.progress_tracker.start_stage(
                    ProcessingStage.PDF_PARSING, "Processing PDF to chunks"
                )

        # Step 1: Parse document to markdown (supports PDF, DOCX, PPTX, XLSX)
        parsed_pdf = await self.parse_pdf_to_markdown(pdf_path, output_dir, force, content_type)

        # Step 2: Extract markdown content
        markdown_content = parsed_pdf.get("markdown", "")
        if not markdown_content:
            raise VoiceProcessingError(
                message="No markdown content found in parsed PDF",
                error_code=ErrorCode.PROCESSING_ERROR,
                is_retryable=False,
            )

        logger.info(f"Extracted {len(markdown_content)} characters of markdown")

        # Step 3: Extract and enhance image descriptions
        images = self._extract_images_info(parsed_pdf)
        logger.info(f"Found {len(images)} images")

        if enhance_images and images:
            logger.info("Enhancing image descriptions with AI...")
            images = await self._generate_image_descriptions_with_ai(images, markdown_content)

        # Step 4: Add image descriptions to markdown
        if images:
            logger.info("Adding image descriptions to markdown...")
            enhanced_markdown = self._add_image_descriptions_to_markdown(markdown_content, images)
        else:
            enhanced_markdown = markdown_content

        # Step 5: Save enhanced markdown
        markdown_output_path = os.path.join(
            output_dir, f"{os.path.splitext(os.path.basename(pdf_path))[0]}_enhanced.md"
        )
        with open(markdown_output_path, "w", encoding="utf-8") as f:
            f.write(enhanced_markdown)
        logger.info(f"Saved enhanced markdown to: {markdown_output_path}")

        # Step 5.5: Update Document table with raw markdown content
        if document_id:
            try:
                from uuid import UUID

                from sqlalchemy import update

                from shared.database.models.document import Document
                from shared.database.voice_job_model import async_session_maker

                async with async_session_maker() as session:
                    # Extract page_count from parsed_pdf metadata if available
                    # page_count = parsed_pdf.get('metadata', {}).get('page_count') or parsed_pdf.get('page_count')

                    update_values = {"content_text": enhanced_markdown}

                    # Update metadata with page_count if available
                    # if page_count:
                    #     update_values["document_metadata"] = {
                    #         "page_count": page_count
                    #     }
                    #     logger.info(f"📄 PDF has {page_count} pages")

                    stmt = (
                        update(Document)
                        .where(Document.id == UUID(document_id))
                        .values(**update_values)
                    )
                    await session.execute(stmt)
                    await session.commit()

                logger.info(
                    f"✅ Updated Document {document_id} content_text with {len(enhanced_markdown)} characters of markdown"
                )
            except Exception as e:
                logger.error(f"⚠️ Failed to update Document content_text: {e}")
                # Capture in Sentry for monitoring
                capture_exception_with_context(
                    e,
                    extra={
                        "document_id": document_id,
                        "markdown_length": len(enhanced_markdown),
                        "pdf_path": pdf_path,
                        "operation": "document_update",
                    },
                    tags={
                        "component": "voice_worker",
                        "operation": "document_update",
                        "parser_type": "pdf_parser",
                        "severity": "medium",
                    },
                )
                # Don't fail the job if this update fails

        # Step 6: Create chunks
        logger.info("Creating chunks from enhanced markdown...")
        chunks = self._create_chunks(enhanced_markdown, chunk_size, overlap)
        logger.info(f"Created {len(chunks)} chunks")

        # Determine source type based on file extension
        from pathlib import Path

        file_ext = Path(pdf_path).suffix.lower()

        # Map file extensions to source types
        source_type_map = {
            ".pdf": "pdf",
            ".doc": "doc",
            ".docx": "docx",
            ".xls": "xls",
            ".xlsx": "xlsx",
            ".ppt": "ppt",
            ".pptx": "pptx",
        }

        # Get source type, default to "pdf" if unknown
        source_type = source_type_map.get(file_ext, "pdf")

        # Map to content type for metadata
        content_type_map = {
            ".pdf": "pdf_document",
            ".doc": "doc_document",
            ".docx": "docx_document",
            ".xls": "xls_document",
            ".xlsx": "xlsx_document",
            ".ppt": "ppt_document",
            ".pptx": "pptx_document",
        }

        chunk_content_type = content_type_map.get(file_ext, "pdf_document")

        logger.info(
            f"Processing {source_type.upper()} document - source type: {source_type}, content type: {chunk_content_type}"
        )

        # Step 7: Enrich chunks with AI and format with standardized metadata
        all_chunks = []
        from datetime import datetime

        for idx, chunk in enumerate(chunks):
            logger.info(f"Enriching chunk {idx+1}/{len(chunks)}...")
            enriched = await self._enrich_chunk(chunk)

            # Calculate token count (approximate: 1 token ≈ 4 characters)
            token_count = len(chunk) // 4

            # Enrich the content by prepending summary and keywords
            # This makes the context immediately available in the chunk text for better LLM understanding
            summary = enriched.get("summary", "")
            keywords = enriched.get("keywords", [])

            # Build enriched content with context prepended
            enriched_content = chunk  # Start with original chunk

            if summary or keywords:
                context_header = []
                if summary:
                    context_header.append(f"Summary: {summary}")
                if keywords:
                    context_header.append(f"Keywords: {', '.join(keywords)}")

                # Prepend context to chunk content
                enriched_content = chunk + "\n".join(context_header)

                # Update token count for enriched content
                token_count = len(enriched_content) // 4

            # Format chunk with standardized metadata matching audio/video format
            chunk_dict = {
                # Chunk identification (matches audio/video)
                "chunk_id": idx,
                "chunk_index": idx,
                # Chunk content (vectorized) - NOW ENRICHED with summary and keywords
                "content": enriched_content,  # Contains: Summary + Keywords + Original chunk
                "token_count": token_count,
                # Temporal information (all None for documents since no timestamps)
                "start_time": None,
                "end_time": None,
                "duration": None,
                "start_time_formatted": None,
                "end_time_formatted": None,
                # Speaker information (None for documents)
                "speakers": None,
                "speaker_count": None,
                # Source metadata (matches audio/video format) - DYNAMIC based on extension
                "source": source_type,  # Changed from hardcoded "pdf" to dynamic source_type
                "file_path": s3_uri if s3_uri else pdf_path,  # Use S3 URI if available
                "file_url": s3_uri if s3_uri else pdf_path,  # Both point to same S3 location
                "file_size": os.path.getsize(pdf_path),
                # Context for LLM (summary in context, full details in full_context)
                "context": enriched.get("summary", ""),
                "full_context": f"{enriched.get('summary', '')}|{', '.join(enriched.get('keywords', []))}",
                # Metadata
                "extracted_at": datetime.now().isoformat(),
                "segment_count": 1,  # Each document chunk is one segment
                "content_type": chunk_content_type,  # Dynamic based on file extension
                # Additional fields for compatibility
                "summary": enriched.get("summary", ""),
                "keywords": enriched.get("keywords", []),
            }
            all_chunks.append(chunk_dict)

        # Removed: Step 8 chunk dump saving (unnecessary - chunks already in vector DB)
        # The chunks are ingested into the RAG system, no need to save to JSON files

        # Step 8: Save image info (kept - useful for reference)
        if images:
            images_output_path = os.path.join(
                output_dir,
                f"{os.path.splitext(os.path.basename(pdf_path))[0]}_markdown_images.json",
            )
            with open(images_output_path, "w", encoding="utf-8") as f:
                json.dump(images, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(images)} image descriptions to: {images_output_path}")

        # Only complete the stage if we started it in this method
        # if self.progress_tracker and need_to_complete_stage:
        #     self.progress_tracker.complete_stage("PDF processing completed successfully")

        return all_chunks
