"""Text document processing handler for voice processing worker.

Handles .txt and .md files by:
1. Downloading from S3
2. Reading raw text content
3. Chunking with semantic boundaries
4. Generating summaries and keywords using OpenAI
5. Ingesting into RAG system
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from loguru import logger
from openai import AsyncOpenAI
from utils.progress import ProgressTracker

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.services.s3_service import get_s3_service
from shared.voice_processing.errors import ErrorCode, VoiceProcessingError
from shared.voice_processing.models import JobRequest, JobResult, ProcessingStage

from .rag_ingestion import ingest_chunked_content_to_rag, update_document_content


async def process_text_document(
    request: JobRequest, progress_tracker: ProgressTracker
) -> JobResult:
    """Process text document (.txt, .md) for RAG ingestion.

    Args:
        request: Job request with text file source
        progress_tracker: Progress tracking callback

    Returns:
        Job result with processing information
    """
    import time

    start_time = time.time()

    # Get OpenAI API key for summarization and keyword extraction
    openai_api_key = settings.openai_api_key

    if not openai_api_key:
        raise VoiceProcessingError(
            message="OPENAI_API_KEY not configured in settings",
            error_code=ErrorCode.CONFIGURATION_ERROR,
        )

    text_chunks = []
    input_info = {}
    temp_file = None

    try:
        logger.info(f"📄 Starting text document processing for: {request.input_source}")
        progress_tracker.start_stage(ProcessingStage.VALIDATION, "Validating text source")

        # Download text file from S3
        if request.input_source.startswith("s3://"):
            text_content, input_info, temp_file = await _download_text_from_s3(
                request.input_source, progress_tracker
            )
        else:
            raise VoiceProcessingError(
                message="Only S3 sources are supported for text documents",
                error_code=ErrorCode.INVALID_FORMAT,
            )

        progress_tracker.update_progress(10, "Text file downloaded successfully")

        # Detect file type from extension
        file_ext = Path(request.input_source).suffix.lower()
        is_markdown = file_ext == ".md"

        # Set source_type based on file extension
        source_type = "md" if is_markdown else "txt"

        logger.info(
            f"📝 Processing {file_ext} file: {len(text_content)} characters, "
            f"markdown={is_markdown}, source_type={source_type}"
        )

        # Chunk the text content with semantic boundaries
        progress_tracker.start_stage(
            ProcessingStage.CHUNK_ENRICHMENT, "Chunking text with semantic boundaries"
        )

        text_chunks = await _chunk_text_content(
            text_content=text_content,
            chunk_size=request.chunk_size or 1000,
            overlap=request.overlap or 200,
            is_markdown=is_markdown,
            openai_api_key=openai_api_key,
            progress_tracker=progress_tracker,
        )

        logger.info(f"✅ Generated {len(text_chunks)} chunks from text document")

        # Ingest text chunks into RAG
        if request.user_id and text_chunks:
            progress_tracker.start_stage(
                ProcessingStage.CHUNK_ENRICHMENT, "Ingesting chunks into RAG"
            )

            document_id = request.metadata.get("document_id") if request.metadata else None
            logger.info(f"📚 Ingesting {len(text_chunks)} chunks to RAG for user {request.user_id}")

            await _ingest_text_chunks_to_rag(
                chunks=text_chunks,
                user_id=request.user_id,
                document_id=document_id,
                persona_id=request.persona_id,
                source_type=source_type,  # Pass the specific source_type (txt or md)
            )

            # Update document with full content
            if document_id:
                await update_document_content(
                    document_id=str(document_id), content_text=text_content
                )

            logger.info("✅ RAG ingestion completed successfully")
        else:
            logger.warning("⚠️ Skipping RAG ingestion: missing user_id or no chunks")

        processing_time = time.time() - start_time

        # Calculate statistics
        total_words = sum(chunk.get("word_count", 0) for chunk in text_chunks)
        total_chars = sum(chunk.get("character_count", 0) for chunk in text_chunks)
        avg_chunk_size = total_words / len(text_chunks) if text_chunks else 0

        logger.info(
            f"📈 Processing complete: {len(text_chunks)} chunks, {total_words} words, "
            f"{processing_time:.2f}s"
        )

        progress_tracker.complete_stage("Text processing completed successfully")

        # ===== REFRESH USAGE CACHE AFTER SUCCESSFUL TEXT INGESTION =====
        # Recalculate usage from Documents table to ensure accurate limits
        if request.user_id:
            try:
                logger.info(
                    f"🔄 Refreshing usage cache for user {request.user_id} after text ingestion"
                )
                from shared.database.voice_job_model import async_session_maker
                from shared.services.usage_cache_service import UsageCacheService

                async with async_session_maker() as session:
                    usage_cache_service = UsageCacheService(session)
                    await usage_cache_service.recalculate_usage_from_source(
                        user_id=(
                            UUID(request.user_id)
                            if isinstance(request.user_id, str)
                            else request.user_id
                        )
                    )
                    await session.commit()
                    logger.info(f"✅ Usage cache refreshed for user {request.user_id} (text)")
            except Exception as cache_error:
                # Non-critical error - log warning but don't fail the job
                logger.warning(f"⚠️ Failed to refresh usage cache: {cache_error}")
        # ===== END USAGE CACHE REFRESH =====

        return JobResult(
            success=True,
            processing_time_seconds=processing_time,
            input_info=input_info,
            transcript_chunks=text_chunks,
            transcript_stats={
                "total_chunks": len(text_chunks),
                "total_words": total_words,
                "total_characters": total_chars,
                "average_chunk_size": avg_chunk_size,
                "file_type": file_ext,
                "is_markdown": is_markdown,
            },
        )

    except Exception as e:
        logger.error(f"❌ Failed to process text document: {e}")
        # Capture exception in Sentry with full context
        capture_exception_with_context(
            e,
            extra={
                "input_source": request.input_source,
                "document_id": request.metadata.get("document_id") if request.metadata else None,
                "persona_id": str(request.persona_id) if request.persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
                "chunk_size": request.chunk_size,
                "overlap": request.overlap,
            },
            tags={
                "component": "voice_worker",
                "operation": "text_processing",
                "parser_type": "text_handler",
                "severity": "high",
            },
        )
        raise
    finally:
        # Cleanup temporary file
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")


async def _download_text_from_s3(
    s3_path: str, progress_tracker: ProgressTracker
) -> tuple[str, Dict, str]:
    """Download text file from S3.

    Args:
        s3_path: S3 URI (s3://bucket/key)
        progress_tracker: Progress tracker

    Returns:
        Tuple of (text_content, input_info, temp_file_path)
    """
    from urllib.parse import urlparse

    logger.info(f"Downloading text from S3: {s3_path}")
    progress_tracker.update_progress(5, "Downloading text from S3")

    # Parse S3 path to get file extension
    parsed_url = urlparse(s3_path)
    file_extension = Path(parsed_url.path).suffix or ".txt"

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False, mode="w+b")
    temp_file_path = temp_file.name
    temp_file.close()

    # Download from S3
    s3_service = get_s3_service()
    await s3_service.download_file(s3_path=s3_path, local_path=temp_file_path)

    # Read text content
    with open(temp_file_path, "r", encoding="utf-8") as f:
        text_content = f.read()

    input_info = {
        "source": "s3",
        "s3_path": s3_path,
        "file_size": os.path.getsize(temp_file_path),
        "content_type": "text",
        "character_count": len(text_content),
    }

    logger.info(
        f"✅ Downloaded text from S3: {s3_path} ({input_info['file_size']} bytes, "
        f"{input_info['character_count']} characters)"
    )

    return text_content, input_info, temp_file_path


async def _chunk_text_content(
    text_content: str,
    chunk_size: int,
    overlap: int,
    is_markdown: bool,
    openai_api_key: str,
    progress_tracker: ProgressTracker,
) -> List[Dict]:
    """Chunk text content with semantic boundaries and generate summaries/keywords.

    Uses token-based chunking with semantic boundaries for better quality chunks.
    Default: 1000 tokens per chunk with 200 token overlap.

    Args:
        text_content: Raw text content
        chunk_size: Target chunk size in tokens (default: 1000)
        overlap: Token overlap between chunks (default: 200)
        is_markdown: Whether the content is markdown
        openai_api_key: OpenAI API key for enrichment
        progress_tracker: Progress tracker

    Returns:
        List of enriched chunks with summaries and keywords
    """
    import tiktoken

    logger.info(
        f"Chunking text content: {len(text_content)} chars, target={chunk_size} tokens, overlap={overlap} tokens"
    )

    # Initialize tokenizer for accurate token counting
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
    except Exception:
        # Fallback to a standard encoding
        encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        """Count tokens in text."""
        return len(encoding.encode(text))

    # Semantic chunking by paragraphs with token-based sizing
    # Split by double newline to maintain semantic boundaries
    paragraphs = text_content.split("\n\n")

    chunks = []
    current_chunk = ""
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = count_tokens(para)

        # If adding this paragraph would exceed chunk size, save current chunk
        if current_chunk and (current_tokens + para_tokens) > chunk_size:
            chunks.append(current_chunk)

            # Create overlap from the end of previous chunk
            if overlap > 0 and current_tokens > overlap:
                # Extract last N tokens for overlap by working backwards through words
                words = current_chunk.split()
                overlap_words = []
                overlap_token_count = 0

                # Build overlap from end backwards, collecting words
                for word in reversed(words):
                    # Check if adding this word would exceed overlap limit
                    word_tokens = count_tokens(word)
                    if overlap_token_count + word_tokens > overlap:
                        break
                    overlap_words.insert(0, word)  # Insert at beginning to maintain order
                    overlap_token_count += word_tokens

                # Reconstruct overlap text with proper word order
                overlap_text = " ".join(overlap_words) if overlap_words else ""

                current_chunk = overlap_text + "\n\n" + para if overlap_text else para
                current_tokens = count_tokens(current_chunk)
            else:
                current_chunk = para
                current_tokens = para_tokens
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk = current_chunk + "\n\n" + para
                current_tokens = count_tokens(current_chunk)
            else:
                current_chunk = para
                current_tokens = para_tokens

    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(current_chunk)

    logger.info(f"Created {len(chunks)} semantic chunks from text content (token-based)")

    # Generate document_about description (what the document is about)
    progress_tracker.update_progress(25, "Analyzing document content...")

    client = AsyncOpenAI(api_key=openai_api_key)

    # Generate document_about from full text (or large sample)
    document_about = await _generate_document_about(client, text_content, is_markdown)
    logger.info(f"Generated document_about: {document_about[:100]}...")

    # Enrich chunks with summaries and keywords using OpenAI
    progress_tracker.update_progress(30, f"Enriching {len(chunks)} chunks with AI")

    enriched_chunks = []

    for i, chunk_text in enumerate(chunks):
        try:
            # Generate summary and keywords
            summary, keywords = await _generate_summary_and_keywords(
                client, chunk_text, is_markdown
            )

            # Prepend document context to chunk text for better LLM understanding
            enriched_text = f"{chunk_text}\n\n[Document Context: {document_about}]\n\n[Summary: {summary} | Keywords: {', '.join(keywords)}]"
            chunk_tokens = count_tokens(enriched_text)

            enriched_chunk = {
                "chunk_id": f"text_chunk_{i}",
                "chunk_index": i,
                "text": enriched_text,  # Text with document context prepended
                "summary": summary,
                "keywords": keywords,
                "document_about": document_about,  # Also keep as metadata
                "word_count": len(enriched_text.split()),
                "character_count": len(enriched_text),
                "token_count": chunk_tokens,
                "is_markdown": is_markdown,
            }

            enriched_chunks.append(enriched_chunk)

            # Update progress
            if (i + 1) % 10 == 0 or (i + 1) == len(chunks):
                progress = 30 + int((i + 1) / len(chunks) * 40)
                progress_tracker.update_progress(progress, f"Enriched {i + 1}/{len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Failed to enrich chunk {i}: {e}")
            # Add chunk without enrichment but still with document context
            enriched_text = f"[Document Context: {document_about}]\n\n{chunk_text}"
            enriched_chunks.append(
                {
                    "chunk_id": f"text_chunk_{i}",
                    "chunk_index": i,
                    "text": enriched_text,  # Text with document context prepended
                    "summary": "",
                    "keywords": [],
                    "document_about": document_about,  # Also keep as metadata
                    "word_count": len(enriched_text.split()),
                    "character_count": len(enriched_text),
                    "token_count": count_tokens(enriched_text),
                    "is_markdown": is_markdown,
                }
            )

    progress_tracker.update_progress(70, f"Enriched all {len(enriched_chunks)} chunks")

    # Log statistics
    total_tokens = sum(chunk.get("token_count", 0) for chunk in enriched_chunks)
    avg_tokens = total_tokens / len(enriched_chunks) if enriched_chunks else 0
    logger.info(
        f"Chunk statistics: {len(enriched_chunks)} chunks, {total_tokens} total tokens, {avg_tokens:.1f} avg tokens/chunk"
    )

    return enriched_chunks


async def _generate_document_about(client: AsyncOpenAI, full_text: str, is_markdown: bool) -> str:
    """Generate a 2-3 line description about what the document contains.

    Args:
        client: OpenAI client
        full_text: Full document text (or beginning portion)
        is_markdown: Whether the content is markdown

    Returns:
        2-3 line description of what the document is about
    """
    content_type = "markdown" if is_markdown else "plain text"

    try:
        # Use beginning of document to understand overall content
        sample_text = full_text[:4000]  # Use first 4000 chars for context

        prompt = f"""Read this {content_type} document and describe what it is about in 2-3 concise lines.
Focus on WHAT the document contains, not summarizing specific details.

For example:
- "This document contains technical specifications for API endpoints..."
- "This document contains meeting notes discussing project timeline..."
- "This document contains research findings on machine learning..."

Document:
{sample_text}

Provide ONLY a 2-3 line description starting with "This document contains..." or similar phrasing."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You describe what documents contain in clear, concise terms. Focus on content type and topics, not detailed summaries.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=100,
        )

        document_about = response.choices[0].message.content.strip()

        # Ensure it's concise (2-3 lines max)
        lines = document_about.split("\n")
        if len(lines) > 3:
            document_about = "\n".join(lines[:3])

        logger.debug(f"Generated document_about description: {document_about[:100]}...")
        return document_about

    except Exception as e:
        logger.warning(f"Failed to generate document_about with OpenAI: {e}")
        # Fallback: simple heuristic-based description
        return _generate_simple_document_about(full_text, is_markdown)


