"""
Centralized Sentry utilities for exception tracking and context management.

Usage:
    from shared.monitoring.sentry_utils import capture_exception_with_context

    try:
        risky_operation()
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={"user_id": str(user_id), "job_id": str(job_id)},
            tags={"component": "scraping", "provider": "crustdata"}
        )
        raise
"""

import logging
import os
from typing import Any, Dict, Optional, Union
from uuid import UUID

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from shared.config import settings

logger = logging.getLogger(__name__)


def init_sentry(
    component: str = "api",
    worker_id: Optional[str] = None,
    custom_tags: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Initialize Sentry SDK with environment-specific configuration.

    Args:
        component: Component type ("api", "worker_scraping", "worker_voice", "agent")
        worker_id: Optional worker identifier for distributed systems
        custom_tags: Additional tags to apply to all events

    Returns:
        bool: True if Sentry initialized, False if disabled/missing DSN
    """
    sentry_dsn = settings.sentry_dsn
    environment = settings.environment
    release = settings.git_sha

    if not sentry_dsn or not sentry_dsn.startswith("http"):
        logger.warning(f"⚠️  Sentry disabled for {component} (no valid DSN)")
        return False

    # Base tags for all events
    tags = {
        "component": component,
        "environment": environment,
    }

    if worker_id:
        tags["worker_id"] = worker_id

    if custom_tags:
        tags.update(custom_tags)

    # Component-specific integrations
    # Type annotation allows mixing different integration types
    integrations: list = [
        LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR,
        )
    ]

    # Add FastAPI integration only for API server
    if component == "api":
        # Automatically capture HTTP errors without manual capture_exception_with_context calls
        # 422: Validation/processing errors (could be our fault - integration issues, bad validation)
        # 500-599: Server errors (always our fault)
        integrations.append(
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes={422, *range(500, 600)},  # Auto-capture 422 + 5xx
            )
        )

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment,
        release=release,
        traces_sample_rate=_get_sample_rate(environment),
        profiles_sample_rate=_get_sample_rate(environment),
        integrations=integrations,
        before_send=_filter_and_enrich_event,
    )

    # Set component-wide tags
    for key, value in tags.items():
        sentry_sdk.set_tag(key, value)

    logger.info(f"✅ Sentry initialized: {component} (env={environment}, release={release})")
    return True


def _get_sample_rate(environment: str) -> float:
    """Get sample rate based on environment."""
    if environment == "production":
        return 0.1  # 10% sampling
    elif environment == "staging":
        return 0.5  # 50% sampling
    else:
        return 1.0  # 100% sampling for dev


def _filter_and_enrich_event(event, hint):
    """
    Filter and enrich Sentry events before sending.

    Categorizes exceptions by type rather than string matching for more reliable tagging.
    """

    # Add system context for debugging
    event.setdefault("extra", {})
    event["extra"]["system_info"] = {
        "environment": settings.environment,
        "container_id": os.getenv("HOSTNAME", "unknown")[:12],
    }

    # Categorize by exception type and HTTP status (single exc_info extraction)
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]
        event.setdefault("tags", {})

        # Check if it's an HTTPException (FastAPI) - add HTTP status tags
        if hasattr(exc_value, "status_code"):
            status_code = exc_value.status_code
            event["tags"]["http_status"] = str(status_code)

            # Categorize by status code range
            if status_code >= 500:
                event["tags"]["error_type"] = "server_error"
                event["tags"]["severity"] = "high"
            elif status_code == 422:
                event["tags"]["error_type"] = "validation_error"
                event["tags"]["severity"] = "medium"
            elif status_code >= 400:
                event["tags"]["error_type"] = "client_error"
                event["tags"]["severity"] = "low"

        # Import custom exception types
        has_custom_exceptions = False
        try:
            from shared.voice_processing.errors import ErrorCategory, VoiceProcessingError

            has_custom_exceptions = True
        except ImportError as e:
            # Log but continue - built-in exceptions will still be categorized
            logger.warning(
                f"Could not import custom exceptions for Sentry categorization: {e}. "
                "Voice errors won't have detailed tags, but built-in exceptions will still be categorized."
            )

        # Voice processing errors (only if imports succeeded)
        if has_custom_exceptions and isinstance(exc_value, VoiceProcessingError):
            event["tags"]["error_category"] = exc_value.category.value
            event["tags"]["error_code"] = exc_value.error_code.value
            event["tags"]["severity"] = exc_value.severity.value

            # Mark user-facing errors
            if exc_value.category in (ErrorCategory.VALIDATION, ErrorCategory.NETWORK):
                event["tags"]["user_facing"] = "true"

            # Add error context to Sentry extra
            if exc_value.context:
                event["extra"]["error_context"] = exc_value._serialize_context()

        # Built-in Python exceptions (ALWAYS categorize, even if custom imports failed)
        elif isinstance(exc_value, TimeoutError):
            event["tags"]["error_category"] = "timeout"
            event["tags"]["severity"] = "medium"
            event["tags"]["retryable"] = "true"

        elif isinstance(exc_value, ConnectionError):
            event["tags"]["error_category"] = "connection"
            event["tags"]["severity"] = "medium"
            event["tags"]["retryable"] = "true"

        elif isinstance(exc_value, BrokenPipeError):
            event["tags"]["error_category"] = "ipc_failure"
            event["tags"]["severity"] = "high"

        elif isinstance(exc_value, (ValueError, TypeError)):
            event["tags"]["error_category"] = "validation"
            event["tags"]["severity"] = "low"

        elif isinstance(exc_value, PermissionError):
            event["tags"]["error_category"] = "permissions"
            event["tags"]["severity"] = "high"

        elif isinstance(exc_value, FileNotFoundError):
            event["tags"]["error_category"] = "file_not_found"
            event["tags"]["severity"] = "medium"

    return event


def capture_exception_with_context(
    exception: Exception,
    extra: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    level: str = "error",
) -> Optional[str]:
    """
    Capture exception with structured context.

    Args:
        exception: The exception to capture
        extra: Additional context data (user_id, job_id, etc.)
        tags: Tags for grouping/filtering (component, operation, provider)
        user_context: User information (id, email, username)
        level: Severity level (error, warning, info)

    Returns:
        Event ID if captured, None otherwise

    Example:
        capture_exception_with_context(
            e,
            extra={"user_id": str(user_id), "job_id": str(job_id)},
            tags={"component": "scraping", "provider": "crustdata"},
            user_context={"id": str(user_id), "email": user.email}
        )
    """
    with sentry_sdk.push_scope() as scope:
        # Add extra context
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        # Add tags
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)

        # Set user context
        if user_context:
            scope.set_user(user_context)

        # Set level
        scope.level = level

        # Capture exception
        event_id = sentry_sdk.capture_exception(exception)

        logger.debug(f"Sentry event captured: {event_id}")
        return event_id


def set_user_context(
    user_id: Optional[Union[str, UUID]] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
    **kwargs,
):
    """Set user context for current scope."""
    user_data = {}

    if user_id:
        user_data["id"] = str(user_id)
    if email:
        user_data["email"] = email
    if username:
        user_data["username"] = username

    user_data.update(kwargs)

    if user_data:
        sentry_sdk.set_user(user_data)


def set_persona_context(persona_id: Union[str, UUID], persona_name: Optional[str] = None):
    """Set persona context as tags."""
    sentry_sdk.set_tag("persona_id", str(persona_id))
    if persona_name:
        sentry_sdk.set_tag("persona_name", persona_name)


def set_job_context(
    job_id: Union[str, UUID],
    job_type: str,
    source: Optional[str] = None,
    provider: Optional[str] = None,
):
    """Set job context for background processing."""
    sentry_sdk.set_tag("job_id", str(job_id))
    sentry_sdk.set_tag("job_type", job_type)

    if source:
        sentry_sdk.set_tag("source", source)
    if provider:
        sentry_sdk.set_tag("provider", provider)


def add_breadcrumb(
    message: str, category: str, level: str = "info", data: Optional[Dict[str, Any]] = None
):
    """Add breadcrumb for debugging context."""
    sentry_sdk.add_breadcrumb(message=message, category=category, level=level, data=data or {})


def start_transaction(name: str, op: str, **kwargs):
    """
    Start a performance transaction (top-level operation).

    WARNING: Only use this for top-level operations like workers and background jobs.
    For API request handlers, use start_span() instead to avoid double transactions
    (FastAPI integration already creates transactions).

    Returns a context manager for transaction tracking.

    Example (workers only):
        with start_transaction("process_scraping_job", "worker.scraping"):
            result = await process_job()
    """
    return sentry_sdk.start_transaction(name=name, op=op, **kwargs)


def start_span(op: str, description: Optional[str] = None, **kwargs):
    """
    Start a performance span (child of current transaction).

    Use this in API request handlers where FastAPI integration already
    creates a transaction. Avoids double transactions and broken traces.

    Returns a context manager for span tracking.

    Example (API handlers):
        with start_span("api.scraping.linkedin", "scrape_linkedin"):
            result = await scrape_profile()
    """
    return sentry_sdk.start_span(op=op, description=description, **kwargs)


def capture_message(
    message: str,
    level: str = "info",
    tags: dict = None,
    extra: dict = None,
    **kwargs,
):
    """
    Capture informational message with optional tags and extra data.

    Args:
        message: The message to capture
        level: Severity level (debug, info, warning, error, fatal)
        tags: Dictionary of tags for filtering/searching
        extra: Dictionary of extra context data
    """
    with sentry_sdk.push_scope() as scope:
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)
        sentry_sdk.capture_message(message, level=level, scope=scope)
