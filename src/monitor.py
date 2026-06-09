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
from environment_manager import get_ai_api_key, get_resend_api_key
from models import CompetitorChange
from scraper import WebScraper
from snapshot_manager import SnapshotManager
from analyzer import CompetitiveIntelligenceAnalyzer
from email_reporter import EmailReporter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main monitoring function."""
    logger.info(f"Starting competitor monitoring at {datetime.now(UTC).isoformat()}")

    config_path = Path(__file__).parent.parent / "config.yaml"
    config_manager = ConfigManager(config_path)

    ai_provider = config_manager.get_ai_provider()
    ai_api_key = get_ai_api_key(ai_provider)
    resend_api_key = get_resend_api_key()

    ai_config = config_manager.get_ai_config()
    monitoring_config = config_manager.get_monitoring_config()
    email_config = config_manager.get_email_config()

    logger.info(f"Using AI provider: {ai_provider.title()} ({ai_config['model']})")

    snapshots_dir = Path(__file__).parent.parent / "snapshots"
    scraper = WebScraper(
        user_agent=monitoring_config['user_agent'],
        timeout=monitoring_config['timeout']
    )
    snapshot_manager = SnapshotManager(
        snapshots_dir,
        content_limit=monitoring_config['snapshot_content_limit'],
    )
    analyzer = CompetitiveIntelligenceAnalyzer(
        provider=ai_config['provider'],
        api_key=ai_api_key,
        model=ai_config['model'],
        max_tokens=ai_config['max_tokens'],
        system_prompt=ai_config.get('system_prompt', ''),
    )
    reporter = EmailReporter(
        api_key=resend_api_key,
        from_email=email_config['from_email'],
        from_name=email_config['from_name'],
        to_emails=email_config['to_emails']
    )

    changes: List[CompetitorChange] = []
    for competitor in config_manager.get_competitors():
        name = competitor['name']
        url = competitor['url']
        requires_js = competitor.get('requires_js', False)

        logger.info(f"\n{'='*60}")
        logger.info(f"Monitoring: {name}")
        logger.info(f"{'='*60}")

        content = await scraper.scrape(url, requires_js)

        if content is None:
            logger.warning(f"Failed to scrape {name}, skipping...")
            continue

        has_changed, previous_timestamp = snapshot_manager.detect_change(name, url, content)

        if has_changed:
            change = CompetitorChange(
                name=name,
                url=url,
                content=content,
                last_checked=previous_timestamp or 'Never'
            )
            changes.append(change)

    logger.info(f"\n{'='*60}")
    logger.info("Analyzing changes with AI...")
    logger.info(f"{'='*60}")
    change_analyses = analyzer.analyze_changes_individually(changes)
    for name, analysis in change_analyses.items():
        logger.info(f"\n{name}:\n{analysis}\n")

    logger.info(f"\n{'='*60}")
    logger.info("Sending email digest...")
    logger.info(f"{'='*60}")
    reporter.send_digest(changes, change_analyses, email_config['subject_prefix'])

    logger.info(f"\nMonitoring complete at {datetime.now(UTC).isoformat()}")
    logger.info(f"Total changes detected: {len(changes)}")


if __name__ == "__main__":
    asyncio.run(main())
