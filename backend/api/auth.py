import os
import time
import logging
import secrets
import string
from datetime import timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError

from app_state import db
from core.auth_utils import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
    verify_token_hash,
)
from deps import get_current_user
from schemas import CliDeviceApproveRequest, CliDevicePollRequest, CliDeviceSessionResponse, CliDeviceStartResponse, RefreshTokenRequest, Token, UserRegister

router = APIRouter()
logger = logging.getLogger(__name__)

REFRESH_COOKIE_NAME = "nbs_refresh_token"
REFRESH_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
COOKIE_SECURE = str(os.getenv("COOKIE_SECURE", "false")).strip().lower() in {"1", "true", "yes", "on"}
CLI_DEVICE_CODE_TTL_SECONDS = int(os.getenv("NBS_CLI_DEVICE_CODE_TTL_SECONDS", "600"))
CLI_DEVICE_POLL_INTERVAL_SECONDS = int(os.getenv("NBS_CLI_DEVICE_POLL_INTERVAL_SECONDS", "2"))
CLI_DEVICE_USER_CODE_LENGTH = int(os.getenv("NBS_CLI_DEVICE_USER_CODE_LENGTH", "8"))


def _now_ts() -> float:
    return time.time()


def _request_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None


def _auth_log(event: str, request: Request, **fields) -> None:
    payload = {
        "event": event,
        "ip": _request_ip(request),
        "user_agent": request.headers.get("user-agent"),
    }
    payload.update(fields)
    safe_payload = {k: v for k, v in payload.items() if v not in (None, "", {})}
    logger.warning("auth_event %s", safe_payload)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")


def _build_session(user: Dict, request: Request) -> Token:
    access_token, access_expire = create_access_token(
        data={"sub": str(user["id"]), "username": user["username"], "role": "admin" if user["username"] == "admin" else "user"}
    )
    refresh_token, refresh_expire, refresh_jti = create_refresh_token(
        data={"sub": str(user["id"]), "username": user["username"], "role": "admin" if user["username"] == "admin" else "user"}
    )
    db.purge_expired_refresh_tokens()
    db.create_refresh_token(
        user_id=user["id"],
        jti=refresh_jti,
        token_hash=hash_token(refresh_token),
        expires_at=refresh_expire.replace(tzinfo=timezone.utc).timestamp(),
        user_agent=request.headers.get("user-agent"),
        ip=_request_ip(request),
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        expires_in=max(1, int(access_expire.replace(tzinfo=timezone.utc).timestamp() - _now_ts())),
        refresh_expires_in=max(1, int(refresh_expire.replace(tzinfo=timezone.utc).timestamp() - _now_ts())),
    )


def _resolve_refresh_token(request: Request, body: Optional[RefreshTokenRequest]) -> Optional[str]:
    if body and body.refresh_token:
        return body.refresh_token.strip()
    cookie_value = request.cookies.get(REFRESH_COOKIE_NAME)
    if isinstance(cookie_value, str) and cookie_value.strip():
        return cookie_value.strip()
    return None


def _cli_user_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(max(6, CLI_DEVICE_USER_CODE_LENGTH)))
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))


def _cli_device_payload(device_code: str, user_code: str, request: Request) -> CliDeviceStartResponse:
    base_url = str(request.base_url).rstrip("/")
    verification_uri = f"{base_url}/cli-sync"
    return CliDeviceStartResponse(
        device_code=device_code,
        user_code=user_code,
        verification_uri=verification_uri,
        verification_uri_complete=f"{verification_uri}?user_code={user_code}",
        expires_in=CLI_DEVICE_CODE_TTL_SECONDS,
        interval=CLI_DEVICE_POLL_INTERVAL_SECONDS,
    )


@router.post("/api/auth/register")
async def register(user: UserRegister):
    if db.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    db.create_user(user.username, get_password_hash(user.password))
    return {"success": True}


