"""At-rest encryption for the raw-log vault, layered on top of gzip compression.

Optional and additive: set VAULT_ENCRYPTION_KEY (a Fernet key -- generate one
with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
to encrypt new writes. Follows the same graceful-degradation pattern as
JWT_SECRET in core/config.py: if unset, writes stay gzip-only (compressed but
not encrypted) with a loud warning, since a demo/air-gapped instance should
still start -- a real deployment must set this.
"""
import os
import warnings
from cryptography.fernet import Fernet

_ENC_MAGIC = b"ULPFV1"

_key_env = os.getenv("VAULT_ENCRYPTION_KEY", "").strip()
if _key_env:
    _fernet = Fernet(_key_env.encode())
else:
    _fernet = None
    warnings.warn(
        "VAULT_ENCRYPTION_KEY is not set -- the raw log vault will be stored "
        "compressed but NOT encrypted at rest. Generate one with "
        '`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` '
        "and set it in .env before real use.",
        stacklevel=2,
    )


def is_enabled() -> bool:
    return _fernet is not None


def encrypt(data: bytes) -> bytes:
    if not _fernet:
        return data
    return _ENC_MAGIC + _fernet.encrypt(data)


def decrypt(data: bytes) -> bytes:
    if data.startswith(_ENC_MAGIC):
        if not _fernet:
            raise RuntimeError(
                "Found an encrypted vault file but VAULT_ENCRYPTION_KEY is not set -- cannot decrypt it."
            )
        return _fernet.decrypt(data[len(_ENC_MAGIC):])
    return data
