"""Auth API: login (password grant), self-serve signup, current-user lookup, MFA."""
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import secrets as _secrets

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token, create_preauth_token, decode_preauth_token, TokenError,
    hash_password, verify_password,
    generate_totp_secret, totp_provisioning_uri, verify_totp_code,
)
from app.models.all import PlatformSetting, User, AuditLog

router = APIRouter()


def _session_timeout_minutes(db: Session) -> int | None:
    """Real-settings-backed override for how long a freshly-issued token is
    valid, set via the Settings page's Security tab (PUT /settings). None
    means "use the JWT_EXPIRE_MINUTES env default" -- this only overrides
    when an admin has actually saved a value."""
    row = db.query(PlatformSetting).filter(PlatformSetting.key == "session_timeout_minutes").first()
    return int(row.value) if row and row.value else None


class LoginRequest(BaseModel):
    # Plain str (not EmailStr) to avoid a hard dependency on `email-validator`;
    # correctness is enforced by the DB lookup + password check, not by format here.
    email: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=1, max_length=256)


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=8, max_length=256)


class TokenResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    # Set instead of access_token when the account has MFA enabled: the
    # caller must redeem this at POST /auth/mfa/verify with a TOTP code
    # before it gets a real session token. Part D1.
    mfa_required: bool = False
    preauth_token: Optional[str] = None


class MfaVerifyRequest(BaseModel):
    preauth_token: str
    code: str = Field(..., min_length=6, max_length=8)


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaEnableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)


class MfaDisableRequest(BaseModel):
    password: str


class CurrentUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role_name: str | None = None
    organization_id: str | None = None
    status: str

    class Config:
        from_attributes = True