def _generate_simple_document_about(text: str, is_markdown: bool) -> str:
    """Generate simple document description without AI.

    Args:
        text: Document text
        is_markdown: Whether content is markdown

    Returns:
        Simple description of document content
    """
    content_type = "markdown content" if is_markdown else "text content"

    # Count some basic stats
    word_count = len(text.split())
    line_count = len(text.split("\n"))

    # Try to extract first meaningful sentence
    import re

    sentences = re.split(r"[.!?]+", text[:500])
    first_sentence = next((s.strip() for s in sentences if len(s.strip()) > 20), "")

    if first_sentence:
        return f"This document contains {content_type} discussing: {first_sentence}. Document has approximately {word_count} words across {line_count} lines."
    else:
        return f"This document contains {content_type} with approximately {word_count} words across {line_count} lines."


async def _generate_summary_and_keywords(
    client: AsyncOpenAI, text: str, is_markdown: bool
) -> tuple[str, List[str]]:
    """Generate summary and keywords for a text chunk using OpenAI.

    Args:
        client: OpenAI client
        text: Text chunk
        is_markdown: Whether the content is markdown

    Returns:
        Tuple of (summary, keywords)
    """
    content_type = "markdown" if is_markdown else "plain text"

    try:
        # Use OpenAI to generate concise summary and keywords (matching YouTube handler)
        prompt = f"""Analyze this {content_type} content and provide:
1. A concise 1-2 sentence summary
2. 3-5 key topics/keywords (single words or short phrases, NO explanations)

Content:
{text[:2000]}

Format your response as:
Summary: [your summary]
Keywords: [keyword1, keyword2, keyword3, ...]

Keep keywords short and focused. Fewer keywords are better for vector search."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts concise summaries and key topics from text content. Keep keywords minimal (3-5 max) and highly relevant.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,  # Lower temperature for more consistent extraction
            max_tokens=200,  # Keep response concise
        )

        content = response.choices[0].message.content.strip()

        # Parse the response
        summary = ""
        keywords = []

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("Summary:"):
                summary = line.replace("Summary:", "").strip()
            elif line.startswith("Keywords:"):
                keywords_text = line.replace("Keywords:", "").strip()
                # Parse comma-separated keywords
                keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
                # Limit to 5 keywords max to avoid overwhelming the vector search
                keywords = keywords[:5]

        # Fallback if parsing failed
        if not summary:
            summary = text[:150] + "..." if len(text) > 150 else text
        if not keywords:
            keywords = _extract_simple_keywords(text)[:5]

        logger.debug(
            f"OpenAI generated summary ({len(summary)} chars) and {len(keywords)} keywords"
        )
        return summary, keywords

    except Exception as e:
        logger.warning(f"Failed to generate summary/keywords with OpenAI: {e}")
        # Capture in Sentry for monitoring
        capture_exception_with_context(
            e,
            extra={
                "text_length": len(text),
                "text_preview": text[:200],
                "operation": "text_summarization",
            },
            tags={
                "component": "voice_worker",
                "operation": "text_summarization",
                "parser_type": "openai_gpt",
                "severity": "medium",
            },
        )
        # Return fallback extraction
        return _generate_simple_summary_and_keywords(text)


def _generate_simple_summary_and_keywords(text: str) -> tuple[str, List[str]]:
    """Fallback method for simple summary and keyword extraction without AI.

    Args:
        text: The text content

    Returns:
        Tuple of (summary, keywords_list)
    """
    import re

    # Simple summary generation (first 2 sentences or up to 150 chars)
    sentences = re.split(r"[.!?]+", text)
    meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if len(meaningful_sentences) >= 2:
        summary = ". ".join(meaningful_sentences[:2]) + "."
    elif meaningful_sentences:
        summary = meaningful_sentences[0] + "."
    else:
        summary = text[:150] + "..." if len(text) > 150 else text

    keywords = _extract_simple_keywords(text)[:5]  # Limit to 5 keywords

    return summary, keywords


def _extract_simple_keywords(text: str) -> List[str]:
    """Extract keywords using simple word frequency analysis.

    Args:
        text: The text content

    Returns:
        List of keywords
    """
    import re
    from collections import Counter

    # Simple keyword extraction based on word frequency
    # Remove common stop words
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "up",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "can",
        "will",
        "just",
        "should",
        "now",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "this",
        "that",
        "these",
        "those",
        "am",
        "as",
        "if",
        "it",
        "its",
        "they",
        "them",
        "their",
        "what",
    }

    # Tokenize and clean
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())

    # Filter out stop words and get frequency
    filtered_words = [w for w in words if w not in stop_words]
    word_freq = Counter(filtered_words)

    # Get top 5 most common words as keywords
    keywords = [word for word, _ in word_freq.most_common(5)]

    return keywords


async def _ingest_text_chunks_to_rag(
    chunks: List[Dict],
    user_id: UUID,
    document_id: Optional[str],
    persona_id: Optional[UUID],
    source_type: str = "txt",  # Add source_type parameter with default
):
    """Ingest text chunks into RAG system.

    Args:
        chunks: Enriched text chunks
        user_id: User UUID
        document_id: Document UUID string
        persona_id: Persona UUID
        source_type: Source type ('txt' or 'md')
    """
    from shared.database.models.database import Persona
    from shared.database.voice_job_model import async_session_maker

    # Ensure persona exists
    async with async_session_maker() as session:
        from sqlalchemy import select

        if persona_id:
            stmt = select(Persona).where(Persona.id == persona_id)
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()

            if not persona:
                logger.warning(f"Persona {persona_id} not found, using default")
                persona_id = None

        # Get or create default persona if needed
        if not persona_id:
            stmt = select(Persona).where(
                Persona.user_id == user_id,
                Persona.persona_name == "default",
                Persona.is_active == True,
            )
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()

            if not persona:
                # Create default persona
                persona = Persona(
                    user_id=user_id,
                    persona_name="default",
                    name="Default Persona",
                    description="Default persona for text documents",
                )
                session.add(persona)
                await session.commit()
                await session.refresh(persona)

            persona_id = persona.id

    # Convert document_id to UUID
    doc_uuid = UUID(document_id) if document_id else None

    # Ingest to RAG with specific source_type (txt or md)
    await ingest_chunked_content_to_rag(
        chunks=chunks,
        user_id=user_id,
        persona_id=persona_id,
        source_type=source_type,  # Use the specific source_type instead of generic "text"
        source_record_id=doc_uuid,
        document_id=document_id,
        additional_metadata={
            "content_type": "markdown" if source_type == "md" else "text",
            "file_type": source_type,
        },
    )

    logger.info(f"✅ Ingested {len(chunks)} {source_type} chunks to RAG")
