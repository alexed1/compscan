"""
Snapshot management and change detection for the competitor monitoring tool.
"""
import json
import hashlib
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


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
