#!/usr/bin/env python3
"""
Competitor Website Monitoring Tool
Scrapes competitor websites, detects changes, analyzes with AI, and sends email alerts.
"""

import asyncio
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import List

from config_manager import ConfigManager
from environment_manager import EnvironmentManager
from models import CompetitorChange
from scraper import WebScraper
from snapshot_manager import SnapshotManager
from analyzer import CompetitiveIntelligenceAnalyzer
from email_reporter import EmailReporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
