"""
AI-powered competitive intelligence analysis for the competitor monitoring tool.
"""
import logging
from typing import List
from anthropic import Anthropic
from openai import OpenAI

from models import CompetitorChange

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are a competitive intelligence analyst monitoring competitor websites for strategic changes. "
    "For each changed page, summarize the new or changed content compared to the previous version of the page. "
    "For blog pages, create a list of new blog posts with their titles."
)


class CompetitiveIntelligenceAnalyzer:
    """Analyzes changes using AI (Anthropic or OpenAI)."""

    def __init__(self, provider: str, api_key: str, model: str, max_tokens: int,
                 system_prompt: str = ""):
        self.provider = provider.lower()
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt.strip() or _DEFAULT_SYSTEM_PROMPT

        if self.provider == "anthropic":
            self.client = Anthropic(api_key=api_key)
        elif self.provider == "openai":
            self.client = OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}. Use 'anthropic' or 'openai'.")

    def analyze_changes(self, changes: List[CompetitorChange]) -> str:
        """Analyze detected changes and generate insights."""
        if not changes:
            return "No changes detected in this monitoring cycle."

        changes_summary = "\n\n".join([
            f"**{change.name}** ({change.url})\n"
            f"Last checked: {change.last_checked}\n"
            f"Content preview: {change.content[:500]}..."
            for change in changes
        ])

        prompt = (
            f"{self.system_prompt}\n\n"
            f"The following competitor websites have been updated since the last check:\n\n"
            f"{changes_summary}"
        )

        try:
            if self.provider == "anthropic":
                return self._analyze_with_anthropic(prompt)
            elif self.provider == "openai":
                return self._analyze_with_openai(prompt)
        except Exception as e:
            logger.error(f"Error calling {self.provider.title()} API: {e}")
            return f"Error analyzing changes: {str(e)}"

    def _analyze_with_anthropic(self, prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def _analyze_with_openai(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
