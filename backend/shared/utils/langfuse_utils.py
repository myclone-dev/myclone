"""
Langfuse utility functions for instrumentation and monitoring.
"""

import logging
from typing import Optional

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

# Import OpenInference for instrumentation (optional)
try:
    from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

    OPENINFERENCE_AVAILABLE = True
    # Initialize LlamaIndex instrumentation
    LlamaIndexInstrumentor().instrument()
    logger.info("✅ OpenInference available for LlamaIndex instrumentation")
except ImportError:
    OPENINFERENCE_AVAILABLE = False
    LlamaIndexInstrumentor = None
    logger.warning(
        "⚠️ OpenInference not available. Install openinference-instrumentation-llama-index for instrumentation."
    )

# Import Langfuse for prompt evaluation tracking
try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None  # type: ignore


def setup_langfuse_instrumentation(
    langfuse_public_key: str, langfuse_secret_key: str, langfuse_host: str
):
    """
    Initialize Langfuse instrumentation for LlamaIndex observability using OpenInference instrumentor.

    Args:
        langfuse_public_key: Langfuse public API key
        langfuse_secret_key: Langfuse secret API key
        langfuse_host: Langfuse host URL

    Returns:
        Langfuse client instance if successful, None otherwise
    """
    if not OPENINFERENCE_AVAILABLE:
        logger.warning("⚠️ OpenInference not available; skipping instrumentation setup")
        return None

    # Initialize Langfuse client
    try:
        from langfuse import Langfuse, get_client

        Langfuse(
            public_key=langfuse_public_key,
            secret_key=langfuse_secret_key,
            host=langfuse_host,
        )
        logger.info(
            f" ✅ Langfuse client initialized with public key {langfuse_public_key} and host {langfuse_host}"
        )
        langfuse_client = get_client()
        # Optionally verify auth
        if hasattr(langfuse_client, "auth_check"):
            ok = langfuse_client.auth_check()
            if not ok:
                logger.warning("⚠️ Langfuse client authentication failed")
            else:
                logger.info("✅ Langfuse client authenticated and ready")
        return langfuse_client
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "langfuse_host": langfuse_host,
                "has_public_key": bool(langfuse_public_key),
                "has_secret_key": bool(langfuse_secret_key),
            },
            tags={
                "component": "langfuse_utils",
                "operation": "setup_langfuse_instrumentation",
                "severity": "medium",
                "user_facing": "false",
            },
        )
        logger.error(f"❌ Failed to initialize Langfuse client: {e}")
        return None


# -------------------- Langfuse Helper Functions -------------------- #


def get_langfuse_client() -> Optional[Langfuse]:
    """
    Initialize and return a Langfuse client for prompt evaluation tracking.

    Returns:
        Langfuse client instance if available and configured, None otherwise
    """
    if not LANGFUSE_AVAILABLE:
        logger.warning(
            "⚠️ Langfuse not available. Install langfuse package for evaluation tracking."
        )
        return None

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning("⚠️ Langfuse credentials not configured. Skipping evaluation tracking.")
        return None

    try:
        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("✅ Langfuse client initialized for prompt evaluation")
        return client
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "langfuse_host": settings.langfuse_host,
                "has_public_key": bool(settings.langfuse_public_key),
                "has_secret_key": bool(settings.langfuse_secret_key),
            },
            tags={
                "component": "langfuse_utils",
                "operation": "get_langfuse_client",
                "severity": "medium",
                "user_facing": "false",
            },
        )
        logger.error(f"❌ Failed to initialize Langfuse client: {e}")
        return None