def _authenticate(db: Session, email: str, password: str) -> User:
    """Part D1: account lockout. locked_until is checked BEFORE the password
    is compared, so a locked account can't be brute-forced during its own
    lockout window either. A wrong password increments failed_login_attempts
    and, once it crosses ACCOUNT_LOCKOUT_THRESHOLD, sets locked_until --
    reset back to 0 on the next successful login."""
    user = db.query(User).filter(User.email == email).first()

    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        retry_minutes = max(1, int((user.locked_until - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked due to repeated failed logins. Try again in {retry_minutes} minute(s).",
        )

    if not user or not verify_password(password, user.password_hash or ""):
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_THRESHOLD:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
                db.add(AuditLog(user=user.id, action="account_locked", entity_type="User", entity_id=user.id,
                                 after_state={"failed_attempts": user.failed_login_attempts}))
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

    return user


def _issue_login_response(db: Session, user: User) -> TokenResponse:
    """Shared MFA branch point for every password-grant login path: if the
    account has MFA enabled, hand back a short-lived preauth_token instead
    of a real session -- the caller must redeem it at /auth/mfa/verify."""
    if user.mfa_enabled:
        return TokenResponse(mfa_required=True, preauth_token=create_preauth_token(user.id))
    token = create_access_token(subject=user.id, extra_claims={"role": user.role_name}, expire_minutes=_session_timeout_minutes(db))
    return TokenResponse(access_token=token)


@router.post("/auth/login", response_model=TokenResponse)
def login_json(req: LoginRequest, db: Session = Depends(get_db)):
    """JSON login: {"email": "...", "password": "..."} -> either
    {access_token, token_type} or, if MFA is enabled, {mfa_required: true,
    preauth_token} to be redeemed at POST /auth/mfa/verify."""
    user = _authenticate(db, req.email, req.password)
    return _issue_login_response(db, user)


@router.post("/auth/mfa/verify", response_model=TokenResponse)
def mfa_verify(req: MfaVerifyRequest, db: Session = Depends(get_db)):
    """Second step of a login for an MFA-enabled account: exchanges a
    preauth_token (from /auth/login) + a valid TOTP code for a real session
    token. The preauth token alone (without a correct code) is useless
    against every other endpoint -- get_current_user rejects its `type`."""
    try:
        payload = decode_preauth_token(req.preauth_token)
    except TokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA is not enabled on this account")
    if not verify_totp_code(user.mfa_secret, req.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code")

    token = create_access_token(subject=user.id, extra_claims={"role": user.role_name}, expire_minutes=_session_timeout_minutes(db))
    return TokenResponse(access_token=token)


@router.post("/auth/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generates a new TOTP secret and stores it, but does NOT enable MFA --
    a login can't be gated on a secret the user hasn't proven they've
    actually saved into an authenticator app yet. Call /auth/mfa/enable with
    a real generated code to complete setup. Calling this again before
    /auth/mfa/enable replaces the pending secret (safe: nothing is enabled
    yet)."""
    secret = generate_totp_secret()
    current_user.mfa_secret = secret
    db.commit()
    return MfaSetupResponse(secret=secret, provisioning_uri=totp_provisioning_uri(secret, current_user.email))


@router.post("/auth/mfa/enable")
def mfa_enable(req: MfaEnableRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="Call /auth/mfa/setup first")
    if not verify_totp_code(current_user.mfa_secret, req.code):
        raise HTTPException(status_code=400, detail="Invalid code -- check your authenticator app's current code and try again")
    current_user.mfa_enabled = True
    db.add(AuditLog(user=current_user.id, action="mfa_enabled", entity_type="User", entity_id=current_user.id))
    db.commit()
    return {"status": "mfa_enabled"}


@router.post("/auth/mfa/disable")
def mfa_disable(req: MfaDisableRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Requires the account's current password (not just a valid session) --
    an MFA disable is exactly the kind of action a stolen/idle session token
    shouldn't be able to take on its own."""
    if not verify_password(req.password, current_user.password_hash or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    db.add(AuditLog(user=current_user.id, action="mfa_disabled", entity_type="User", entity_id=current_user.id))
    db.commit()
    return {"status": "mfa_disabled"}


@router.post("/auth/signup", response_model=TokenResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """Real self-serve account creation, deliberately narrow: always creates
    an 'analyst' role at 'active' status -- never lets the caller pick their
    own role (the admin-only POST /users endpoint is what grants elevated
    roles, via a real admin). Auto-logs in on success so signup and login
    end at the same real, working state."""
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    slug = re.sub(r"[^a-z0-9]+", "-", req.name.strip().lower()).strip("-") or "user"
    user_id = f"{slug[:40]}-{uuid.uuid4().hex[:8]}"

    user = User(
        id=user_id, name=req.name.strip(), email=req.email,
        role_name="analyst", status="active",
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()

    token = create_access_token(subject=user.id, extra_claims={"role": user.role_name}, expire_minutes=_session_timeout_minutes(db))
    return TokenResponse(access_token=token)


@router.post("/auth/token", response_model=TokenResponse)
def login_oauth2_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password-grant form login (username=email), for Swagger UI's
    Authorize button. Known limitation: Swagger's built-in Authorize dialog
    has no second step for a TOTP code, so an MFA-enabled account can't
    complete login through it -- use POST /auth/login + /auth/mfa/verify
    instead (documented, not silently broken: this returns 403 rather than
    a token or a fake mfa_required the dialog can't act on)."""
    user = _authenticate(db, form_data.username, form_data.password)
    if user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA is enabled on this account -- use POST /auth/login + /auth/mfa/verify, not the Swagger Authorize form")
    token = create_access_token(subject=user.id, extra_claims={"role": user.role_name}, expire_minutes=_session_timeout_minutes(db))
    return TokenResponse(access_token=token)


@router.get("/auth/csrf-token")
def issue_csrf_token(response: Response):
    """Issues a CSRF double-submit cookie + returns the same value in the
    body (see app/core/security_middleware.py's csrf_middleware). A no-op
    for this API's normal bearer-token clients, which never set this cookie
    at all and so never trigger the check; relevant only for a client that
    opts into cookie-based auth."""
    token = _secrets.token_urlsafe(32)
    response.set_cookie("ulpf_csrf", token, httponly=False, samesite="strict", secure=True)
    return {"csrf_token": token}


@router.get("/auth/me", response_model=CurrentUserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
