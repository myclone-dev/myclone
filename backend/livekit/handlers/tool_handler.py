"""
Tool Handler

Function tools for LiveKit agent:
- Internet search with SSRF protection
- URL fetching with Firecrawl support
- Calendar link sending

Created: 2026-01-25
"""

import logging
from typing import Optional

from livekit.agents.llm.tool_context import ToolError
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class ToolHandler:
    """
    Handles function tool operations.

    Responsibilities:
    - Internet search (when enabled)
    - URL fetching and content extraction
    - Calendar link sharing
    """

    def __init__(
        self,
        room,
        search_enabled: bool = False,
        calendar_enabled: bool = False,
        calendar_url: Optional[str] = None,
        calendar_display_name: Optional[str] = None,
    ):
        """
        Initialize tool handler.

        Args:
            room: LiveKit room instance
            search_enabled: Whether internet search is enabled
            calendar_enabled: Whether calendar is enabled
            calendar_url: Calendar booking URL
            calendar_display_name: Calendar display name
        """
        self.room = room
        self.search_enabled = search_enabled
        self.calendar_enabled = calendar_enabled
        self.calendar_url = calendar_url
        self.calendar_display_name = calendar_display_name
        self.logger = logging.getLogger(__name__)

    async def _publish_status(self, status: str, message: str = "") -> None:
        """Publish agent status event to frontend via data channel."""
        from livekit.utils import publish_agent_status

        await publish_agent_status(self.room, status, message)

    async def search_internet(self, query: str) -> str:
        """
        Search the internet for current information.

        Args:
            query: Search query

        Returns:
            Search results with enhanced context

        Raises:
            ToolError: If search is not enabled or fails
        """
        self.logger.info(f"🔍 [TOOL] search_internet('{query}')")

        if not self.search_enabled:
            raise ToolError(
                "Internet search is not available for this persona. "
                "Please ask the persona owner to enable search in settings."
            )

        await self._publish_status("searching", "Searching the internet...")
        try:
            from shared.services.internet_search_service import InternetSearchService

            search_service = InternetSearchService()
            result = await search_service.search(query, max_results=5, enhanced_context=True)

            # Return the formatted output which includes enhanced context
            return result.get("formatted_output", "No results found.")

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "query": query[:200],
                    "search_enabled": self.search_enabled,
                },
                tags={
                    "component": "tool_handler",
                    "operation": "search_internet",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Search failed: {e}", exc_info=True)
            raise ToolError(f"Search failed: {str(e)}")
        finally:
            await self._publish_status("idle")

    async def fetch_url(self, url: str) -> str:
        """
        Fetch content from a URL.

        Uses InternetSearchService with Firecrawl support and SSRF protection.

        Args:
            url: URL to fetch

        Returns:
            Page content

        Raises:
            ToolError: If URL is invalid or fetch fails
        """
        self.logger.info(f"🌐 [TOOL] fetch_url('{url}')")

        await self._publish_status("fetching", "Fetching content...")
        try:
            from shared.services.internet_search_service import InternetSearchService

            search_service = InternetSearchService()
            content = await search_service.fetch_url(url)

            if content:
                return content
            else:
                raise ToolError(f"Failed to fetch content from {url}")

        except ToolError:
            raise
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "url": url[:500],
                },
                tags={
                    "component": "tool_handler",
                    "operation": "fetch_url",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Error fetching {url}: {e}", exc_info=True)
            raise ToolError(f"Failed to fetch URL: {str(e)}")
        finally:
            await self._publish_status("idle")

    async def send_calendar_link(self) -> str:
        """
        Send calendar booking link to user.

        Returns:
            Success message

        Raises:
            ToolError: If calendar is not enabled
        """
        self.logger.info("📅 [TOOL] send_calendar_link()")

        if not self.calendar_enabled or not self.calendar_url:
            raise ToolError("Calendar booking is not available for this persona.")

        try:
            await self.room.local_participant.publish_data(
                payload=self.calendar_url.encode("utf-8"),
                topic="calendar",
                reliable=True,
            )
            self.logger.info(f"✅ Calendar link sent: {self.calendar_url}")

            display_name = self.calendar_display_name or "my calendar"
            return f"I've sent you {display_name} link. Feel free to choose a time that works best for you!"

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "calendar_enabled": self.calendar_enabled,
                    "has_calendar_url": bool(self.calendar_url),
                },
                tags={
                    "component": "tool_handler",
                    "operation": "send_calendar_link",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Error sending calendar link: {e}", exc_info=True)
            raise ToolError("I encountered an issue sending the calendar link.")
