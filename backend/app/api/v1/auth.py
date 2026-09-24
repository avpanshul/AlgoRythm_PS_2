"""Auth API: login (password grant) + current-user lookup."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.models.all import User

router = APIRouter()


class LoginRequest(BaseModel):
    # Plain str (not EmailStr) to avoid a hard dependency on `email-validator`;
    # correctness is enforced by the DB lookup + password check, not by format here.
    email: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
    return user


@router.post("/auth/login", response_model=TokenResponse)
def login_json(req: LoginRequest, db: Session = Depends(get_db)):
    """JSON login: {"email": "...", "password": "..."} -> {access_token, token_type}."""
    user = _authenticate(db, req.email, req.password)
    token = create_access_token(subject=user.id, extra_claims={"role": user.role_name})
    return TokenResponse(access_token=token)


@router.post("/auth/token", response_model=TokenResponse)
def login_oauth2_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password-grant form login (username=email), for Swagger UI's Authorize button."""
    user = _authenticate(db, form_data.username, form_data.password)
    token = create_access_token(subject=user.id, extra_claims={"role": user.role_name})
    return TokenResponse(access_token=token)


@router.get("/auth/me", response_model=CurrentUserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
