"""
Web scraping functionality for the competitor monitoring tool.
"""
import logging
from typing import Optional
import httpx
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from bs4 import BeautifulSoup
from blog_extractor import BlogExtractor

logger = logging.getLogger(__name__)

_MIN_LINE_LENGTH = 3
_MAX_SINGLE_WORD_LENGTH = 20
_PLAYWRIGHT_TIMEOUT_MULTIPLIER = 1000


class WebScraper:
    """Handles web scraping with httpx and Playwright fallback."""

    def __init__(self, user_agent: str, timeout: int):
        self.user_agent = user_agent
        self.timeout = timeout
        self.blog_extractor = BlogExtractor()

    def extract_meaningful_content(self, html: str) -> str:
        """Extract only meaningful content from HTML, ignoring scripts, styles, and metadata."""
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        # Remove meta tags, links to stylesheets, and other non-content elements
        for tag in soup(["meta", "link", "head"]):
            tag.decompose()

        # Remove common page chrome that changes frequently
        # Navigation menus, headers, footers often have dynamic elements
        for tag in soup.find_all(['nav', 'header', 'footer']):
            tag.decompose()

        # Remove common dynamic content containers
        for tag in soup.find_all(attrs={"class": lambda x: x and any(
            keyword in str(x).lower() for keyword in [
                "analytics", "tracking", "cookie", "consent",
                "nav", "header", "footer", "menu", "sidebar",
                "testimonial", "review", "carousel", "slider", "rotating"
            ]
        )}):
            tag.decompose()

        # Remove by common ID patterns
        for tag in soup.find_all(attrs={"id": lambda x: x and any(
            keyword in str(x).lower() for keyword in [
                "nav", "header", "footer", "menu", "sidebar"
            ]
        )}):
            tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()

        # Extract text content
        text = soup.get_text(separator='\n', strip=True)

        # Clean up whitespace and remove empty lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Filter out lines that look like timestamps, IDs, or other dynamic content
        # Also filter out very common generic text and copyright notices
        meaningful_lines = []
        for line in lines:
            if len(line) < _MIN_LINE_LENGTH:
                continue
            if line.replace('-', '').replace(':', '').replace('.', '').isdigit():
                continue
            if any(pattern in line.lower() for pattern in [
                '© 20', 'all rights reserved', 'cookie preferences',
                'product of the', 'customer of the', 'featured on',
                'as seen on', 'trusted by'
            ]):
                continue
            if len(line.split()) == 1 and len(line) < _MAX_SINGLE_WORD_LENGTH:
                continue

            meaningful_lines.append(line)

        return '\n'.join(meaningful_lines)

    async def scrape_with_httpx(self, url: str) -> Optional[str]:
        """Scrape a URL using httpx (for static pages) with retry logic."""
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        )
        async def _fetch():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                return response.text

        try:
            return await _fetch()
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

                await page.goto(url, wait_until="networkidle", timeout=self.timeout * _PLAYWRIGHT_TIMEOUT_MULTIPLIER)
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

        # Extract meaningful content based on page type
        if html:
            # Use specialized blog extraction for blog/resource pages
            if self.blog_extractor.is_blog_page(url):
                logger.info(f"Using blog extraction for {url}")
                return self.blog_extractor.extract_blog_posts(html)
            else:
                return self.extract_meaningful_content(html)
        return None
