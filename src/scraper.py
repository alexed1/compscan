"""
Web scraping functionality for the competitor monitoring tool.
"""
import logging
from typing import Optional
import httpx
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebScraper:
    """Handles web scraping with httpx and Playwright fallback."""

    def __init__(self, user_agent: str, timeout: int):
        self.user_agent = user_agent
        self.timeout = timeout

    def extract_meaningful_content(self, html: str) -> str:
        """Extract only meaningful content from HTML, ignoring scripts, styles, and metadata."""
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        # Remove meta tags, links to stylesheets, and other non-content elements
        for tag in soup(["meta", "link", "head"]):
            tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()

        # Remove common dynamic content containers (e.g., analytics, tracking)
        for tag in soup.find_all(attrs={"class": lambda x: x and any(
            keyword in str(x).lower() for keyword in ["analytics", "tracking", "cookie", "consent"]
        )}):
            tag.decompose()

        # Extract text content
        text = soup.get_text(separator='\n', strip=True)

        # Clean up whitespace and remove empty lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Filter out lines that look like timestamps, IDs, or other dynamic content
        # (lines that are purely numbers, UUIDs, or very short)
        meaningful_lines = [
            line for line in lines
            if len(line) > 2 and not line.replace('-', '').replace(':', '').replace('.', '').isdigit()
        ]

        return '\n'.join(meaningful_lines)

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
            html = await self.scrape_with_playwright(url)
        else:
            logger.info(f"Scraping {url} with httpx...")
            html = await self.scrape_with_httpx(url)

            # Fallback to Playwright if httpx fails
            if html is None:
                logger.info(f"Falling back to Playwright for {url}...")
                html = await self.scrape_with_playwright(url)

        # Extract only meaningful content
        if html:
            return self.extract_meaningful_content(html)
        return None
