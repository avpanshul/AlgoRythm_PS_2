"""
Password hashing and JWT issuance/validation.

Minimal, dependency-light auth core: passlib[bcrypt] for password hashing,
PyJWT for signing/validating bearer tokens. No refresh tokens / rotation --
this is a single short-lived bearer access token, sized for this demo/SIEM
backend, not a full OAuth2 provider.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import pyotp
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return pwd_context.verify(plain_password, password_hash)
    except ValueError:
        # Malformed/unknown hash format -- treat as verification failure, not a crash.
        return False


def create_access_token(subject: str, extra_claims: Optional[dict] = None, expire_minutes: Optional[int] = None) -> str:
    """Issues a full-session bearer token. `scope` defaults to "full" (a real
    human user session) unless the caller overrides it via extra_claims --
    app/api/v1/admin.py's ingest-token issuance sets scope="ingest" instead
    (Part D1: separate ingest-vs-admin token identities)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes if expire_minutes is not None else settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
        "scope": "full",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_preauth_token(subject: str) -> str:
    """Short-lived, narrow-purpose token issued after a correct password but
    before the TOTP code has been checked (Part D1 MFA). Deliberately its own
    `type` ("mfa_preauth", not "access") so it's rejected outright by
    get_current_user / every real endpoint -- it can only ever be redeemed at
    POST /auth/mfa/verify, never used as a session token even if leaked."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.MFA_PREAUTH_EXPIRE_MINUTES),
        "type": "mfa_preauth",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


class TokenError(Exception):
    pass


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Token expired")
    except jwt.InvalidTokenError:
        raise TokenError("Invalid token")
    if payload.get("type") != "access":
        raise TokenError("Invalid token type")
    return payload


def decode_preauth_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Pre-auth token expired -- log in again")
    except jwt.InvalidTokenError:
        raise TokenError("Invalid pre-auth token")
    if payload.get("type") != "mfa_preauth":
        raise TokenError("Invalid token type")
    return payload


# ─── MFA (TOTP, RFC 6238) ────────────────────────────────────────────

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=settings.MFA_ISSUER_NAME)


def verify_totp_code(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    # valid_window=1 tolerates one 30s step of clock drift either side --
    # standard practice for TOTP verification, not a broadened attack window
    # (still only 3 codes total are ever valid at once).
    return pyotp.totp.TOTP(secret).verify(code.strip(), valid_window=1)
