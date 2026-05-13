import os
import time
import logging
import secrets
import string
from datetime import timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
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


def _public_base_url(request: Request) -> str:
    configured = str(os.getenv("EXTERNAL_BASE_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    host = request.headers.get("x-forwarded-host", "").split(",")[0].strip() or request.headers.get("host", "").strip()
    if host:
        scheme = proto or request.url.scheme
        return f"{scheme}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _cli_device_payload(device_code: str, user_code: str, request: Request) -> CliDeviceStartResponse:
    base_url = _public_base_url(request)
    verification_uri = f"{base_url}/api/auth/cli/sync-page"
    return CliDeviceStartResponse(
        device_code=device_code,
        user_code=user_code,
        verification_uri=verification_uri,
        verification_uri_complete=f"{verification_uri}?user_code={user_code}&device_code={device_code}",
        expires_in=CLI_DEVICE_CODE_TTL_SECONDS,
        interval=CLI_DEVICE_POLL_INTERVAL_SECONDS,
    )


CLI_SYNC_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Roil CLI 登录同步</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: linear-gradient(135deg, #f8fafc, #dbeafe 48%, #fef3c7); color: #0f172a; }
    main { width: min(560px, calc(100vw - 32px)); background: rgba(255,255,255,.84); border: 1px solid rgba(148,163,184,.45); border-radius: 28px; padding: 30px; box-shadow: 0 24px 80px rgba(15,23,42,.14); }
    h1 { margin: 0 0 10px; font-size: 28px; }
    p { line-height: 1.7; color: #334155; }
    code { display: inline-block; padding: 6px 10px; border-radius: 10px; background: #e0f2fe; color: #075985; font-weight: 700; letter-spacing: .08em; }
    button { width: 100%; margin-top: 16px; border: 0; border-radius: 16px; padding: 14px 18px; color: white; background: #0f766e; font-weight: 800; font-size: 16px; cursor: pointer; }
    button:disabled { opacity: .55; cursor: wait; }
    .status { margin-top: 16px; min-height: 24px; font-weight: 700; }
    .ok { color: #047857; }
    .err { color: #b91c1c; }
  </style>
</head>
<body>
  <main>
    <h1>同步 Roil CLI 登录态</h1>
    <p>这会给当前终端生成一个新的 CLI 会话，不会复制浏览器里的 refresh token。</p>
    <p>授权码：<code id="user-code">读取中</code></p>
    <button id="approve">授权给 CLI</button>
    <div id="status" class="status"></div>
  </main>
  <script>
    const params = new URLSearchParams(location.search);
    const userCode = (params.get('user_code') || '').trim();
    const deviceCode = (params.get('device_code') || '').trim();
    const statusEl = document.getElementById('status');
    document.getElementById('user-code').textContent = userCode || deviceCode || '缺少授权码';
    function token() { return localStorage.getItem('token') || ''; }
    function show(text, cls) { statusEl.textContent = text; statusEl.className = 'status ' + (cls || ''); }
    document.getElementById('approve').onclick = async () => {
      const btn = document.getElementById('approve');
      btn.disabled = true;
      try {
        const accessToken = token();
        if (!accessToken) throw new Error('浏览器当前没有可用登录态，请先在 Roil 平台登录。');
        const res = await fetch('/api/auth/cli/device/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + accessToken },
          credentials: 'include',
          body: JSON.stringify({ user_code: userCode || undefined, device_code: deviceCode || undefined })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || data.error || ('授权失败：HTTP ' + res.status));
        show('已授权。回到终端等待 nbs auth sync-web 自动完成。', 'ok');
      } catch (err) {
        show(err.message || String(err), 'err');
        btn.disabled = false;
      }
    };
  </script>
</body>
</html>"""


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


@router.get("/api/auth/cli/sync-page", response_class=HTMLResponse)
async def cli_sync_page():
    return HTMLResponse(CLI_SYNC_PAGE)


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
        base_url=_public_base_url(request),
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
