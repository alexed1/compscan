"""
Tests for SnapshotManager component
"""
import pytest
import json
import tempfile
from pathlib import Path
from src.snapshot_manager import SnapshotManager


@pytest.fixture
def temp_snapshots_dir():
    """Create a temporary directory for snapshots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def snapshot_manager(temp_snapshots_dir):
    """Create a SnapshotManager instance for testing."""
    return SnapshotManager(temp_snapshots_dir)


def test_sanitize_name(snapshot_manager):
    """Test name sanitization for filenames."""
    assert snapshot_manager._sanitize_name("Competitor A - Homepage") == "competitor_a_-_homepage"
    assert snapshot_manager._sanitize_name("Test/Name:123") == "test_name_123"
    assert snapshot_manager._sanitize_name("Normal_Name-123") == "normal_name-123"


def test_compute_hash(snapshot_manager):
    """Test content hash computation."""
    content1 = "Test content"
    content2 = "Different content"

    hash1 = snapshot_manager._compute_hash(content1)
    hash2 = snapshot_manager._compute_hash(content2)

    # Same content should produce same hash
    assert hash1 == snapshot_manager._compute_hash(content1)

    # Different content should produce different hash
    assert hash1 != hash2

    # Hash should be SHA-256 (64 hex characters)
    assert len(hash1) == 64
    assert all(c in '0123456789abcdef' for c in hash1)


def test_save_and_load_snapshot(snapshot_manager):
    """Test saving and loading snapshots."""
    competitor_name = "Test Competitor"
    url = "https://example.com"
    content = "<html><body>Test</body></html>"
    content_hash = snapshot_manager._compute_hash(content)

    # Save snapshot
    snapshot_manager.save_snapshot(competitor_name, url, content, content_hash)

    # Load snapshot
    loaded = snapshot_manager.load_snapshot(competitor_name)

    assert loaded is not None
    assert loaded['name'] == competitor_name
    assert loaded['url'] == url
    assert loaded['content_hash'] == content_hash
    assert loaded['content'] == content  # Content is small, so it's fully stored
    assert 'timestamp' in loaded


def test_load_nonexistent_snapshot(snapshot_manager):
    """Test loading a snapshot that doesn't exist."""
    loaded = snapshot_manager.load_snapshot("Nonexistent Competitor")
    assert loaded is None


def test_save_large_content(snapshot_manager):
    """Test that large content is truncated to content_limit chars."""
    competitor_name = "Large Content Test"
    url = "https://example.com"
    limit = snapshot_manager.content_limit
    content = "x" * (limit * 2)
    content_hash = snapshot_manager._compute_hash(content)

    snapshot_manager.save_snapshot(competitor_name, url, content, content_hash)
    loaded = snapshot_manager.load_snapshot(competitor_name)

    assert len(loaded['content']) == limit
    assert loaded['content'] == "x" * limit


def test_detect_change_first_run(snapshot_manager):
    """Test change detection on first run (no previous snapshot)."""
    competitor_name = "New Competitor"
    url = "https://example.com"
    content = "<html><body>New</body></html>"

    has_changed, old_hash = snapshot_manager.detect_change(competitor_name, url, content)

    assert has_changed is True
    assert old_hash is None

    # Verify snapshot was created
    loaded = snapshot_manager.load_snapshot(competitor_name)
    assert loaded is not None


def test_detect_change_no_change(snapshot_manager):
    """Test change detection when content hasn't changed."""
    competitor_name = "Stable Competitor"
    url = "https://example.com"
    content = "<html><body>Same content</body></html>"

    # First run
    snapshot_manager.detect_change(competitor_name, url, content)

    # Second run with same content
    has_changed, old_hash = snapshot_manager.detect_change(competitor_name, url, content)

    assert has_changed is False
    assert old_hash is not None


def test_detect_change_with_change(snapshot_manager):
    """Test change detection when content has changed."""
    competitor_name = "Changing Competitor"
    url = "https://example.com"
    old_content = "<html><body>Old content</body></html>"
    new_content = "<html><body>New content</body></html>"

    # First run
    snapshot_manager.detect_change(competitor_name, url, old_content)

    # Second run with different content
    has_changed, old_hash = snapshot_manager.detect_change(competitor_name, url, new_content)

    assert has_changed is True
    assert old_hash is not None

    # Verify new snapshot was saved
    loaded = snapshot_manager.load_snapshot(competitor_name)
    assert snapshot_manager._compute_hash(new_content) == loaded['content_hash']


def test_get_snapshot_path(snapshot_manager):
    """Test snapshot path generation."""
    path = snapshot_manager._get_snapshot_path("Test Competitor")

    assert path.parent == snapshot_manager.snapshots_dir
    assert path.name == "test_competitor.json"
    assert path.suffix == ".json"


def test_load_snapshot_handles_corrupt_json(snapshot_manager):
    """load_snapshot returns None and does not raise on malformed JSON."""
    path = snapshot_manager._get_snapshot_path("Corrupt Competitor")
    path.write_text("{ this is not valid json }")

    result = snapshot_manager.load_snapshot("Corrupt Competitor")
    assert result is None


def test_detect_change_returns_previous_timestamp(snapshot_manager):
    """Second detect_change call returns the timestamp from the first snapshot."""
    name, url = "Timestamped Co - Home", "https://example.com"
    snapshot_manager.detect_change(name, url, "first content")

    has_changed, timestamp = snapshot_manager.detect_change(name, url, "second content")

    assert has_changed is True
    assert timestamp is not None
    assert "UTC" in timestamp  # timestamp_human format contains "UTC"


def test_custom_content_limit_respected(temp_snapshots_dir):
    """SnapshotManager honours a non-default content_limit."""
    sm = SnapshotManager(temp_snapshots_dir, content_limit=100)
    content = "a" * 300
    sm.save_snapshot("Limit Test", "https://example.com", content, sm._compute_hash(content))
    loaded = sm.load_snapshot("Limit Test")
    assert len(loaded["content"]) == 100


def test_save_snapshot_timestamp_human_format(snapshot_manager):
    """Saved snapshot includes a timestamp_human in the expected readable format."""
    import re
    snapshot_manager.save_snapshot("Ts Test", "https://example.com", "content", "abc123")
    loaded = snapshot_manager.load_snapshot("Ts Test")
    ts = loaded["timestamp_human"]
    # e.g. "June 05, 2026 at 03:15 AM UTC"
    assert re.match(r"\w+ \d{2}, \d{4} at \d{2}:\d{2} [AP]M UTC", ts), f"Unexpected format: {ts}"
