from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from app_state import db, img_gen
from core.auth_utils import get_password_hash
from core.env_utils import normalize_key_list
from core.key_pools import normalize_key_pools
from deps import get_current_user
from helpers import _get_model_catalog, _get_system_config_with_env, _load_system_config, _save_system_config, normalize_model_catalog
from schemas import AdminCreateUserRequest, SystemConfigUpdateRequest, ToggleFeatureRequest, UserUpdateRequest

router = APIRouter()


@router.post("/api/admin/toggle_feature")
async def toggle_feature(req: ToggleFeatureRequest, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    db.toggle_feature(req.filename, req.featured)
    return {"success": True, "featured": req.featured}


@router.get("/api/admin/system_config")
async def get_system_config(current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    cfg = _get_system_config_with_env()
    auth_cfg = cfg.get("auth", {}) or {}
    api_cfg = cfg.get("api", {}) or {}
    tts_cfg = cfg.get("tts", {}) or {}
    video_cfg = cfg.get("video", {}) or {}
    key_pools = normalize_key_pools(cfg.get("key_pools") or [])
    model_catalog = _get_model_catalog()
    return {
        "image": {
            "api_key": auth_cfg.get("api_key", ""),
            "backup_keys": normalize_key_list(auth_cfg.get("backup_keys", [])),
            "base_url": api_cfg.get("base_url", ""),
        },
        "tts": {
            "api_key": tts_cfg.get("api_key", ""),
            "backup_keys": normalize_key_list(tts_cfg.get("backup_keys", [])),
            "base_url": tts_cfg.get("base_url", ""),
        },
        "video": {
            "api_key": video_cfg.get("api_key", ""),
            "backup_keys": normalize_key_list(video_cfg.get("backup_keys", [])),
            "base_url": video_cfg.get("base_url", ""),
        },
        "key_pools": key_pools,
        "models": model_catalog,
    }


@router.post("/api/admin/system_config")
async def update_system_config(req: SystemConfigUpdateRequest, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    cfg = _load_system_config()
    cfg.setdefault("auth", {})
    cfg.setdefault("api", {})
    cfg["auth"]["api_key"] = req.image.api_key.strip()
    cfg["auth"]["backup_keys"] = normalize_key_list(req.image.backup_keys)
    if req.image.base_url is not None:
        cfg["api"]["base_url"] = req.image.base_url.strip()
    cfg.setdefault("tts", {})
    cfg["tts"]["api_key"] = req.tts.api_key.strip()
    cfg["tts"]["backup_keys"] = normalize_key_list(req.tts.backup_keys)
    if req.tts.base_url is not None:
        cfg["tts"]["base_url"] = req.tts.base_url.strip()
    cfg["tts"].pop("ws_url", None)
    if req.video is not None:
        cfg.setdefault("video", {})
        cfg["video"]["api_key"] = req.video.api_key.strip()
        cfg["video"]["backup_keys"] = normalize_key_list(req.video.backup_keys)
        if req.video.base_url is not None:
            cfg["video"]["base_url"] = req.video.base_url.strip()
    if req.key_pools is not None:
        cfg["key_pools"] = normalize_key_pools(req.key_pools)
    if req.models is not None:
        raw_models = []
        for item in req.models:
            if hasattr(item, "model_dump"):
                raw_models.append(item.model_dump())
            elif hasattr(item, "dict"):
                raw_models.append(item.dict())
            else:
                raw_models.append(item)
        cfg["models"] = normalize_model_catalog(raw_models)
    _save_system_config(cfg)
    img_gen._apply_config(cfg)
    return {"success": True}


@router.get("/api/admin/users")
async def get_all_users(current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return db.get_all_users()


@router.post("/api/admin/users")
async def admin_create_user(req: AdminCreateUserRequest, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if db.get_user_by_username(req.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    user_id = db.create_user(
        req.username,
        get_password_hash(req.password),
        is_pro=req.is_pro,
        quota_limit=req.quota_limit,
    )
    if not user_id:
        raise HTTPException(status_code=400, detail="Create user failed")
    return {"success": True, "user_id": user_id}


@router.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("username") == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    if not db.delete_user(user_id):
        raise HTTPException(status_code=400, detail="Delete user failed")
    return {"success": True}


@router.post("/api/admin/update_user")
async def update_user(req: UserUpdateRequest, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    db.update_user_status(req.user_id, req.is_pro, req.quota_limit)
    return {"success": True}