@router.post("/api/auth/login", response_model=Token)
async def login_for_access_token(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session = _build_session(user, request)
    _set_refresh_cookie(response, session.refresh_token or "")
    return session


@router.post("/api/auth/refresh", response_model=Token)
async def refresh_access_token(request: Request, response: Response, body: Optional[RefreshTokenRequest] = None):
    raw_refresh_token = _resolve_refresh_token(request, body)
    if not raw_refresh_token:
        _auth_log("refresh_failed", request, reason="missing_refresh_token")
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = decode_token(raw_refresh_token, expected_type="refresh")
    except JWTError as exc:
        _auth_log("refresh_failed", request, reason="invalid_refresh_token")
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    token_jti = str(payload.get("jti") or "").strip()
    subject = str(payload.get("sub") or "").strip()
    if not token_jti or not subject:
        _auth_log("refresh_failed", request, reason="missing_jti_or_subject")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    stored = db.get_refresh_token(token_jti)
    if not stored or stored.get("revoked_at"):
        _auth_log("refresh_failed", request, reason="token_revoked", token_jti=token_jti)
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    if float(stored.get("expires_at") or 0) <= _now_ts():
        db.revoke_refresh_token(token_jti)
        _auth_log("refresh_failed", request, reason="token_expired", token_jti=token_jti)
        raise HTTPException(status_code=401, detail="Refresh token expired")
    if not verify_token_hash(raw_refresh_token, stored.get("token_hash") or ""):
        db.revoke_refresh_token(token_jti)
        _auth_log("refresh_failed", request, reason="token_mismatch", token_jti=token_jti)
        raise HTTPException(status_code=401, detail="Refresh token mismatch")

    user = db.get_user_by_id(int(subject)) if subject.isdigit() else db.get_user_by_username(subject)
    if not user:
        db.revoke_refresh_token(token_jti)
        _auth_log("refresh_failed", request, reason="user_not_found", token_jti=token_jti, subject=subject)
        raise HTTPException(status_code=401, detail="User not found")

    session = _build_session(user, request)
    try:
        new_payload = decode_token(session.refresh_token or "", expected_type="refresh")
        db.revoke_refresh_token(token_jti, replaced_by_jti=str(new_payload.get("jti") or "").strip() or None)
    except JWTError:
        db.revoke_refresh_token(token_jti)
        _auth_log("refresh_warn", request, reason="new_refresh_decode_failed", token_jti=token_jti)
    _set_refresh_cookie(response, session.refresh_token or "")
    return session


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response, body: Optional[RefreshTokenRequest] = None):
    raw_refresh_token = _resolve_refresh_token(request, body)
    if raw_refresh_token:
        try:
            payload = decode_token(raw_refresh_token, expected_type="refresh")
            token_jti = str(payload.get("jti") or "").strip()
            if token_jti:
                db.revoke_refresh_token(token_jti)
        except JWTError:
            _auth_log("logout_warn", request, reason="invalid_refresh_token")
    else:
        _auth_log("logout_info", request, reason="missing_refresh_token")
    _clear_refresh_cookie(response)
    return {"success": True}


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


@router.post("/api/auth/cli/device/start", response_model=CliDeviceStartResponse)
async def start_cli_device(request: Request):
    db.purge_expired_cli_device_tokens()
    device_code = secrets.token_urlsafe(32)
    user_code = _cli_user_code()
    expires_at = _now_ts() + CLI_DEVICE_CODE_TTL_SECONDS
    db.create_cli_device_token(
        device_code=device_code,
        user_code=user_code,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip=_request_ip(request),
    )
    return _cli_device_payload(device_code, user_code, request)


@router.post("/api/auth/cli/device/approve")
async def approve_cli_device(
    request: Request,
    body: CliDeviceApproveRequest,
    current_user: Dict = Depends(get_current_user),
):
    raw_user_code = str(body.user_code or "").strip().upper()
    raw_device_code = str(body.device_code or "").strip()
    record = None
    if raw_device_code:
        record = db.get_cli_device_token(raw_device_code)
    elif raw_user_code:
        record = db.get_cli_device_token_by_user_code(raw_user_code)
    if not record:
        raise HTTPException(status_code=404, detail="Device code not found")
    if float(record.get("expires_at") or 0) <= _now_ts():
        raise HTTPException(status_code=410, detail="Device code expired")
    session = _build_session(current_user, request)
    approved = db.approve_cli_device_token(
        device_code=record["device_code"],
        user_id=current_user["id"],
        access_token=session.access_token or "",
        refresh_token=session.refresh_token or "",
        token_type=session.token_type,
        base_url=str(request.base_url).rstrip("/"),
        username=current_user["username"],
        user_agent=request.headers.get("user-agent"),
        ip=_request_ip(request),
    )
    if not approved:
        raise HTTPException(status_code=409, detail="Device code can no longer be approved")
    return {"success": True}


@router.post("/api/auth/cli/device/poll", response_model=CliDeviceSessionResponse)
async def poll_cli_device(body: CliDevicePollRequest):
    db.purge_expired_cli_device_tokens()
    record = db.get_cli_device_token(body.device_code)
    if not record:
        raise HTTPException(status_code=404, detail="Device code not found")
    if float(record.get("expires_at") or 0) <= _now_ts():
        raise HTTPException(status_code=410, detail="Device code expired")
    status_value = str(record.get("status") or "pending")
    if status_value == "pending":
        raise HTTPException(status_code=428, detail="Authorization pending")
    if status_value != "approved":
        raise HTTPException(status_code=400, detail="Device code already consumed")
    if not record.get("access_token") or not record.get("refresh_token"):
        raise HTTPException(status_code=400, detail="Device authorization incomplete")
    db.consume_cli_device_token(body.device_code)
    return CliDeviceSessionResponse(
        access_token=record["access_token"],
        token_type=record.get("token_type") or "bearer",
        refresh_token=record["refresh_token"],
        base_url=str(record.get("base_url") or "").rstrip("/"),
        username=record.get("username"),
    )
