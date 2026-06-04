"""
Tests for WebScraper component
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.monitor import WebScraper


@pytest.fixture
def scraper():
    """Create a WebScraper instance for testing."""
    return WebScraper(
        user_agent="Mozilla/5.0 Test",
        timeout=30
    )


@pytest.mark.asyncio
async def test_scrape_with_httpx_success(scraper):
    """Test successful scraping with httpx."""
    mock_response = Mock()
    mock_response.text = "<html><body>Test content</body></html>"
    mock_response.raise_for_status = Mock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        content = await scraper.scrape_with_httpx("https://example.com")

        assert content == "<html><body>Test content</body></html>"


@pytest.mark.asyncio
async def test_scrape_with_httpx_failure(scraper):
    """Test failed scraping with httpx."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Connection error"))

        content = await scraper.scrape_with_httpx("https://example.com")

        assert content is None


@pytest.mark.asyncio
async def test_scrape_with_playwright_success(scraper):
    """Test successful scraping with Playwright."""
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>JS content</body></html>")
    mock_page.goto = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch('src.monitor.async_playwright') as mock_pw:
        mock_pw.return_value.__aenter__.return_value = mock_playwright

        content = await scraper.scrape_with_playwright("https://example.com")

        assert content == "<html><body>JS content</body></html>"


@pytest.mark.asyncio
async def test_scrape_with_playwright_failure(scraper):
    """Test failed scraping with Playwright."""
    with patch('src.monitor.async_playwright') as mock_pw:
        mock_pw.return_value.__aenter__.side_effect = Exception("Playwright error")

        content = await scraper.scrape_with_playwright("https://example.com")

        assert content is None


@pytest.mark.asyncio
async def test_scrape_requires_js_true(scraper):
    """Test scrape with requires_js=True uses Playwright."""
    with patch.object(scraper, 'scrape_with_playwright', new_callable=AsyncMock) as mock_pw:
        mock_pw.return_value = "<html>JS content</html>"

        content = await scraper.scrape("https://example.com", requires_js=True)

        mock_pw.assert_called_once_with("https://example.com")
        assert content == "<html>JS content</html>"


@pytest.mark.asyncio
async def test_scrape_requires_js_false_success(scraper):
    """Test scrape with requires_js=False uses httpx first."""
    with patch.object(scraper, 'scrape_with_httpx', new_callable=AsyncMock) as mock_httpx:
        mock_httpx.return_value = "<html>Static content</html>"

        content = await scraper.scrape("https://example.com", requires_js=False)

        mock_httpx.assert_called_once_with("https://example.com")
        assert content == "<html>Static content</html>"


@pytest.mark.asyncio
async def test_scrape_fallback_to_playwright(scraper):
    """Test fallback to Playwright when httpx fails."""
    with patch.object(scraper, 'scrape_with_httpx', new_callable=AsyncMock) as mock_httpx, \
         patch.object(scraper, 'scrape_with_playwright', new_callable=AsyncMock) as mock_pw:

        mock_httpx.return_value = None
        mock_pw.return_value = "<html>Fallback content</html>"

        content = await scraper.scrape("https://example.com", requires_js=False)

        mock_httpx.assert_called_once_with("https://example.com")
        mock_pw.assert_called_once_with("https://example.com")
        assert content == "<html>Fallback content</html>"
