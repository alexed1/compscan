"""
Tests for EmailReporter component
"""
import pytest
from unittest.mock import Mock, patch
from src.monitor import EmailReporter


@pytest.fixture
def email_reporter():
    """Create an EmailReporter instance for testing."""
    return EmailReporter(
        api_key="test_api_key",
        from_email="test@example.com",
        from_name="Test Sender",
        to_emails=["recipient@example.com"]
    )


def test_email_reporter_initialization(email_reporter):
    """Test EmailReporter initialization."""
    assert email_reporter.from_email == "test@example.com"
    assert email_reporter.from_name == "Test Sender"
    assert email_reporter.to_emails == ["recipient@example.com"]


def test_generate_html_digest_no_changes(email_reporter):
    """Test HTML generation with no changes."""
    changes = []
    analysis = "No changes detected."
    timestamp = "2024-01-15 12:00 UTC"

    html = email_reporter._generate_html_digest(changes, analysis, timestamp)

    assert "Competitor Intelligence Report" in html
    assert "2024-01-15 12:00 UTC" in html
    assert "Changes Detected: 0" in html
    assert "No changes detected." in html


def test_generate_html_digest_with_changes(email_reporter):
    """Test HTML generation with changes."""
    changes = [
        {
            "name": "Competitor A",
            "url": "https://competitor-a.com",
            "content": "<html>content</html>",
            "last_checked": "2024-01-14 12:00 UTC"
        },
        {
            "name": "Competitor B",
            "url": "https://competitor-b.com",
            "content": "<html>content2</html>",
            "last_checked": "2024-01-14 11:00 UTC"
        }
    ]
    analysis = "## Analysis\nSignificant changes detected."
    timestamp = "2024-01-15 12:00 UTC"

    html = email_reporter._generate_html_digest(changes, analysis, timestamp)

    # Check structure
    assert "Changes Detected: 2" in html
    assert "Competitor A" in html
    assert "https://competitor-a.com" in html
    assert "Competitor B" in html
    assert "https://competitor-b.com" in html
    assert "2024-01-14 12:00 UTC" in html

    # Check that markdown is converted to HTML
    assert "<h2>Analysis</h2>" in html
    assert "<p>Significant changes detected.</p>" in html
    # Should NOT contain raw markdown
    assert "## Analysis" not in html


def test_generate_html_digest_markdown_conversion(email_reporter):
    """Test that markdown is properly converted to HTML."""
    changes = [{
        "name": "Test",
        "url": "https://test.com",
        "content": "test",
        "last_checked": "Never"
    }]

    # Test various markdown elements
    analysis = """
# Heading 1
## Heading 2
### Heading 3

**Bold text** and *italic text*

- List item 1
- List item 2
- List item 3

1. Numbered item 1
2. Numbered item 2

[Link text](https://example.com)
"""

    html = email_reporter._generate_html_digest(changes, analysis, "2024-01-15 12:00 UTC")

    # Check HTML conversion
    assert "<h1>Heading 1</h1>" in html
    assert "<h2>Heading 2</h2>" in html
    assert "<h3>Heading 3</h3>" in html
    assert "<strong>Bold text</strong>" in html
    assert "<em>italic text</em>" in html
    assert "<li>List item 1</li>" in html
    assert "<a href=\"https://example.com\">Link text</a>" in html

    # Should NOT contain raw markdown
    assert "**Bold text**" not in html
    assert "*italic text*" not in html


def test_send_digest_no_changes(email_reporter):
    """Test that no email is sent when there are no changes."""
    result = email_reporter.send_digest([], "No changes", "[Test]")

    assert result is True  # Should return True but skip sending


def test_send_digest_success(email_reporter):
    """Test successful email sending."""
    changes = [{
        "name": "Test Competitor",
        "url": "https://test.com",
        "content": "content",
        "last_checked": "Never"
    }]
    analysis = "Test analysis"

    with patch('resend.Emails.send') as mock_send:
        mock_send.return_value = {"id": "email_123"}

        result = email_reporter.send_digest(changes, analysis, "[Test]")

        assert result is True
        mock_send.assert_called_once()

        # Check email parameters
        call_args = mock_send.call_args[0][0]
        assert call_args['from'] == "Test Sender <test@example.com>"
        assert call_args['to'] == ["recipient@example.com"]
        assert "[Test]" in call_args['subject']
        assert "1 change(s) detected" in call_args['subject']
        assert "html" in call_args
        assert len(call_args['html']) > 0


def test_send_digest_multiple_recipients(email_reporter):
    """Test email sending to multiple recipients."""
    email_reporter.to_emails = ["user1@example.com", "user2@example.com", "user3@example.com"]

    changes = [{
        "name": "Test",
        "url": "https://test.com",
        "content": "content",
        "last_checked": "Never"
    }]

    with patch('resend.Emails.send') as mock_send:
        mock_send.return_value = {"id": "email_123"}

        result = email_reporter.send_digest(changes, "Analysis", "[Test]")

        assert result is True
        assert mock_send.call_count == 3  # Should send to each recipient


def test_send_digest_failure(email_reporter):
    """Test email sending failure handling."""
    changes = [{
        "name": "Test",
        "url": "https://test.com",
        "content": "content",
        "last_checked": "Never"
    }]

    with patch('resend.Emails.send') as mock_send:
        mock_send.side_effect = Exception("Email sending failed")

        result = email_reporter.send_digest(changes, "Analysis", "[Test]")

        assert result is False


def test_html_email_structure(email_reporter):
    """Test that generated HTML has proper email structure."""
    changes = [{
        "name": "Test",
        "url": "https://test.com",
        "content": "content",
        "last_checked": "Never"
    }]
    html = email_reporter._generate_html_digest(changes, "Test", "2024-01-15 12:00 UTC")

    # Check HTML document structure
    assert "<!DOCTYPE html>" in html
    assert "<html>" in html and "</html>" in html
    assert "<head>" in html and "</head>" in html
    assert "<body" in html and "</body>" in html
    assert "<meta charset=\"utf-8\">" in html
    assert "viewport" in html

    # Check CSS styling
    assert "<style>" in html or "style=" in html
    assert "analysis-content" in html

    # Check branding
    assert "Generated by Competitor Monitoring Tool" in html
    assert "Powered by Claude AI" in html
