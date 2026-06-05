"""
Tests for WebScraper component
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.scraper import WebScraper


@pytest.fixture
def scraper():
    return WebScraper(user_agent="Mozilla/5.0 Test", timeout=30)


# ---------------------------------------------------------------------------
# scrape_with_httpx
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scrape_with_httpx_success(scraper):
    mock_response = Mock()
    mock_response.text = "<html><body>Test content</body></html>"
    mock_response.raise_for_status = Mock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        content = await scraper.scrape_with_httpx("https://example.com")

    assert content == "<html><body>Test content</body></html>"


@pytest.mark.asyncio
async def test_scrape_with_httpx_failure(scraper):
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Connection error")
        )
        content = await scraper.scrape_with_httpx("https://example.com")

    assert content is None


# ---------------------------------------------------------------------------
# scrape_with_playwright
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_playwright_success():
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
    return mock_playwright


@pytest.mark.asyncio
async def test_scrape_with_playwright_success(scraper, mock_playwright_success):
    with patch('src.scraper.async_playwright') as mock_pw:
        mock_pw.return_value.__aenter__.return_value = mock_playwright_success
        content = await scraper.scrape_with_playwright("https://example.com")

    assert content == "<html><body>JS content</body></html>"


@pytest.mark.asyncio
async def test_scrape_with_playwright_failure(scraper):
    with patch('src.scraper.async_playwright') as mock_pw:
        mock_pw.return_value.__aenter__.side_effect = Exception("Playwright error")
        content = await scraper.scrape_with_playwright("https://example.com")

    assert content is None


# ---------------------------------------------------------------------------
# scrape (routing + fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scrape_requires_js_true(scraper):
    with patch.object(scraper, 'scrape_with_playwright', new_callable=AsyncMock) as mock_pw:
        mock_pw.return_value = "<html><body>JS content</body></html>"
        content = await scraper.scrape("https://example.com", requires_js=True)

    mock_pw.assert_called_once_with("https://example.com")
    assert "JS content" in content


@pytest.mark.asyncio
async def test_scrape_requires_js_false_success(scraper):
    with patch.object(scraper, 'scrape_with_httpx', new_callable=AsyncMock) as mock_httpx:
        mock_httpx.return_value = "<html><body>Static content</body></html>"
        content = await scraper.scrape("https://example.com", requires_js=False)

    mock_httpx.assert_called_once_with("https://example.com")
    assert "Static content" in content


@pytest.mark.asyncio
async def test_scrape_fallback_to_playwright(scraper):
    with patch.object(scraper, 'scrape_with_httpx', new_callable=AsyncMock) as mock_httpx, \
         patch.object(scraper, 'scrape_with_playwright', new_callable=AsyncMock) as mock_pw:
        mock_httpx.return_value = None
        mock_pw.return_value = "<html><body>Fallback content</body></html>"
        content = await scraper.scrape("https://example.com", requires_js=False)

    mock_httpx.assert_called_once_with("https://example.com")
    mock_pw.assert_called_once_with("https://example.com")
    assert "Fallback content" in content


@pytest.mark.asyncio
async def test_scrape_returns_none_when_both_fail(scraper):
    with patch.object(scraper, 'scrape_with_httpx', new_callable=AsyncMock) as mock_httpx, \
         patch.object(scraper, 'scrape_with_playwright', new_callable=AsyncMock) as mock_pw:
        mock_httpx.return_value = None
        mock_pw.return_value = None
        content = await scraper.scrape("https://example.com", requires_js=False)

    assert content is None


# ---------------------------------------------------------------------------
# extract_meaningful_content
# ---------------------------------------------------------------------------

def test_extract_strips_script_tags(scraper):
    html = "<html><body><p>Meaningful page text</p><script>alert('xss')</script></body></html>"
    result = scraper.extract_meaningful_content(html)
    assert "alert" not in result
    assert "Meaningful page text" in result


def test_extract_strips_style_tags(scraper):
    html = "<html><body><p>Meaningful page content</p><style>body { color: red; }</style></body></html>"
    result = scraper.extract_meaningful_content(html)
    assert "color" not in result
    assert "Meaningful page content" in result


def test_extract_strips_noscript_tags(scraper):
    html = "<html><body><p>Real page content</p><noscript>Enable JS</noscript></body></html>"
    result = scraper.extract_meaningful_content(html)
    assert "Enable JS" not in result
    assert "Real page content" in result


def test_extract_strips_head_meta_link(scraper):
    html = """<html>
    <head>
        <meta charset="utf-8">
        <link rel="stylesheet" href="style.css">
        <title>Page Title</title>
    </head>
    <body><p>Body text</p></body>
    </html>"""
    result = scraper.extract_meaningful_content(html)
    assert "utf-8" not in result
    assert "style.css" not in result
    assert "Body text" in result


def test_extract_removes_analytics_class_divs(scraper):
    html = """<html><body>
    <p>Good content</p>
    <div class="analytics-tracker">track me</div>
    <div class="cookie-consent">Accept cookies</div>
    </body></html>"""
    result = scraper.extract_meaningful_content(html)
    assert "track me" not in result
    assert "Accept cookies" not in result
    assert "Good content" in result


def test_extract_filters_short_lines(scraper):
    html = "<html><body><p>ab</p><p>This is meaningful content</p></body></html>"
    result = scraper.extract_meaningful_content(html)
    assert "This is meaningful content" in result
    # Two-char line should be filtered
    assert "\nab\n" not in result


def test_extract_filters_pure_number_lines(scraper):
    html = "<html><body><p>12345</p><p>Real text here</p></body></html>"
    result = scraper.extract_meaningful_content(html)
    assert "Real text here" in result
    assert "12345" not in result


def test_extract_empty_html(scraper):
    result = scraper.extract_meaningful_content("")
    assert result == ""


def test_extract_only_scripts(scraper):
    html = "<html><head></head><body><script>var x = 1;</script></body></html>"
    result = scraper.extract_meaningful_content(html)
    assert "var x" not in result


def test_extract_returns_string(scraper):
    html = "<html><body><p>Hello world</p></body></html>"
    result = scraper.extract_meaningful_content(html)
    assert isinstance(result, str)
    assert len(result) > 0
