"""
Internet Search Service

Provides web search functionality with multiple providers and fallbacks:
- DuckDuckGo via ddgs library (primary)
- Brave Search API (fallback)
- DuckDuckGo HTML scraping (final fallback)

Also includes:
- URL content fetching with Firecrawl support
- SSRF protection
- Enhanced context retrieval

Created: 2026-01-25
"""

import asyncio
import ipaddress
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, unquote, urlparse

import httpx

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class InternetSearchService:
    """
    Service for internet search and URL fetching.

    Provides robust search with multiple fallbacks and SSRF protection.
    """

    def __init__(self):
        """Initialize search service."""
        self.logger = logging.getLogger(__name__)

    async def search(
        self, query: str, max_results: int = 5, enhanced_context: bool = True
    ) -> Dict[str, Any]:
        """
        Search the internet and return results with optional enhanced context.

        Args:
            query: Search query
            max_results: Maximum number of results
            enhanced_context: Whether to fetch full content from top URLs

        Returns:
            Dict with 'results', 'formatted_output', and optionally 'enhanced_context'
        """
        try:
            # Check if query contains URLs - fetch their content directly
            url_pattern = r"https?://[^\s]+"
            urls_in_query = re.findall(url_pattern, query)

            if urls_in_query:
                self.logger.info(f"🔗 Found {len(urls_in_query)} URL(s) in query")
                url_contents = await self._fetch_multiple_urls(urls_in_query)
                if url_contents:
                    # Append URL contents to query for context
                    query = query + "\n\n" + url_contents

            # Perform web search
            search_results = await self._perform_web_search(query, max_results)

            if not search_results:
                return {
                    "results": [],
                    "formatted_output": f"I searched for '{query}' but couldn't find relevant results.",
                }

            # Format basic search results
            formatted = self._format_search_results(search_results, query)

            result = {
                "results": search_results,
                "formatted_output": formatted,
            }

            # Fetch top URL contents for enhanced context
            if enhanced_context:
                self.logger.info("🔧 Fetching top URL contents for enhanced context...")
                url_contents = await self._fetch_top_url_contents(search_results, top_n=3)

                if url_contents:
                    # Build hidden context
                    hidden_context = "\n\n---HIDDEN_CONTEXT_START (Not shown to user)---\n"
                    for url_data in url_contents:
                        hidden_context += f"\n**Full Content from: {url_data['title']}**\n"
                        hidden_context += f"URL: {url_data['url']}\n\n"
                        hidden_context += url_data["content"]
                        hidden_context += "\n\n---\n"
                    hidden_context += "---HIDDEN_CONTEXT_END---\n\n"
                    hidden_context += "Use the above detailed content along with the search results to provide a comprehensive, accurate response."

                    result["formatted_output"] = formatted + hidden_context
                    result["enhanced_context"] = url_contents
                    self.logger.info(
                        f"📎 Added {len(url_contents)} URL contents as enhanced context"
                    )

            return result

        except Exception as e:
            self.logger.error(f"❌ Search error: {e}", exc_info=True)
            capture_exception_with_context(
                e,
                extra={"query": query},
                tags={
                    "component": "internet_search_service",
                    "operation": "search",
                    "severity": "medium",
                },
            )
            return {
                "results": [],
                "formatted_output": "I encountered an error while searching.",
            }

    async def fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch content from a single URL.

        Args:
            url: URL to fetch

        Returns:
            Content text or None if fetch failed
        """
        try:
            content = await self._fetch_single_url(url)

            if content:
                self.logger.info(f"✅ Fetched {len(content)} chars from {url}")
                return f"📄 **Content from: {url}**\n\n{content}\n\n---\n\nUse the above content to answer the user's question about this URL."
            else:
                return f"Unable to fetch content from {url}. The site may be blocking access or the URL may be invalid."

        except Exception as e:
            self.logger.error(f"❌ URL fetch error: {e}", exc_info=True)
            capture_exception_with_context(
                e,
                extra={"url": url},
                tags={
                    "component": "internet_search_service",
                    "operation": "fetch_url",
                    "severity": "medium",
                },
            )
            return f"I encountered an error while fetching the URL: {str(e)}"

    async def _perform_web_search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Perform web search using DuckDuckGo with fallbacks.

        Priority order:
        1. DuckDuckGo via ddgs library (with timeout)
        2. Brave Search API (if configured)
        3. DuckDuckGo HTML scraping (fallback)

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of search results with title, snippet, and url
        """
        results = []
        self.logger.info(f"🔧 [SEARCH] Searching for: '{query}'")

        # 1. Try DuckDuckGo via ddgs library with timeout
        try:
            self.logger.info("🔧 [SEARCH] Attempting DuckDuckGo search via ddgs library...")

            # Run the synchronous DDGS in a thread pool with timeout
            def _sync_search():
                try:
                    # Use new ddgs package
                    from ddgs import DDGS

                    with DDGS() as ddgs:
                        return list(ddgs.text(query, max_results=max_results))
                except ImportError:
                    # Fallback to old package name if ddgs not available
                    from duckduckgo_search import DDGS

                    with DDGS() as ddgs:
                        return list(ddgs.text(query, max_results=max_results))

            loop = asyncio.get_event_loop()
            # Add timeout to prevent hanging
            ddg_results = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_search), timeout=20.0
            )

            if ddg_results:
                for item in ddg_results:
                    title = item.get("title", "")
                    url = item.get("href", item.get("link", ""))
                    snippet = item.get("body", item.get("snippet", ""))

                    if title and url:
                        results.append(
                            {
                                "title": title,
                                "url": url,
                                "snippet": snippet[:300] if snippet else "",
                            }
                        )
                        self.logger.info(f"🔧 [SEARCH] DDG Result: {title[:50]}...")

                if results:
                    self.logger.info(f"🔧 [SEARCH] DuckDuckGo returned {len(results)} results")
                    return results
            else:
                self.logger.warning("🔧 [SEARCH] DuckDuckGo returned no results")

        except asyncio.TimeoutError:
            self.logger.warning("🔧 [SEARCH] DuckDuckGo search timed out after 20s")
        except ImportError as e:
            self.logger.warning(f"🔧 [SEARCH] ddgs/duckduckgo-search not installed: {e}")
        except Exception as e:
            self.logger.warning(f"🔧 [SEARCH] DuckDuckGo search failed: {e}")

        # 2. Try Brave Search API if configured
        brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if brave_api_key:
            try:
                self.logger.info("🔧 [SEARCH] Attempting Brave Search API...")
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": max_results},
                        headers={
                            "Accept": "application/json",
                            "X-Subscription-Token": brave_api_key,
                        },
                    )

                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("web", {}).get("results", [])[:max_results]:
                            results.append(
                                {
                                    "title": item.get("title", ""),
                                    "url": item.get("url", ""),
                                    "snippet": item.get("description", "")[:300],
                                }
                            )
                            self.logger.info(
                                f"🔧 [SEARCH] Brave Result: {item.get('title', '')[:50]}..."
                            )

                        if results:
                            self.logger.info(
                                f"🔧 [SEARCH] Brave Search returned {len(results)} results"
                            )
                            return results
                    else:
                        self.logger.warning(
                            f"🔧 [SEARCH] Brave Search returned status {response.status_code}"
                        )
            except Exception as e:
                self.logger.warning(f"🔧 [SEARCH] Brave Search failed: {e}")

        # 3. Final fallback: DuckDuckGo HTML scraping
        try:
            self.logger.info("🔧 [SEARCH] Attempting DuckDuckGo HTML scraping fallback...")

            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    search_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    html = response.text

                    # Extract results using regex patterns
                    result_pattern = (
                        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
                    )
                    snippet_pattern = r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>([^<]*)</a>'

                    links = re.findall(result_pattern, html, re.IGNORECASE)
                    snippets = re.findall(snippet_pattern, html, re.IGNORECASE)

                    for i, (url, title) in enumerate(links[:max_results]):
                        # Decode DuckDuckGo redirect URLs
                        if "uddg=" in url:
                            url_match = re.search(r"uddg=([^&]*)", url)
                            if url_match:
                                url = unquote(url_match.group(1))

                        if title and url and url.startswith("http"):
                            snippet = snippets[i] if i < len(snippets) else ""
                            results.append(
                                {
                                    "title": title.strip(),
                                    "url": url,
                                    "snippet": snippet[:300] if snippet else "",
                                }
                            )
                            self.logger.info(f"🔧 [SEARCH] HTML Result: {title.strip()[:50]}...")

                    if results:
                        self.logger.info(
                            f"🔧 [SEARCH] HTML scraping returned {len(results)} results"
                        )
                        return results

        except Exception as e:
            self.logger.warning(f"🔧 [SEARCH] HTML scraping fallback failed: {e}")

        self.logger.warning("🔧 [SEARCH] All search methods failed, returning empty results")
        return results

    def _is_safe_url(self, url: str) -> bool:
        """
        Validate URL to prevent SSRF attacks.

        Blocks:
        - Private IPs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
        - Loopback (127.0.0.0/8, ::1)
        - Link-local (169.254.0.0/16, fe80::/10)
        - Cloud metadata endpoints (169.254.169.254)
        - localhost by hostname

        Args:
            url: URL to validate

        Returns:
            True if safe, False otherwise
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"]:
                self.logger.warning(f"⚠️ Blocked URL with invalid scheme: {url}")
                return False
            if not parsed.hostname:
                self.logger.warning(f"⚠️ Blocked URL with no hostname: {url}")
                return False

            # Try to parse as IP address for comprehensive private IP blocking
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                # Block private, loopback, link-local, and reserved IPs
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    self.logger.warning(f"⚠️ Blocked private/internal IP: {url}")
                    return False
                # Explicitly block cloud metadata endpoints
                if str(ip) == "169.254.169.254":
                    self.logger.warning(f"⚠️ Blocked metadata endpoint: {url}")
                    return False
            except ValueError:
                # Not an IP address - hostname/domain
                # Block localhost by hostname
                if parsed.hostname.lower() in ["localhost", "localhost.localdomain"]:
                    self.logger.warning(f"⚠️ Blocked localhost hostname: {url}")
                    return False

            return True
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"url": url},
                tags={
                    "component": "internet_search_service",
                    "operation": "url_validation",
                    "severity": "medium",
                },
            )
            self.logger.warning(f"⚠️ URL validation error for {url}: {e}")
            return False

    async def _fetch_single_url(self, url: str) -> Optional[str]:
        """
        Fetch content from a single URL.

        Uses Firecrawl if available, falls back to httpx.

        Args:
            url: URL to fetch content from

        Returns:
            Content text or None if fetch failed
        """
        MAX_CONTENT = 50_000  # 50KB limit

        # Validate URL first (SSRF protection)
        if not self._is_safe_url(url):
            return None

        content_text = None

        # Try Firecrawl first (handles anti-bot protection, JavaScript rendering)
        if settings.firecrawl_api_key:
            try:
                from shared.services.firecrawl_service import FirecrawlService

                firecrawl_provider = FirecrawlService(
                    api_key=settings.firecrawl_api_key,
                    base_url=settings.firecrawl_base_url,
                    timeout_sec=30,
                )
                self.logger.info(f"🔥 Fetching {url} via Firecrawl...")
                page_result = await firecrawl_provider.scrape_page(url)
                # Prefer markdown content (cleaner for LLM), fallback to HTML
                content_text = page_result.markdown or page_result.html or ""
                content_text = content_text[:MAX_CONTENT]
                self.logger.info(
                    f"✅ Firecrawl successfully fetched {len(content_text)} chars from {url}"
                )
                return content_text
            except Exception as fc_error:
                capture_exception_with_context(
                    fc_error,
                    extra={"url": url, "provider": "firecrawl"},
                    tags={
                        "component": "internet_search_service",
                        "operation": "fetch_url_firecrawl",
                        "severity": "low",
                    },
                )
                self.logger.warning(
                    f"⚠️ Firecrawl failed for {url}: {fc_error}, falling back to httpx"
                )
                content_text = None

        # Fallback to basic httpx
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
            ) as client:
                response = await client.get(url)
                if len(response.content) > 300 * 1024:  # 300KB limit for raw fetch
                    self.logger.warning(f"⚠️ URL content exceeds 300KB, truncating: {url}")
                content_text = response.text[:MAX_CONTENT]
                self.logger.info(
                    f"✅ httpx successfully fetched {len(content_text)} chars from {url}"
                )
                return content_text
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"url": url, "provider": "httpx"},
                tags={
                    "component": "internet_search_service",
                    "operation": "fetch_url_httpx",
                    "severity": "low",
                },
            )
            self.logger.warning(f"⚠️ Failed to fetch {url} via httpx: {e}")
            return None

    async def _fetch_top_url_contents(
        self, search_results: List[Dict[str, str]], top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Fetch content from top N search result URLs.

        This content is added as hidden context (not shown to frontend but available to LLM).

        Args:
            search_results: List of search results with URLs
            top_n: Number of top URLs to fetch (default: 3)

        Returns:
            List of dictionaries with url, title, and content
        """
        if not search_results:
            return []

        url_contents = []
        MAX_CONTENT_PER_URL = 5_000  # 5KB per URL — keeps total context manageable for LLM

        # Fetch content from top N URLs
        for i, result in enumerate(search_results[:top_n]):
            url = result.get("url", "")
            title = result.get("title", "")

            if not url:
                continue

            try:
                self.logger.info(f"🔧 Fetching content from top result #{i + 1}: {url}")
                content = await self._fetch_single_url(url)

                if content:
                    content = content[:MAX_CONTENT_PER_URL]
                    url_contents.append(
                        {
                            "url": url,
                            "title": title,
                            "content": content,
                            "hidden": True,  # Mark as hidden from frontend
                        }
                    )
                    self.logger.info(f"✅ Fetched {len(content)} chars from {url}")
                else:
                    self.logger.warning(f"⚠️ No content retrieved from {url}")

            except Exception as e:
                self.logger.warning(f"⚠️ Failed to fetch content from {url}: {e}")
                # Continue with next URL instead of failing completely
                continue

        self.logger.info(f"📦 Successfully fetched content from {len(url_contents)} URLs")
        return url_contents

    async def _fetch_multiple_urls(self, urls: List[str]) -> str:
        """
        Fetch content from multiple URLs and combine.

        Args:
            urls: List of URLs to fetch

        Returns:
            Combined content text
        """
        url_contents = []
        MAX_TOTAL_CONTENT = 100_000  # 100KB total limit
        total_content_size = 0

        for url in urls:
            if total_content_size >= MAX_TOTAL_CONTENT:
                self.logger.warning("⚠️ Total URL content limit reached, skipping remaining URLs")
                break

            content = await self._fetch_single_url(url)
            if content:
                # Check if adding this content would exceed total limit
                if total_content_size + len(content) > MAX_TOTAL_CONTENT:
                    remaining = MAX_TOTAL_CONTENT - total_content_size
                    content = content[:remaining]
                    self.logger.warning(
                        f"⚠️ Truncating content from {url} to fit within total limit"
                    )

                url_contents.append(
                    f"\n\n--- Content from {url} ---\n{content}\n--- End of URL content ---\n"
                )
                total_content_size += len(content)

        if url_contents:
            self.logger.info(
                f"📎 Fetched {len(url_contents)} URL content(s) (total size: {total_content_size} bytes)"
            )

        return "".join(url_contents)

    def _format_search_results(self, results: List[Dict[str, str]], query: str) -> str:
        """
        Format search results for display.

        Args:
            results: List of search results
            query: Original search query

        Returns:
            Formatted search results string
        """
        if not results:
            return f"No results found for '{query}'."

        formatted = f"🔍 **Search Results for: '{query}'**\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"**{i}. {result['title']}**\n"
            if result["snippet"]:
                formatted += f"   {result['snippet']}\n"
            formatted += f"   🔗 {result['url']}\n\n"

        return formatted
