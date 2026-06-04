#!/usr/bin/env python3
"""
Competitor Website Monitoring Tool
Scrapes competitor websites, detects changes, analyzes with AI, and sends email alerts.
"""

import json
import hashlib
import asyncio
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import httpx
from playwright.async_api import async_playwright
from anthropic import Anthropic
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import resend
import markdown

from config_manager import ConfigManager
from environment_manager import EnvironmentManager
from models import CompetitorChange

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebScraper:
    """Handles web scraping with httpx and Playwright fallback."""

    def __init__(self, user_agent: str, timeout: int):
        self.user_agent = user_agent
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    async def scrape_with_httpx(self, url: str) -> Optional[str]:
        """Scrape a URL using httpx (for static pages) with retry logic."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning(f"httpx scraping failed for {url}: {e}")
            return None

    async def scrape_with_playwright(self, url: str) -> Optional[str]:
        """Scrape a URL using Playwright (for JS-rendered pages)."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.user_agent)
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
                content = await page.content()

                await browser.close()
                return content
        except Exception as e:
            logger.error(f"Playwright scraping failed for {url}: {e}")
            return None

    async def scrape(self, url: str, requires_js: bool = False) -> Optional[str]:
        """Scrape a URL, using appropriate method based on JS requirement."""
        if requires_js:
            logger.info(f"Scraping {url} with Playwright (JS required)...")
            return await self.scrape_with_playwright(url)

        logger.info(f"Scraping {url} with httpx...")
        content = await self.scrape_with_httpx(url)

        # Fallback to Playwright if httpx fails
        if content is None:
            logger.info(f"Falling back to Playwright for {url}...")
            content = await self.scrape_with_playwright(url)

        return content


