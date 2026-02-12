from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app_state import db
from core.auth_utils import create_access_token, get_password_hash, verify_password
from deps import get_current_user
from schemas import Token, UserRegister

router = APIRouter()


@router.post("/api/auth/register")
async def register(user: UserRegister):
    if db.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    db.create_user(user.username, get_password_hash(user.password))
    return {"success": True}


@router.post("/api/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/api/auth/me")
async def read_users_me(current_user: Dict = Depends(get_current_user)):
    remaining = current_user["quota_limit"] - current_user["quota_used"]
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "is_pro": bool(current_user["is_pro"]),
        "quota_limit": current_user["quota_limit"],
        "quota_used": current_user["quota_used"],
        "quota_remaining": max(0, remaining),
    }
