"""
Tests for ConfigManager component
"""
import pytest
import tempfile
from pathlib import Path
import yaml
from src.config_manager import ConfigManager


@pytest.fixture
def config_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


_EMPTY_TARGETS = {"competitors": []}


def write_config(config_dir, config_data, targets_data=None):
    config_path = config_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    targets_path = config_dir / "targets.yml"
    with open(targets_path, "w") as f:
        yaml.dump(targets_data if targets_data is not None else _EMPTY_TARGETS, f)

    return config_path


MINIMAL_CONFIG = {
    "ai": {
        "provider": "anthropic",
        "anthropic": {"model": "claude-sonnet-4-5", "max_tokens": 2048},
        "openai": {"model": "gpt-4o", "max_tokens": 4096},
    },
    "monitoring": {
        "user_agent": "TestAgent/1.0",
        "timeout": 30,
        "check_interval": 24,
    },
    "email": {
        "from_email": "test@example.com",
        "from_name": "Test",
        "to_emails": ["a@example.com", "b@example.com"],
        "subject_prefix": "[Alert]",
    },
}


def test_get_ai_provider(config_dir):
    path = write_config(config_dir, MINIMAL_CONFIG)
    cm = ConfigManager(path)
    assert cm.get_ai_provider() == "anthropic"


def test_get_ai_config_anthropic(config_dir):
    path = write_config(config_dir, MINIMAL_CONFIG)
    cm = ConfigManager(path)
    cfg = cm.get_ai_config()
    assert cfg["provider"] == "anthropic"
    assert cfg["model"] == "claude-sonnet-4-5"
    assert cfg["max_tokens"] == 2048


def test_get_ai_config_openai(config_dir):
    data = {**MINIMAL_CONFIG, "ai": {**MINIMAL_CONFIG["ai"], "provider": "openai"}}
    path = write_config(config_dir, data)
    cm = ConfigManager(path)
    cfg = cm.get_ai_config()
    assert cfg["provider"] == "openai"
    assert cfg["model"] == "gpt-4o"
    assert cfg["max_tokens"] == 4096


def test_get_monitoring_config(config_dir):
    path = write_config(config_dir, MINIMAL_CONFIG)
    cm = ConfigManager(path)
    cfg = cm.get_monitoring_config()
    assert cfg["user_agent"] == "TestAgent/1.0"
    assert cfg["timeout"] == 30
    assert cfg["check_interval"] == 24
    assert cfg["snapshot_content_limit"] == 10000  # default when not set in config


def test_get_email_config(config_dir):
    path = write_config(config_dir, MINIMAL_CONFIG)
    cm = ConfigManager(path)
    cfg = cm.get_email_config()
    assert cfg["from_email"] == "test@example.com"
    assert cfg["from_name"] == "Test"
    assert cfg["to_emails"] == ["a@example.com", "b@example.com"]
    assert cfg["subject_prefix"] == "[Alert]"


def test_get_competitors_loads_targets(config_dir):
    targets = {
        "competitors": [
            {"name": "Acme - Home", "url": "https://acme.com", "requires_js": False},
            {"name": "Beta - Pricing", "url": "https://beta.com", "requires_js": True},
        ]
    }
    path = write_config(config_dir, MINIMAL_CONFIG, targets_data=targets)
    cm = ConfigManager(path)
    competitors = cm.get_competitors()
    assert len(competitors) == 2
    assert competitors[0]["name"] == "Acme - Home"
    assert competitors[1]["requires_js"] is True


def test_missing_required_key_raises(config_dir):
    bad_config = {"monitoring": MINIMAL_CONFIG["monitoring"]}  # no 'ai' key
    path = write_config(config_dir, bad_config)
    cm = ConfigManager(path)
    with pytest.raises(KeyError):
        cm.get_ai_provider()
