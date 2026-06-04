#!/usr/bin/env python3
"""
Competitor Website Monitoring Tool
Scrapes competitor websites, detects changes, analyzes with AI, and sends email alerts.
"""

import os
import json
import hashlib
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml
import httpx
from playwright.async_api import async_playwright
from anthropic import Anthropic
import resend


class WebScraper:
    """Handles web scraping with httpx and Playwright fallback."""

    def __init__(self, user_agent: str, timeout: int):
        self.user_agent = user_agent
        self.timeout = timeout

    async def scrape_with_httpx(self, url: str) -> Optional[str]:
        """Scrape a URL using httpx (for static pages)."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                return response.text
        except Exception as e:
            print(f"httpx scraping failed for {url}: {e}")
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
            print(f"Playwright scraping failed for {url}: {e}")
            return None

    async def scrape(self, url: str, requires_js: bool = False) -> Optional[str]:
        """Scrape a URL, using appropriate method based on JS requirement."""
        if requires_js:
            print(f"Scraping {url} with Playwright (JS required)...")
            return await self.scrape_with_playwright(url)

        print(f"Scraping {url} with httpx...")
        content = await self.scrape_with_httpx(url)

        # Fallback to Playwright if httpx fails
        if content is None:
            print(f"Falling back to Playwright for {url}...")
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
                print(f"Error loading snapshot for {competitor_name}: {e}")
        return None

    def save_snapshot(self, competitor_name: str, url: str, content: str, content_hash: str):
        """Save new snapshot for a competitor."""
        snapshot_path = self._get_snapshot_path(competitor_name)
        snapshot = {
            "name": competitor_name,
            "url": url,
            "timestamp": datetime.utcnow().isoformat(),
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
            print(f"No previous snapshot found for {competitor_name} - treating as new")
            self.save_snapshot(competitor_name, url, content, content_hash)
            return True, None

        old_hash = old_snapshot.get("content_hash")
        has_changed = content_hash != old_hash

        if has_changed:
            print(f"Change detected for {competitor_name}!")
            self.save_snapshot(competitor_name, url, content, content_hash)
        else:
            print(f"No change detected for {competitor_name}")

        return has_changed, old_hash


class CompetitiveIntelligenceAnalyzer:
    """Analyzes changes using Anthropic API."""

    def __init__(self, api_key: str, model: str, max_tokens: int):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def analyze_changes(self, changes: List[Dict]) -> str:
        """Analyze detected changes and generate insights."""
        if not changes:
            return "No changes detected in this monitoring cycle."

        # Prepare summary of changes for analysis
        changes_summary = "\n\n".join([
            f"**{change['name']}** ({change['url']})\n"
            f"Last checked: {change.get('last_checked', 'Never')}\n"
            f"Content preview: {change['content'][:500]}..."
            for change in changes
        ])

        prompt = f"""You are a competitive intelligence analyst monitoring competitor websites for strategic changes.

The following competitor websites have been updated since the last check:

{changes_summary}

Please analyze these changes and provide:
1. A brief executive summary of the most important changes
2. Key insights about what these changes might indicate (new features, pricing changes, market positioning, etc.)
3. Potential competitive implications for our business
4. Recommended actions or areas to investigate further

Focus on actionable intelligence rather than just describing what changed."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

            return message.content[0].text
        except Exception as e:
            print(f"Error calling Anthropic API: {e}")
            return f"Error analyzing changes: {str(e)}"