class SnapshotManager:
    """Manages snapshots and detects changes using hash comparison."""

    def __init__(self, snapshots_dir: Path):
        self.snapshots_dir = snapshots_dir
        self.snapshots_dir.mkdir(exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        """Convert competitor name to safe filename."""
        return "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in name).lower()

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _get_snapshot_path(self, competitor_name: str) -> Path:
        """Get path to snapshot file for a competitor."""
        safe_name = self._sanitize_name(competitor_name)
        return self.snapshots_dir / f"{safe_name}.json"

    def load_snapshot(self, competitor_name: str) -> Optional[Dict]:
        """Load existing snapshot for a competitor."""
        snapshot_path = self._get_snapshot_path(competitor_name)
        if snapshot_path.exists():
            try:
                with open(snapshot_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading snapshot for {competitor_name}: {e}")
        return None

    def save_snapshot(self, competitor_name: str, url: str, content: str, content_hash: str):
        """Save new snapshot for a competitor."""
        snapshot_path = self._get_snapshot_path(competitor_name)
        now = datetime.now(UTC)
        snapshot = {
            "name": competitor_name,
            "url": url,
            "timestamp": now.isoformat(),
            "timestamp_human": now.strftime("%B %d, %Y at %I:%M %p UTC"),
            "content_hash": content_hash,
            "content": content[:10000]  # Store first 10k chars for reference
        }

        with open(snapshot_path, 'w') as f:
            json.dump(snapshot, f, indent=2)

    def detect_change(self, competitor_name: str, url: str, content: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if content has changed since last snapshot.
        Returns (has_changed, old_hash).
        """
        content_hash = self._compute_hash(content)
        old_snapshot = self.load_snapshot(competitor_name)

        if old_snapshot is None:
            logger.info(f"No previous snapshot found for {competitor_name} - treating as new")
            self.save_snapshot(competitor_name, url, content, content_hash)
            return True, None

        old_hash = old_snapshot.get("content_hash")
        has_changed = content_hash != old_hash

        if has_changed:
            logger.info(f"Change detected for {competitor_name}!")
            self.save_snapshot(competitor_name, url, content, content_hash)
        else:
            logger.debug(f"No change detected for {competitor_name}")

        return has_changed, old_hash


class CompetitiveIntelligenceAnalyzer:
    """Analyzes changes using AI (Anthropic or OpenAI)."""

    def __init__(self, provider: str, api_key: str, model: str, max_tokens: int):
        self.provider = provider.lower()
        self.model = model
        self.max_tokens = max_tokens

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

        # Prepare summary of changes for analysis
        changes_summary = "\n\n".join([
            f"**{change.name}** ({change.url})\n"
            f"Last checked: {change.last_checked}\n"
            f"Content preview: {change.content[:500]}..."
            for change in changes
        ])

        prompt = f"""You are a competitive intelligence analyst monitoring competitor websites for strategic changes.

The following competitor websites have been updated since the last check:

{changes_summary}

For each, change, summarize what has changed. The goal is to empahsize signficant new developments, like a product announcement. New 
blog posts should be summarized. 
Please analyze these changes and provide:
"""

        try:
            if self.provider == "anthropic":
                return self._analyze_with_anthropic(prompt)
            elif self.provider == "openai":
                return self._analyze_with_openai(prompt)
        except Exception as e:
            logger.error(f"Error calling {self.provider.title()} API: {e}")
            return f"Error analyzing changes: {str(e)}"

    def _analyze_with_anthropic(self, prompt: str) -> str:
        """Analyze using Anthropic Claude."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def _analyze_with_openai(self, prompt: str) -> str:
        """Analyze using OpenAI GPT."""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": "You are a competitive intelligence analyst monitoring competitor websites for strategic changes."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content


class EmailReporter:
    """Sends HTML email digests via Resend."""

    def __init__(self, api_key: str, from_email: str, from_name: str, to_emails: List[str]):
        resend.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.to_emails = to_emails

    def _generate_changes_table(self, changes: List[CompetitorChange]) -> str:
        """Generate HTML table for detected changes."""
        changes_rows = ""
        for change in changes:
            changes_rows += f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{change.company_name}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{change.page_name}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                        <a href="{change.url}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: none;">
                            View Page →
                        </a>
                    </td>
                </tr>
            """

        return f"""
        <table style="width: 100%; border-collapse: collapse; background-color: white; border: 1px solid #e5e7eb; margin: 15px 0;">
            <thead>
                <tr style="background-color: #f9fafb;">
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #1e40af; font-weight: 600;">Company</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #1e40af; font-weight: 600;">Page</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #1e40af; font-weight: 600;">URL</th>
                </tr>
            </thead>
            <tbody>
                {changes_rows}
            </tbody>
        </table>
        """

    def _generate_email_styles(self) -> str:
        """Generate CSS styles for email."""
        return """
            <style>
                .analysis-content h2 {
                    color: #1e40af;
                    font-size: 1.25em;
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                }
                .analysis-content h3 {
                    color: #1f2937;
                    font-size: 1.1em;
                    margin-top: 1em;
                    margin-bottom: 0.5em;
                }
                .analysis-content ul, .analysis-content ol {
                    margin: 0.5em 0;
                    padding-left: 1.5em;
                }
                .analysis-content li {
                    margin: 0.25em 0;
                }
                .analysis-content p {
                    margin: 0.75em 0;
                }
                .analysis-content strong {
                    color: #1f2937;
                    font-weight: 600;
                }
            </style>
        """

    def _generate_html_digest(self, changes: List[CompetitorChange], analysis: str, timestamp: str) -> str:
        """Generate HTML email digest."""
        changes_table = self._generate_changes_table(changes)
        styles = self._generate_email_styles()

        # Convert markdown analysis to HTML
        analysis_html = markdown.markdown(
            analysis,
            extensions=['extra', 'nl2br', 'sane_lists']
        )

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            {styles}
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">Competitor Intelligence Report</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">{timestamp}</p>
            </div>

            <div style="background-color: white; padding: 20px; border: 1px solid #e5e7eb; border-top: none;">
                <h2 style="color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
                    Changes Detected: {len(changes)}
                </h2>

                {changes_table}

                <h2 style="color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-top: 30px;">
                    AI Analysis & Insights
                </h2>

                <div class="analysis-content" style="background-color: #f0f9ff; padding: 15px; border-radius: 8px;">
{analysis_html}
                </div>

                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 14px;">
                    <p>Generated by Competitor Monitoring Tool</p>
                    <p>Powered by AI</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def send_digest(self, changes: List[CompetitorChange], analysis: str, subject_prefix: str) -> bool:
        """Send email digest with changes and analysis."""
        if not changes:
            logger.info("No changes to report, skipping email")
            return True

        now = datetime.now(UTC)
        timestamp = now.strftime("%B %d, %Y at %I:%M %p UTC")
        timestamp_short = now.strftime("%b %d, %Y")
        html_content = self._generate_html_digest(changes, analysis, timestamp)
        subject = f"{subject_prefix} {len(changes)} change(s) detected - {timestamp_short}"

        try:
            for to_email in self.to_emails:
                params = {
                    "from": f"{self.from_name} <{self.from_email}>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content
                }

                resend.Emails.send(params)
                logger.info(f"Email sent successfully to {to_email}")

            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False


async def main():
    """Main monitoring function."""
    logger.info(f"Starting competitor monitoring at {datetime.now(UTC).isoformat()}")

    # Load configuration using ConfigManager
    config_path = Path(__file__).parent.parent / "config.yaml"
    config_manager = ConfigManager(config_path)

    # Get API keys using EnvironmentManager
    ai_provider = config_manager.get_ai_provider()
    ai_api_key = EnvironmentManager.get_ai_api_key(ai_provider)
    resend_api_key = EnvironmentManager.get_resend_api_key()

    # Get configuration
    ai_config = config_manager.get_ai_config()
    monitoring_config = config_manager.get_monitoring_config()
    email_config = config_manager.get_email_config()

    logger.info(f"Using AI provider: {ai_provider.title()} ({ai_config['model']})")

    # Initialize components
    snapshots_dir = Path(__file__).parent.parent / "snapshots"
    scraper = WebScraper(
        user_agent=monitoring_config['user_agent'],
        timeout=monitoring_config['timeout']
    )
    snapshot_manager = SnapshotManager(snapshots_dir)
    analyzer = CompetitiveIntelligenceAnalyzer(
        provider=ai_config['provider'],
        api_key=ai_api_key,
        model=ai_config['model'],
        max_tokens=ai_config['max_tokens']
    )
    reporter = EmailReporter(
        api_key=resend_api_key,
        from_email=email_config['from_email'],
        from_name=email_config['from_name'],
        to_emails=email_config['to_emails']
    )

    # Monitor each competitor
    changes: List[CompetitorChange] = []
    for competitor in config_manager.get_competitors():
        name = competitor['name']
        url = competitor['url']
        requires_js = competitor.get('requires_js', False)

        logger.info(f"\n{'='*60}")
        logger.info(f"Monitoring: {name}")
        logger.info(f"{'='*60}")

        # Scrape the website
        content = await scraper.scrape(url, requires_js)

        if content is None:
            logger.warning(f"Failed to scrape {name}, skipping...")
            continue

        # Detect changes
        has_changed, old_hash = snapshot_manager.detect_change(name, url, content)

        if has_changed:
            old_snapshot = snapshot_manager.load_snapshot(name)
            # Use human-readable timestamp if available, otherwise fall back to ISO timestamp
            last_checked = 'Never'
            if old_snapshot:
                last_checked = old_snapshot.get('timestamp_human', old_snapshot.get('timestamp', 'Never'))

            change = CompetitorChange(
                name=name,
                url=url,
                content=content,
                last_checked=last_checked
            )
            changes.append(change)

    # Analyze changes with AI
    logger.info(f"\n{'='*60}")
    logger.info(f"Analyzing changes with AI...")
    logger.info(f"{'='*60}")
    analysis = analyzer.analyze_changes(changes)
    logger.info(f"\nAnalysis:\n{analysis}\n")

    # Send email digest
    logger.info(f"\n{'='*60}")
    logger.info(f"Sending email digest...")
    logger.info(f"{'='*60}")
    reporter.send_digest(changes, analysis, email_config['subject_prefix'])

    logger.info(f"\nMonitoring complete at {datetime.now(UTC).isoformat()}")
    logger.info(f"Total changes detected: {len(changes)}")


if __name__ == "__main__":
    asyncio.run(main())
