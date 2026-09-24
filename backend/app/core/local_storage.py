"""
Local filesystem storage for raw logs.
Falls back to this when MinIO is not available.
"""
import os
import io
from datetime import datetime, timezone


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw_logs")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def save_raw_log(raw_location: str, raw_log: str) -> str:
    """Save raw log to local filesystem. Returns the full path."""
    ensure_data_dir()
    full_path = os.path.join(DATA_DIR, raw_location)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(raw_log)
    return full_path


def read_raw_log(raw_location: str) -> str:
    """Read raw log from local filesystem."""
    full_path = os.path.join(DATA_DIR, raw_location)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Raw log not found: {raw_location}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def get_storage_size_bytes() -> int:
    """Get total size of raw log storage in bytes."""
    ensure_data_dir()
    total = 0
    for dirpath, dirnames, filenames in os.walk(DATA_DIR):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total += os.path.getsize(fp)
    return total


def get_file_count() -> int:
    """Count total files in raw log storage."""
    ensure_data_dir()
    count = 0
    for dirpath, dirnames, filenames in os.walk(DATA_DIR):
        count += len(filenames)
    return count
