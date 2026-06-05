"""
Tests for environment_manager module
"""
import pytest
from unittest.mock import patch
import src.environment_manager as em


def test_get_ai_api_key_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    assert em.get_ai_api_key("anthropic") == "test-anthropic-key"


def test_get_ai_api_key_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    assert em.get_ai_api_key("openai") == "test-openai-key"


def test_get_ai_api_key_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown AI provider"):
        em.get_ai_api_key("gemini")


def test_get_ai_api_key_missing_env_var_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        em.get_ai_api_key("anthropic")


def test_get_resend_api_key(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    assert em.get_resend_api_key() == "test-resend-key"


def test_get_resend_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        em.get_resend_api_key()
