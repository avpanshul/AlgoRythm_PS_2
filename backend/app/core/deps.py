"""
Shared FastAPI dependencies for auth enforcement.
"""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, TokenError
from app.models.all import User, IngestToken

# tokenUrl is used only for OpenAPI docs (the "Authorize" button); the real
# endpoint is mounted under the API_V1_STR prefix in main.py.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Requires a full-session (human) token. Part D1: an ingest-scoped token
    (scope="ingest", see IngestToken/admin.py) is rejected here even though
    it's a structurally valid, unexpired JWT -- it can only be used against
    the ingestion router's get_ingest_or_user() dependency below. This is
    what actually separates the two token identities: possession of an
    ingest token alone can never reach /admin, /users, /settings, etc."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error

    try:
        payload = decode_access_token(token)
    except TokenError:
        raise credentials_error

    if payload.get("scope") == "ingest":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An ingest-scoped token cannot access this endpoint")

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_error
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    return user


class IngestPrincipal:
    """The authenticated identity on an ingest-scoped request -- either a real
    User (existing UI/manual-ingest flows keep working) or an ingest token's
    source_id (a forwarder/collector with no user account at all)."""

    def __init__(self, user: "User | None" = None, source_id: "str | None" = None, token_id: "str | None" = None):
        self.user = user
        self.source_id = source_id
        self.token_id = token_id


def get_ingest_or_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> IngestPrincipal:
    """Auth dependency for the ingestion router only. Accepts a full-session
    user token (unchanged existing behavior) OR an ingest-scoped token --
    but an ingest-scoped token is checked against IngestToken.revoked on
    every call (a JWT is otherwise stateless/can't be revoked before its own
    expiry), and its last_used_at is updated for real operational visibility
    into which forwarders are actually still sending data."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error

    try:
        payload = decode_access_token(token)
    except TokenError:
        raise credentials_error

    if payload.get("scope") == "ingest":
        jti = payload.get("jti")
        row = db.query(IngestToken).filter(IngestToken.id == jti).first() if jti else None
        if not row or row.revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This ingest token has been revoked")
        row.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return IngestPrincipal(source_id=payload.get("source_id"), token_id=jti)

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_error
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
    return IngestPrincipal(user=user)


def require_role(*allowed_roles: str):
    """Optional stricter dependency: require the current user to hold one of the given roles."""

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role_name not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _check
