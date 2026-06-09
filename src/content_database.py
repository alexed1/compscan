"""
Content database for tracking all content ever seen on competitor pages.
This prevents false positives from rotating/cycling content.
"""
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, UTC
from typing import Set, List, Dict, Optional

logger = logging.getLogger(__name__)


class ContentDatabase:
    """Maintains a cumulative database of all content blocks seen for each target."""

    def __init__(self, db_dir: str = "content_db"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)

    def _get_db_path(self, target_name: str) -> Path:
        """Get the database file path for a target."""
        safe_name = target_name.lower().replace(' ', '_').replace('-', '_')
        return self.db_dir / f"{safe_name}.json"

    def _hash_content_block(self, text: str) -> str:
        """Create a hash for a content block."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def _split_into_blocks(self, content: str) -> List[str]:
        """
        Split content into logical blocks for tracking.
        Uses sentences/paragraphs as the unit of tracking.
        """
        # Split by newlines first
        lines = [line.strip() for line in content.split('\n') if line.strip()]

        # Filter out very short lines (likely navigation/UI elements)
        # Use 30 char minimum to catch meaningful content blocks
        meaningful_lines = [line for line in lines if len(line) > 30]

        return meaningful_lines

    def load_content_history(self, target_name: str) -> Dict[str, Dict]:
        """
        Load the content history for a target.
        Returns dict mapping content_hash -> metadata (first_seen, last_seen, text_preview)
        """
        db_path = self._get_db_path(target_name)

        if not db_path.exists():
            return {}

        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading content database for {target_name}: {e}")
            return {}

    def save_content_history(self, target_name: str, content_history: Dict[str, Dict]):
        """Save the content history for a target."""
        db_path = self._get_db_path(target_name)

        try:
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump(content_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving content database for {target_name}: {e}")

    def update_and_find_new_content(self, target_name: str, current_content: str) -> List[str]:
        """
        Update the content database with current content and return truly new content blocks.

        Args:
            target_name: Name of the competitor target
            current_content: Current scraped content

        Returns:
            List of content blocks that have never been seen before
        """
        # Load existing content history
        content_history = self.load_content_history(target_name)

        # Split current content into blocks
        current_blocks = self._split_into_blocks(current_content)

        # Track new content
        new_blocks = []
        now = datetime.now(UTC).isoformat()

        for block in current_blocks:
            block_hash = self._hash_content_block(block)

            if block_hash not in content_history:
                # This is truly new content - never seen before
                new_blocks.append(block)
                content_history[block_hash] = {
                    'first_seen': now,
                    'last_seen': now,
                    'text_preview': block[:200] + '...' if len(block) > 200 else block
                }
                logger.info(f"New content block found for {target_name}: {block[:100]}...")
            else:
                # Content seen before, just update last_seen timestamp
                content_history[block_hash]['last_seen'] = now

        # Save updated history
        self.save_content_history(target_name, content_history)

        logger.info(f"{target_name}: {len(new_blocks)} new blocks out of {len(current_blocks)} total blocks")

        return new_blocks

    def get_statistics(self, target_name: str) -> Dict:
        """Get statistics about tracked content for a target."""
        content_history = self.load_content_history(target_name)

        if not content_history:
            return {'total_blocks': 0}

        first_seen_dates = [item['first_seen'] for item in content_history.values()]
        last_seen_dates = [item['last_seen'] for item in content_history.values()]

        return {
            'total_blocks': len(content_history),
            'earliest_content': min(first_seen_dates) if first_seen_dates else None,
            'latest_update': max(last_seen_dates) if last_seen_dates else None
        }
