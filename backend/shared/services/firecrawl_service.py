"""
Firecrawl URL content fetcher.

Lightweight wrapper around the Firecrawl API for fetching clean markdown/HTML
from URLs. Used by the RAG system for URL content extraction.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    """Result from fetching a single page."""

    url: str
    markdown: Optional[str] = None
    html: Optional[str] = None


class FirecrawlService:
    """Fetches clean content from URLs using Firecrawl API."""

    def __init__(self, api_key: str, base_url: str = "https://api.firecrawl.dev/v1", timeout_sec: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    async def scrape_page(self, url: str) -> PageResult:
        """Scrape a single webpage and return markdown/HTML content."""
        api_url = f"{self.base_url}/scrape"
        payload = {"url": url, "formats": ["markdown", "html"]}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                logger.info(f"Fetching URL content via Firecrawl: {url}")
                response = await client.post(api_url, json=payload, headers=headers)

                if response.status_code != 200:
                    error_msg = f"Firecrawl API error {response.status_code}: {response.text[:500]}"
                    capture_exception_with_context(
                        Exception(error_msg),
                        extra={"url": url, "status_code": response.status_code},
                        tags={
                            "component": "firecrawl",
                            "operation": "scrape_page",
                            "severity": "medium",
                            "user_facing": "false",
                        },
                    )
                    raise Exception(error_msg)

                result = response.json()

                if not result.get("success"):
                    error = result.get("error", "Unknown error")
                    raise Exception(f"Firecrawl scraping failed: {error}")

                data = result.get("data", {})
                metadata = data.get("metadata", {})
                page_url = metadata.get("sourceURL") or data.get("url", url)

                return PageResult(
                    url=page_url,
                    markdown=data.get("markdown"),
                    html=data.get("html"),
                )

        except httpx.TimeoutException:
            raise Exception(f"Firecrawl request timeout for {url}")
        except httpx.HTTPError as e:
            raise Exception(f"HTTP error fetching {url}: {e}")
