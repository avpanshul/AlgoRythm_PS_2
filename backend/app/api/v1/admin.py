"""Admin API (Users, Roles, Organizations)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.all import User, Role, Organization, AuditLog

router = APIRouter()

class UserCreate(BaseModel):
    id: str
    name: str
    email: str
    role_name: Optional[str] = None
    organization_id: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role_name: Optional[str] = None
    organization_id: Optional[str] = None
    status: Optional[str] = None


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.post("/users")
def create_user(req: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter((User.id == req.id) | (User.email == req.email)).first():
        raise HTTPException(status_code=400, detail="User ID or Email already exists")
        
    user = User(**req.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.put("/users/{user_id}")
def update_user(user_id: str, req: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
        
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}


@router.get("/roles")
def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).all()

@router.get("/organizations")
def list_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).all()

@router.get("/connectors")
def list_connectors():
    # Stub for connectors if not in Integrations table
    return [
        {"id": "c1", "name": "Kafka Source"},
        {"id": "c2", "name": "Syslog Listener"},
        {"id": "c3", "name": "S3 Fetcher"}
    ]
