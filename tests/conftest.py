"""
Pytest configuration and shared fixtures
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# Make pytest work with async tests
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def sample_html_content():
    """Sample HTML content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Welcome to Test Site</h1>
        <p>This is test content.</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_competitor_changes():
    """Sample competitor changes data for testing."""
    return [
        {
            "name": "Competitor A - Homepage",
            "url": "https://competitor-a.com",
            "content": "<html>Page content</html>",
            "last_checked": "2024-01-14 09:00:00"
        },
        {
            "name": "Competitor B - Pricing",
            "url": "https://competitor-b.com/pricing",
            "content": "<html>Pricing page</html>",
            "last_checked": "2024-01-14 09:05:00"
        }
    ]
