"""
Webhook Service - Sends event notifications to configured webhook URLs

This service handles:
1. Validating webhook URLs (HTTPS required + SSRF protection)
2. Building standardized event payloads
3. Sending HTTP POST requests with timeout
4. Logging failures to Sentry (fire-and-forget, no retry)

SSRF Protection:
- Blocks private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Blocks loopback addresses (127.0.0.1, ::1)
- Blocks cloud metadata endpoints (169.254.169.254)
- Validates IPs at request time (prevents DNS rebinding attacks)
- Disables HTTP redirects (prevents redirect to internal URLs)
- Checks both IPv4 and IPv6 addresses
"""

import ipaddress
import json
import logging
import socket
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import Persona, async_session_maker
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

# Known dangerous hostnames that should be blocked
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",  # GCP metadata
    "metadata.azure.com",  # Azure metadata
    "instance-data",  # AWS metadata
    "metadata",  # Generic metadata endpoint
}


class WebhookService:
    """Service for sending webhook events to persona-configured URLs"""

    def __init__(self):
        """
        Initialize webhook service with HTTP client

        Uses httpx.AsyncClient for async HTTP requests with timeout.
        SSRF Protection: Disables redirects to prevent redirect to internal URLs.
        """
        self.http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=False)
        self.logger = logging.getLogger(__name__)

    async def send_event(self, persona_id: UUID, event_type: str, event_data: dict) -> bool:
        """
        Send webhook event to persona's configured webhook URL

        Args:
            persona_id: UUID of the persona
            event_type: Event type (e.g., "conversation.finished")
            event_data: Event-specific data payload

        Returns:
            True if sent successfully, False if failed or webhook not enabled
        """
        try:
            async with async_session_maker() as session:
                # Get persona with webhook settings
                persona = await self._get_persona(session, persona_id)

                if not persona:
                    self.logger.warning(f"Persona {persona_id} not found - skipping webhook")
                    return False

                # Check if webhook enabled
                if not persona.webhook_enabled:
                    self.logger.debug(f"Webhook not enabled for persona {persona_id}")
                    return False

                # Validate webhook URL
                if not persona.webhook_url:
                    self.logger.warning(
                        f"Webhook enabled but no URL configured for persona {persona_id}"
                    )
                    return False

                if not self._validate_webhook_url(persona.webhook_url):
                    self.logger.error(
                        f"Invalid webhook URL for persona {persona_id}: {persona.webhook_url}"
                    )
                    return False

                # Build event payload
                payload = self._build_payload(persona, event_type, event_data)

                # Send webhook
                success = await self._send_http_post(persona.webhook_url, payload)

                if success:
                    self.logger.info(
                        f"✅ Webhook sent successfully for persona {persona_id} "
                        f"(event: {event_type}, url: {persona.webhook_url})"
                    )
                else:
                    self.logger.warning(
                        f"❌ Webhook delivery failed for persona {persona_id} "
                        f"(event: {event_type})"
                    )

                return success

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(persona_id),
                    "event_type": event_type,
                },
                tags={
                    "component": "webhook",
                    "operation": "send_event",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Webhook send failed: {e}", exc_info=True)
            return False

    async def _get_persona(self, session: AsyncSession, persona_id: UUID) -> Optional[Persona]:
        """Get persona by ID"""
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _validate_webhook_url(self, url: str) -> bool:
        """
        Validate webhook URL with SSRF protection

        Requirements:
        - Must start with https://
        - Must have valid URL structure
        - Must not resolve to private/internal IPs (SSRF protection)
        - Must not use blocked hostnames

        IMPORTANT: This validates URL structure and hostname safety.
        IP validation happens again at request time to prevent DNS rebinding attacks.
        """
        if not url or not url.startswith("https://"):
            self.logger.error(f"Webhook URL must use HTTPS: {url}")
            return False

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname

            if not hostname or not all([parsed.scheme, parsed.netloc]):
                self.logger.error(f"Invalid webhook URL structure: {url}")
                return False

            # Block known dangerous hostnames
            if hostname.lower() in BLOCKED_HOSTNAMES:
                self.logger.error(f"Blocked dangerous hostname in webhook URL: {hostname}")
                return False

            # Validate that hostname doesn't resolve to private/internal IPs
            return self._check_ip_safety(hostname)

        except (ValueError, AttributeError) as e:
            self.logger.error(f"Invalid webhook URL format: {url}, error: {e}")
            return False

    def _check_ip_safety(self, hostname: str) -> bool:
        """
        Check if hostname resolves to safe (non-private) IPs

        This method resolves the hostname and validates ALL resolved IPs
        (both IPv4 and IPv6) are not private, loopback, or link-local addresses.

        Returns False if ANY resolved IP is private/internal.

        Args:
            hostname: Hostname to check (e.g., "example.com")

        Returns:
            True if all resolved IPs are safe (public), False otherwise
        """
        try:
            # Get ALL IPs (IPv4 + IPv6) for the hostname
            addr_info = socket.getaddrinfo(hostname, None)

            if not addr_info:
                self.logger.error(f"Could not resolve hostname: {hostname}")
                return False

            # Check each resolved IP address
            for _family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]

                try:
                    ip_obj = ipaddress.ip_address(ip_str)

                    # Block private/loopback/link-local addresses
                    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                        self.logger.error(
                            f"Blocked private/internal IP in webhook URL: {hostname} → {ip_str}"
                        )
                        capture_exception_with_context(
                            Exception(f"SSRF attempt blocked: {hostname} → {ip_str}"),
                            extra={"hostname": hostname, "resolved_ip": ip_str},
                            tags={
                                "component": "webhook",
                                "operation": "ssrf_protection",
                                "severity": "high",
                                "user_facing": "false",
                            },
                        )
                        return False

                except ValueError as e:
                    self.logger.error(f"Invalid IP address from DNS: {ip_str} (error: {e})")
                    return False

            # All resolved IPs are safe (public)
            return True

        except (socket.gaierror, OSError) as e:
            self.logger.error(f"Could not resolve hostname {hostname}: {e}")
            return False

    def _build_payload(self, persona: Persona, event_type: str, event_data: dict) -> dict:
        """
        Build standard event envelope

        Format:
        {
          "event": "conversation.finished",
          "timestamp": "2025-12-20T10:30:00Z",
          "persona": {
            "id": "uuid",
            "name": "Steve Jobs",
            "persona_name": "steve-jobs"
          },
          "data": {
            // Event-specific data
          }
        }
        """
        return {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "persona": {
                "id": str(persona.id),
                "name": persona.name,
                "persona_name": persona.persona_name,
            },
            "data": event_data,
        }

    async def _send_http_post(self, url: str, payload: dict) -> bool:
        """
        POST to webhook URL with timeout and error handling

        CRITICAL SSRF Protection:
        - Re-validates IP safety immediately before request (prevents DNS rebinding)
        - Blocks 3xx redirects (prevents redirect to internal URLs)
        - Uses non-redirecting HTTP client

        Args:
            url: Webhook URL
            payload: JSON payload

        Returns:
            True if 200-299 response, False otherwise
        """
        try:
            # CRITICAL: Re-validate IP safety at request time to prevent DNS rebinding
            # Attacker could change DNS between validation and request
            parsed = urlparse(url)
            if not self._check_ip_safety(parsed.hostname):
                self.logger.error(
                    f"Webhook URL resolved to private IP at request time (DNS rebinding?): {url}"
                )
                capture_exception_with_context(
                    Exception(f"DNS rebinding attack blocked: {url}"),
                    extra={"webhook_url": url, "hostname": parsed.hostname},
                    tags={
                        "component": "webhook",
                        "operation": "dns_rebinding_protection",
                        "severity": "high",
                        "user_facing": "false",
                    },
                )
                return False

            response = await self.http_client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "ExpertClone/1.0",
                },
            )

            # Block redirects (3xx responses)
            # Note: follow_redirects=False already prevents following, but log attempts
            if 300 <= response.status_code < 400:
                self.logger.error(
                    f"Webhook returned redirect (blocked for SSRF protection): "
                    f"{response.status_code} (url: {url})"
                )
                capture_exception_with_context(
                    Exception(f"Webhook redirect attempt blocked: {response.status_code}"),
                    extra={
                        "webhook_url": url,
                        "status_code": response.status_code,
                        "location_header": response.headers.get("Location"),
                    },
                    tags={
                        "component": "webhook",
                        "operation": "redirect_protection",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )
                return False

            # Success: 200-299
            if 200 <= response.status_code < 300:
                return True

            # Failure: non-2xx status
            self.logger.warning(
                f"Webhook returned non-2xx status: {response.status_code} (url: {url})"
            )

            # Log to Sentry
            capture_exception_with_context(
                Exception(f"Webhook HTTP {response.status_code}"),
                extra={
                    "webhook_url": url,
                    "status_code": response.status_code,
                    "response_body": response.text[:500],  # First 500 chars
                    "payload_size": len(json.dumps(payload)),
                },
                tags={
                    "component": "webhook",
                    "operation": "send_http_post",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )

            return False

        except httpx.TimeoutException as e:
            self.logger.error(f"Webhook timeout (url: {url}): {e}")
            capture_exception_with_context(
                e,
                extra={
                    "webhook_url": url,
                    "payload_size": len(json.dumps(payload)),
                },
                tags={
                    "component": "webhook",
                    "operation": "send_http_post",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            return False

        except httpx.RequestError as e:
            self.logger.error(f"Webhook request error (url: {url}): {e}")
            capture_exception_with_context(
                e,
                extra={
                    "webhook_url": url,
                    "payload_size": len(json.dumps(payload)),
                },
                tags={
                    "component": "webhook",
                    "operation": "send_http_post",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            return False

        except Exception as e:
            self.logger.error(f"Unexpected webhook error (url: {url}): {e}")
            capture_exception_with_context(
                e,
                extra={
                    "webhook_url": url,
                    "payload_size": len(json.dumps(payload)),
                },
                tags={
                    "component": "webhook",
                    "operation": "send_http_post",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            return False

    async def close(self):
        """Close HTTP client (cleanup)"""
        await self.http_client.aclose()
