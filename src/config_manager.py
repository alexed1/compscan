"""
Configuration management for the competitor monitoring tool.
"""
from pathlib import Path
from typing import Any, Dict, List
import yaml


class ConfigManager:
    """Manages configuration loading and validation."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_yaml(config_path)
        self._competitors = self._load_yaml(config_path.parent / "targets.yml")['competitors']

    def _load_yaml(self, path: Path) -> dict:
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def get_ai_provider(self) -> str:
        """Get configured AI provider name."""
        return self.config['ai']['provider'].lower()

    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI provider configuration."""
        provider = self.get_ai_provider()
        return {
            'provider': provider,
            'model': self.config['ai'][provider]['model'],
            'max_tokens': self.config['ai'][provider]['max_tokens'],
            'system_prompt': self.config['ai'].get('system_prompt', ''),
        }

    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring settings."""
        return {
            'user_agent': self.config['monitoring']['user_agent'],
            'timeout': self.config['monitoring']['timeout'],
            'check_interval': self.config['monitoring']['check_interval'],
            'snapshot_content_limit': self.config['monitoring'].get('snapshot_content_limit', 10000),
        }

    def get_email_config(self) -> Dict[str, Any]:
        """Get email configuration."""
        return {
            'from_email': self.config['email']['from_email'],
            'from_name': self.config['email']['from_name'],
            'to_emails': self.config['email']['to_emails'],
            'subject_prefix': self.config['email']['subject_prefix']
        }

    def get_competitors(self) -> List[Dict[str, Any]]:
        """Get list of competitors to monitor."""
        return self._competitors
