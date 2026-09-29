"""
Local filesystem storage for raw logs.
Falls back to this when MinIO is not available.

Each event is its own file, written once under a path derived from its event ID
(see api/v1/ingestion.py) and never overwritten -- that's the append-only
property at this tier. Files are gzip-compressed, then optionally Fernet
-encrypted (see core/vault_encryption.py) on write. Reads handle three cases by
sniffing magic bytes: encrypted+gzip (current, if VAULT_ENCRYPTION_KEY is set),
gzip-only (current, if it isn't), and plaintext (legacy, pre-compression files).
"""
import os
import gzip

from app.core.vault_encryption import encrypt, decrypt


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw_logs")

GZIP_MAGIC = b"\x1f\x8b"


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def save_raw_log(raw_location: str, raw_log: str) -> str:
    """Save raw log to local filesystem: gzip-compressed, then encrypted at
    rest if VAULT_ENCRYPTION_KEY is configured. Returns the full path."""
    ensure_data_dir()
    full_path = os.path.join(DATA_DIR, raw_location)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    compressed = gzip.compress(raw_log.encode("utf-8"))
    with open(full_path, "wb") as f:
        f.write(encrypt(compressed))
    return full_path


def read_raw_log(raw_location: str) -> str:
    """Read raw log from local filesystem. Transparently handles encrypted,
    gzip-only, and legacy plaintext (pre-compression) files."""
    full_path = os.path.join(DATA_DIR, raw_location)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Raw log not found: {raw_location}")
    with open(full_path, "rb") as f:
        raw_bytes = f.read()
    raw_bytes = decrypt(raw_bytes)
    if raw_bytes[:2] == GZIP_MAGIC:
        return gzip.decompress(raw_bytes).decode("utf-8")
    return raw_bytes.decode("utf-8")


def delete_raw_log(raw_location: str) -> bool:
    """Deletes one raw log file (ULPF-master-prompt.md D10: retention).
    Returns False, not an error, if the file is already gone -- deletion is
    idempotent, matching a retention sweep that might be re-run. Never
    touches the Merkle leaf for this event (a hash, not content) -- the
    tree stays provable after the content it once hashed is deleted."""
    full_path = os.path.join(DATA_DIR, raw_location)
    if not os.path.exists(full_path):
        return False
    os.remove(full_path)
    return True


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
