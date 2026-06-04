"""
Web scraping functionality for the competitor monitoring tool.
"""
import logging
from typing import Optional
import httpx
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class WebScraper:
    """Handles web scraping with httpx and Playwright fallback."""

    def __init__(self, user_agent: str, timeout: int):
        self.user_agent = user_agent
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    async def scrape_with_httpx(self, url: str) -> Optional[str]:
        """Scrape a URL using httpx (for static pages) with retry logic."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning(f"httpx scraping failed for {url}: {e}")
            return None

    async def scrape_with_playwright(self, url: str) -> Optional[str]:
        """Scrape a URL using Playwright (for JS-rendered pages)."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.user_agent)
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
                content = await page.content()

                await browser.close()
                return content
        except Exception as e:
            logger.error(f"Playwright scraping failed for {url}: {e}")
            return None

    async def scrape(self, url: str, requires_js: bool = False) -> Optional[str]:
        """Scrape a URL, using appropriate method based on JS requirement."""
        if requires_js:
            logger.info(f"Scraping {url} with Playwright (JS required)...")
            return await self.scrape_with_playwright(url)

        logger.info(f"Scraping {url} with httpx...")
        content = await self.scrape_with_httpx(url)

        # Fallback to Playwright if httpx fails
        if content is None:
            logger.info(f"Falling back to Playwright for {url}...")
            content = await self.scrape_with_playwright(url)

        return content
