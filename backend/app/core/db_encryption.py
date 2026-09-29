"""Application-level, column-level encryption at rest (Part D4).

Full-disk/database-level encryption (Postgres TDE, LUKS, an encrypted cloud
disk) is a deployment-layer concern this app can't provide from inside itself
-- see docs/deployment.md for that. What application code *can* actually do
is make sure that specific columns holding a real secret (not just sensitive
business data) are never written to the database file in plaintext, so a
stolen `pg_dump`/disk snapshot doesn't hand over that secret directly even
without the deployment-layer protections.

Same graceful-degradation pattern as core/vault_encryption.py and
core/security.py's JWT_SECRET: if DB_ENCRYPTION_KEY is unset, values are
stored in plaintext (compatible with existing rows) with a loud one-time
warning, since a demo/local instance should still start. Generate a key with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
"""
import os
import warnings

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import TypeDecorator, String

_ENC_PREFIX = "encv1:"

_key_env = os.getenv("DB_ENCRYPTION_KEY", "").strip()
if _key_env:
    _fernet = Fernet(_key_env.encode())
else:
    _fernet = None
    warnings.warn(
        "DB_ENCRYPTION_KEY is not set -- columns using EncryptedString "
        "(e.g. User.mfa_secret) will be stored in plaintext in the database. "
        'Generate one with `python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"` and set it in .env before real use.',
        stacklevel=2,
    )


def is_enabled() -> bool:
    return _fernet is not None


class EncryptedString(TypeDecorator):
    """A String column that's Fernet-encrypted on write and decrypted on
    read, transparent to callers. Falls back to plaintext (no prefix) when
    DB_ENCRYPTION_KEY isn't configured, and can still read old plaintext
    rows even after a key is later set (checked via the encv1: prefix, not
    assumed)."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not _fernet:
            return value
        return _ENC_PREFIX + _fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not value.startswith(_ENC_PREFIX):
            return value
        if not _fernet:
            raise RuntimeError(
                "Found an encrypted column value but DB_ENCRYPTION_KEY is not set -- cannot decrypt it."
            )
        try:
            return _fernet.decrypt(value[len(_ENC_PREFIX):].encode("ascii")).decode("utf-8")
        except InvalidToken:
            raise RuntimeError("Could not decrypt column value -- DB_ENCRYPTION_KEY does not match the key it was encrypted with.")