class EmailReporter:
    """Sends HTML email digests via Resend."""

    def __init__(self, api_key: str, from_email: str, from_name: str, to_emails: List[str]):
        resend.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.to_emails = to_emails

    def _generate_html_digest(self, changes: List[Dict], analysis: str, timestamp: str) -> str:
        """Generate HTML email digest."""
        changes_html = ""
        for change in changes:
            changes_html += f"""
            <div style="margin-bottom: 20px; padding: 15px; background-color: #f5f5f5; border-left: 4px solid #2563eb;">
                <h3 style="margin-top: 0; color: #1e40af;">{change['name']}</h3>
                <p style="margin: 5px 0;"><strong>URL:</strong> <a href="{change['url']}">{change['url']}</a></p>
                <p style="margin: 5px 0;"><strong>Last Checked:</strong> {change.get('last_checked', 'Never')}</p>
                <p style="margin: 5px 0;"><strong>Status:</strong> <span style="color: #dc2626;">Changed</span></p>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
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

                {changes_html}

                <h2 style="color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-top: 30px;">
                    AI Analysis & Insights
                </h2>

                <div style="background-color: #f0f9ff; padding: 15px; border-radius: 8px; white-space: pre-wrap;">
{analysis}
                </div>

                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 14px;">
                    <p>Generated by Competitor Monitoring Tool</p>
                    <p>Powered by Claude AI</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def send_digest(self, changes: List[Dict], analysis: str, subject_prefix: str) -> bool:
        """Send email digest with changes and analysis."""
        if not changes:
            print("No changes to report, skipping email")
            return True

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        html_content = self._generate_html_digest(changes, analysis, timestamp)
        subject = f"{subject_prefix} {len(changes)} change(s) detected - {timestamp}"

        try:
            for to_email in self.to_emails:
                params = {
                    "from": f"{self.from_name} <{self.from_email}>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content
                }

                resend.Emails.send(params)
                print(f"Email sent successfully to {to_email}")

            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False


async def main():
    """Main monitoring function."""
    print(f"Starting competitor monitoring at {datetime.utcnow().isoformat()}")

    # Load configuration
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Get API keys from environment
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    resend_api_key = os.getenv("RESEND_API_KEY")

    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    if not resend_api_key:
        raise ValueError("RESEND_API_KEY environment variable not set")

    # Initialize components
    snapshots_dir = Path(__file__).parent.parent / "snapshots"
    scraper = WebScraper(
        user_agent=config['monitoring']['user_agent'],
        timeout=config['monitoring']['timeout']
    )
    snapshot_manager = SnapshotManager(snapshots_dir)
    analyzer = CompetitiveIntelligenceAnalyzer(
        api_key=anthropic_api_key,
        model=config['anthropic']['model'],
        max_tokens=config['anthropic']['max_tokens']
    )
    reporter = EmailReporter(
        api_key=resend_api_key,
        from_email=config['email']['from_email'],
        from_name=config['email']['from_name'],
        to_emails=config['email']['to_emails']
    )

    # Monitor each competitor
    changes = []
    for competitor in config['competitors']:
        name = competitor['name']
        url = competitor['url']
        requires_js = competitor.get('requires_js', False)

        print(f"\n{'='*60}")
        print(f"Monitoring: {name}")
        print(f"{'='*60}")

        # Scrape the website
        content = await scraper.scrape(url, requires_js)

        if content is None:
            print(f"Failed to scrape {name}, skipping...")
            continue

        # Detect changes
        has_changed, old_hash = snapshot_manager.detect_change(name, url, content)

        if has_changed:
            old_snapshot = snapshot_manager.load_snapshot(name)
            changes.append({
                "name": name,
                "url": url,
                "content": content,
                "last_checked": old_snapshot.get('timestamp', 'Never') if old_snapshot else 'Never'
            })

    # Analyze changes with AI
    print(f"\n{'='*60}")
    print(f"Analyzing changes with Claude AI...")
    print(f"{'='*60}")
    analysis = analyzer.analyze_changes(changes)
    print(f"\nAnalysis:\n{analysis}\n")

    # Send email digest
    print(f"\n{'='*60}")
    print(f"Sending email digest...")
    print(f"{'='*60}")
    reporter.send_digest(changes, analysis, config['email']['subject_prefix'])

    print(f"\nMonitoring complete at {datetime.utcnow().isoformat()}")
    print(f"Total changes detected: {len(changes)}")


if __name__ == "__main__":
    asyncio.run(main())
