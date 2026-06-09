"""
AI-powered competitive intelligence analysis for the competitor monitoring tool.
"""
import logging
from typing import List
from anthropic import Anthropic
from openai import OpenAI

from models import CompetitorChange
from typing import Dict

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are a competitive intelligence analyst monitoring competitor websites for strategic changes. "
    "Summarize the key changes in 2-3 concise sentences. For blog pages, list new blog post titles. "
    "Be specific and focus on what's new or different."
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
        """Analyze detected changes and generate insights (legacy method for backwards compatibility)."""
        change_analyses = self.analyze_changes_individually(changes)
        if not change_analyses:
            return "No changes detected in this monitoring cycle."

        # Format as a single report
        return "\n\n".join([
            f"**{change.name}**: {analysis}"
            for change, analysis in zip(changes, change_analyses.values())
        ])

    def analyze_changes_individually(self, changes: List[CompetitorChange]) -> Dict[str, str]:
        """Analyze each change individually and return a mapping of change name to analysis."""
        if not changes:
            return {}

        analyses = {}

        for change in changes:
            prompt = (
                f"A competitor page has been updated:\n\n"
                f"**Page**: {change.name}\n"
                f"**URL**: {change.url}\n"
                f"**Last checked**: {change.last_checked}\n\n"
                f"**Current content preview**:\n{change.content[:800]}...\n\n"
                f"Summarize what's new or changed on this page in 2-3 concise sentences."
            )

            try:
                if self.provider == "anthropic":
                    analysis = self._analyze_with_anthropic(prompt)
                elif self.provider == "openai":
                    analysis = self._analyze_with_openai(prompt)
                analyses[change.name] = analysis
                logger.info(f"Analyzed change for {change.name}")
            except Exception as e:
                logger.error(f"Error analyzing {change.name}: {e}")
                analyses[change.name] = f"Error analyzing changes: {str(e)}"

        return analyses

    def _analyze_with_anthropic(self, prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
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
