"""
Tests for CompetitiveIntelligenceAnalyzer component
"""
import pytest
from unittest.mock import MagicMock, patch
from src.analyzer import CompetitiveIntelligenceAnalyzer
from src.models import CompetitorChange


def make_change(name="Acme - Homepage", url="https://acme.com", content="page content"):
    return CompetitorChange(name=name, url=url, content=content, last_checked="2024-01-14 12:00 UTC")


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def test_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        CompetitiveIntelligenceAnalyzer(provider="gemini", api_key="x", model="m", max_tokens=100)


def test_anthropic_provider_accepted():
    with patch("src.analyzer.Anthropic"):
        analyzer = CompetitiveIntelligenceAnalyzer(
            provider="anthropic", api_key="key", model="claude-sonnet-4-5", max_tokens=1024
        )
    assert analyzer.provider == "anthropic"


def test_openai_provider_accepted():
    with patch("src.analyzer.OpenAI"):
        analyzer = CompetitiveIntelligenceAnalyzer(
            provider="openai", api_key="key", model="gpt-4o", max_tokens=1024
        )
    assert analyzer.provider == "openai"


# ---------------------------------------------------------------------------
# analyze_changes — empty list fast-path
# ---------------------------------------------------------------------------

def test_analyze_changes_empty_returns_no_changes_string():
    with patch("src.analyzer.Anthropic"):
        analyzer = CompetitiveIntelligenceAnalyzer(
            provider="anthropic", api_key="key", model="m", max_tokens=100
        )
    result = analyzer.analyze_changes([])
    assert "No changes detected" in result
    # Client should never be called
    analyzer.client.messages.create.assert_not_called() if hasattr(analyzer.client, 'messages') else None


# ---------------------------------------------------------------------------
# Anthropic path
# ---------------------------------------------------------------------------

@pytest.fixture
def anthropic_analyzer():
    with patch("src.analyzer.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        analyzer = CompetitiveIntelligenceAnalyzer(
            provider="anthropic", api_key="key", model="claude-sonnet-4-5", max_tokens=1024
        )
        yield analyzer, mock_client


def test_anthropic_analyze_calls_api(anthropic_analyzer):
    analyzer, mock_client = anthropic_analyzer
    mock_client.messages.create.return_value.content = [MagicMock(text="Insight text")]

    result = analyzer.analyze_changes([make_change()])

    mock_client.messages.create.assert_called_once()
    assert result == "Insight text"


def test_anthropic_prompt_contains_competitor_name(anthropic_analyzer):
    analyzer, mock_client = anthropic_analyzer
    mock_client.messages.create.return_value.content = [MagicMock(text="ok")]

    analyzer.analyze_changes([make_change("Vertex - Homepage", "https://vertexinc.com")])

    prompt = mock_client.messages.create.call_args[1]["messages"][0]["content"]
    assert "Vertex - Homepage" in prompt
    assert "https://vertexinc.com" in prompt


def test_anthropic_content_preview_capped_at_500_chars(anthropic_analyzer):
    analyzer, mock_client = anthropic_analyzer
    mock_client.messages.create.return_value.content = [MagicMock(text="ok")]

    long_content = "x" * 2000
    analyzer.analyze_changes([make_change(content=long_content)])

    prompt = mock_client.messages.create.call_args[1]["messages"][0]["content"]
    # The preview in the prompt should be at most 500 x's (plus "...")
    x_count = prompt.count("x" * 500)
    assert x_count >= 1
    assert "x" * 501 not in prompt


def test_anthropic_receives_system_prompt_as_parameter(anthropic_analyzer):
    analyzer, mock_client = anthropic_analyzer
    mock_client.messages.create.return_value.content = [MagicMock(text="ok")]

    analyzer.analyze_changes([make_change()])

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["system"] == analyzer.system_prompt


def test_anthropic_api_exception_returns_error_string(anthropic_analyzer):
    analyzer, mock_client = anthropic_analyzer
    mock_client.messages.create.side_effect = Exception("rate limited")

    result = analyzer.analyze_changes([make_change()])

    assert "Error analyzing changes" in result
    assert "rate limited" in result


# ---------------------------------------------------------------------------
# OpenAI path
# ---------------------------------------------------------------------------

@pytest.fixture
def openai_analyzer():
    with patch("src.analyzer.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        analyzer = CompetitiveIntelligenceAnalyzer(
            provider="openai", api_key="key", model="gpt-4o", max_tokens=1024
        )
        yield analyzer, mock_client


def test_openai_analyze_calls_api(openai_analyzer):
    analyzer, mock_client = openai_analyzer
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="OpenAI insight"))
    ]

    result = analyzer.analyze_changes([make_change()])

    mock_client.chat.completions.create.assert_called_once()
    assert result == "OpenAI insight"


def test_openai_prompt_contains_competitor_name(openai_analyzer):
    analyzer, mock_client = openai_analyzer
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="ok"))
    ]

    analyzer.analyze_changes([make_change("Sovos - Homepage", "https://sovos.com")])

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    user_message = next(m["content"] for m in call_kwargs["messages"] if m["role"] == "user")
    assert "Sovos - Homepage" in user_message
    assert "https://sovos.com" in user_message


def test_openai_api_exception_returns_error_string(openai_analyzer):
    analyzer, mock_client = openai_analyzer
    mock_client.chat.completions.create.side_effect = Exception("quota exceeded")

    result = analyzer.analyze_changes([make_change()])

    assert "Error analyzing changes" in result
    assert "quota exceeded" in result
