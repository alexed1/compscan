"""
Environment variable management for the competitor monitoring tool.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

_AI_KEY_MAP = {
    'anthropic': 'ANTHROPIC_API_KEY',
    'openai': 'OPENAI_API_KEY',
}


def get_ai_api_key(provider: str) -> str:
    env_var = _AI_KEY_MAP.get(provider)
    if not env_var:
        raise ValueError(f"Unknown AI provider: {provider}. Must be 'anthropic' or 'openai'")
    api_key = os.getenv(env_var)
    if not api_key:
        raise ValueError(f"{env_var} environment variable not set")
    return api_key


def get_resend_api_key() -> str:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise ValueError("RESEND_API_KEY environment variable not set")
    return api_key
