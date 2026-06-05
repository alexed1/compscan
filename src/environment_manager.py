"""
Environment variable management for the competitor monitoring tool.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class EnvironmentManager:
    """Manages environment variable retrieval and validation."""

    @staticmethod
    def get_ai_api_key(provider: str) -> str:
        """
        Get API key for the specified AI provider.

        Args:
            provider: AI provider name ('anthropic' or 'openai')

        Returns:
            API key from environment variable

        Raises:
            ValueError: If provider is unknown or API key not set
        """
        key_map = {
            'anthropic': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY'
        }

        env_var = key_map.get(provider)
        if not env_var:
            raise ValueError(f"Unknown AI provider: {provider}. Must be 'anthropic' or 'openai'")

        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(f"{env_var} environment variable not set")

        return api_key

    @staticmethod
    def get_resend_api_key() -> str:
        """
        Get Resend API key from environment.

        Returns:
            Resend API key

        Raises:
            ValueError: If API key not set
        """
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            raise ValueError("RESEND_API_KEY environment variable not set")
        return api_key
