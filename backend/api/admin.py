import os
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app_state import AUDIO_DIR, db, digital_human_gen, img_gen, video_gen
from core.auth_utils import get_password_hash
from core.env_utils import normalize_key_list
from core.key_pools import normalize_key_pools
from core.qwen_tts import synthesize_tts
from deps import get_current_user
from helpers import (
    _build_model_candidates,
    _get_credentials,
    _get_model_catalog,
    _get_model_route_summary,
    _get_model_routes,
    _get_prompt_channels_config,
    _get_service_routes,
    _get_system_config_with_env,
    _get_tts_base_url,
    _get_video_base_url,
    _load_system_config,
    _merge_candidates,
    _save_system_config,
    normalize_credentials,
    normalize_prompt_channels,
    normalize_model_catalog,
    normalize_model_routes,
    normalize_service_routes,
    validate_prompt_channels_config,
)
from schemas import (
    AdminBulkCreateUsersRequest,
    AdminCreateUserRequest,
    ModelTestRequest,
    SystemConfigUpdateRequest,
    ToggleFeatureRequest,
    UserUpdateRequest,
)

router = APIRouter()
PROMPT_HEALTH_CACHE: Dict[str, Any] = {}


def _set_prompt_health_cache(payload: Dict[str, Any]):
    global PROMPT_HEALTH_CACHE
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("checked_at", int(time.time()))
    PROMPT_HEALTH_CACHE = payload


def _build_prompt_health(prompt_channels: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    channels_cfg = normalize_prompt_channels(prompt_channels or _get_prompt_channels_config())
    health: Dict[str, Any] = {
        "checked_at": int(time.time()),
        "channels": {},
        "warnings": [],
    }
    test_prompt = "Health check prompt. Return an optimized concise drawing prompt."
    for channel in ("google", "bytedance", "aliyun"):
        channel_cfg = channels_cfg.get(channel) or {"enabled": True, "models": []}
        model_chain = [str(v).strip() for v in (channel_cfg.get("models") or []) if str(v).strip()]
        channel_result: Dict[str, Any] = {
            "enabled": channel_cfg.get("enabled") is True,
            "models": model_chain,
            "status": "red",
            "fallback_depth": None,
            "selected_model": None,
            "candidate_count": 0,
            "attempts": [],
            "message": "",
        }
        if channel_result["enabled"] is not True:
            channel_result["message"] = "channel disabled"
            health["warnings"].append(f"{channel}: 通道已停用")
            health["channels"][channel] = channel_result
            continue
        if not model_chain:
            channel_result["message"] = "no models configured"
            health["warnings"].append(f"{channel}: 未配置模型链")
            health["channels"][channel] = channel_result
            continue

        for index, model_name in enumerate(model_chain):
            candidates = _build_model_candidates("prompt", model=model_name)
            candidate_count = len(candidates)
            channel_result["candidate_count"] += candidate_count
            if not candidates:
                channel_result["attempts"].append(
                    {"model": model_name, "status": "no_key", "error": "no available key candidates"}
                )
                continue
            model_success = False
            model_error = ""
            for candidate in candidates[:2]:
                try:
                    optimized = img_gen.optimize_prompt(
                        raw_prompt=test_prompt,
                        subject="general",
                        model=model_name,
                        api_key=candidate.get("key"),
                        base_url=candidate.get("base_url"),
                    )
                    if optimized:
                        model_success = True
                        break
                    last_error = getattr(img_gen, "last_error", None) or {}
                    model_error = str(last_error.get("message") or "optimization returned empty")
                except Exception as exc:
                    model_error = str(exc)
            if model_success:
                channel_result["selected_model"] = model_name
                channel_result["fallback_depth"] = index
                channel_result["status"] = "green" if index == 0 else "yellow"
                channel_result["message"] = (
                    f"primary model healthy: {model_name}"
                    if index == 0
                    else f"fallback model healthy: {model_name}"
                )
                channel_result["attempts"].append({"model": model_name, "status": "success"})
                break
            channel_result["attempts"].append(
                {"model": model_name, "status": "failed", "error": model_error or "model request failed"}
            )

        if channel_result["status"] == "red":
            channel_result["message"] = channel_result["message"] or "all models failed"
            health["warnings"].append(f"{channel}: 全部模型检测失败")
        elif channel_result["status"] == "yellow":
            health["warnings"].append(f"{channel}: 主模型失败，已回退 {channel_result['selected_model']}")

        health["channels"][channel] = channel_result

    return health


def _build_credential_reference_counts(
    model_routes: List[Dict[str, Any]],
    service_routes: List[Dict[str, Any]],
) -> Dict[str, int]:
    counts: Dict[str, int] = {}

    def add(credential_id: Optional[str]) -> None:
        cred_id = str(credential_id or "").strip()
        if not cred_id:
            return
        counts[cred_id] = counts.get(cred_id, 0) + 1

    for item in model_routes or []:
        add(item.get("primary_credential_id"))
        for cred_id in item.get("fallback_credential_ids") or []:
            add(cred_id)
    for item in service_routes or []:
        add(item.get("primary_credential_id"))
        for cred_id in item.get("fallback_credential_ids") or []:
            add(cred_id)
    return counts


def _build_admin_model_entries(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for item in models or []:
        summary = _get_model_route_summary(item.get("service"), item.get("model"))
        next_item = dict(item)
        next_item["route"] = summary
        output.append(next_item)
    return output


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
    credentials = _get_credentials()
    model_catalog = _get_model_catalog()
    model_routes = _get_model_routes()
    service_routes = _get_service_routes()
    reference_counts = _build_credential_reference_counts(model_routes, service_routes)
    prompt_channels = normalize_prompt_channels(cfg.get("prompt_channels"), model_catalog)
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
        "models": _build_admin_model_entries(model_catalog),
        "model_catalog": model_catalog,
        "credentials": [
            {
                **item,
                "reference_count": reference_counts.get(item.get("id"), 0),
            }
            for item in credentials
        ],
        "model_routes": model_routes,
        "service_routes": service_routes,
        "prompt_channels": prompt_channels,
        "prompt_health": PROMPT_HEALTH_CACHE or None,
    }


@router.post("/api/admin/system_config")
async def update_system_config(req: SystemConfigUpdateRequest, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    cfg = _load_system_config()
    cfg.setdefault("auth", {})
    cfg.setdefault("api", {})
    if req.image is not None:
        cfg["auth"]["api_key"] = req.image.api_key.strip()
        cfg["auth"]["backup_keys"] = normalize_key_list(req.image.backup_keys)
        if req.image.base_url is not None:
            cfg["api"]["base_url"] = req.image.base_url.strip()
    cfg.setdefault("tts", {})
    if req.tts is not None:
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
    raw_model_items = req.model_catalog if req.model_catalog is not None else req.models
    if raw_model_items is not None:
        raw_models = []
        for item in raw_model_items:
            if hasattr(item, "model_dump"):
                raw_models.append(item.model_dump())
            elif hasattr(item, "dict"):
                raw_models.append(item.dict())
            else:
                raw_models.append(item)
        cfg["model_catalog"] = normalize_model_catalog(raw_models)
        cfg["models"] = cfg["model_catalog"]
    if req.credentials is not None:
        raw_credentials = []
        for item in req.credentials:
            if hasattr(item, "model_dump"):
                raw_credentials.append(item.model_dump())
            elif hasattr(item, "dict"):
                raw_credentials.append(item.dict())
            else:
                raw_credentials.append(item)
        cfg["credentials"] = normalize_credentials(raw_credentials)
    if req.model_routes is not None:
        raw_model_routes = []
        for item in req.model_routes:
            if hasattr(item, "model_dump"):
                raw_model_routes.append(item.model_dump())
            elif hasattr(item, "dict"):
                raw_model_routes.append(item.dict())
            else:
                raw_model_routes.append(item)
        cfg["model_routes"] = normalize_model_routes(raw_model_routes, normalize_credentials(cfg.get("credentials") or []))
    if req.service_routes is not None:
        raw_service_routes = []
        for item in req.service_routes:
            if hasattr(item, "model_dump"):
                raw_service_routes.append(item.model_dump())
            elif hasattr(item, "dict"):
                raw_service_routes.append(item.dict())
            else:
                raw_service_routes.append(item)
        cfg["service_routes"] = normalize_service_routes(raw_service_routes, normalize_credentials(cfg.get("credentials") or []))

    prompt_models = normalize_model_catalog(cfg.get("model_catalog") or cfg.get("models") or [])
    prompt_key_pools = normalize_key_pools(cfg.get("key_pools") or [])
    requested_channels = req.prompt_channels if req.prompt_channels is not None else cfg.get("prompt_channels")
    cfg["prompt_channels"] = normalize_prompt_channels(requested_channels, prompt_models)

    validation = validate_prompt_channels_config(
        models=prompt_models,
        key_pools=prompt_key_pools,
        prompt_channels=cfg.get("prompt_channels") or {},
        credentials=cfg.get("credentials") or [],
        model_routes=cfg.get("model_routes") or [],
        service_routes=cfg.get("service_routes") or [],
    )
    if validation.get("errors"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PROMPT_CONFIG_INVALID",
                "errors": validation.get("errors") or [],
                "warnings": validation.get("warnings") or [],
                "channels": validation.get("channels") or {},
            },
        )

    _save_system_config(cfg)
    img_gen._apply_config(cfg)
    health_error = None
    health_payload: Optional[Dict[str, Any]] = None
    try:
        health_payload = _build_prompt_health(cfg.get("prompt_channels"))
        _set_prompt_health_cache(health_payload)
    except Exception as exc:
        health_error = str(exc)

    warnings = list(validation.get("warnings") or [])
    if health_payload and health_payload.get("warnings"):
        warnings.extend([str(item) for item in health_payload.get("warnings") if item])
    if health_error:
        warnings.append(f"自动健康检查执行失败: {health_error}")

    return {
        "success": True,
        "prompt_channels": cfg.get("prompt_channels") or {},
        "prompt_health": health_payload,
        "warnings": warnings,
    }


@router.get("/api/admin/prompt_health")
async def get_prompt_health(current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    cfg = _get_system_config_with_env()
    prompt_channels = normalize_prompt_channels(cfg.get("prompt_channels"), _get_model_catalog())
    health_payload = _build_prompt_health(prompt_channels)
    _set_prompt_health_cache(health_payload)
    return health_payload


def _build_test_candidates(req: ModelTestRequest) -> List[Dict]:
    model_name = (req.model or "").strip()
    candidates = _build_model_candidates(req.service, model_name)
    override_keys = normalize_key_list([req.api_key] + (req.backup_keys or []))
    if not override_keys and not req.base_url:
        return candidates
    base_url = (req.base_url or "").strip() or (candidates[0].get("base_url") if candidates else None)
    override = [
        {"key": key, "base_url": base_url, "platform": req.platform}
        for key in override_keys
        if key
    ]
    if not override and base_url:
        override = [{"key": None, "base_url": base_url, "platform": req.platform}]
    return _merge_candidates(override, candidates)


@router.post("/api/admin/model_test")
async def test_model(req: ModelTestRequest, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    model_name = (req.model or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="Model ID is required")

    candidates = _build_test_candidates(req)
    if not candidates:
        raise HTTPException(status_code=400, detail="Missing model configuration or key")

    service = (req.service or "").strip().lower()
    last_error = None

    if service == "image":
        prompt = (req.prompt or "测试图片生成").strip()
        size = req.size
        if not size:
            size = "2K" if "seedream" in model_name.lower() else "1024x1024"
        for candidate in candidates:
            result = img_gen.generate_image(
                prompt,
                size=size,
                base_url=candidate.get("base_url"),
                api_key=candidate.get("key"),
                model=model_name,
            )
            if result:
                return {"success": True, "service": service, "model": model_name, "result": {"url": result}}
            last_error = img_gen.last_error or {"message": "Image generation failed"}
        raise HTTPException(status_code=502, detail=last_error.get("message") if isinstance(last_error, dict) else str(last_error))

    if service == "audio":
        prompt = (req.prompt or "这是一次模型连通性测试").strip()
        voice = (req.voice or "Cherry").strip()
        tts_base_url = _get_tts_base_url()
        audio_id = f"tts_test_{int(time.time())}_{secrets.token_hex(3)}"
        for candidate in candidates:
            try:
                output_path, mime_type = synthesize_tts(
                    text=prompt,
                    output_dir=AUDIO_DIR,
                    filename_base=audio_id,
                    voice=voice,
                    model=model_name,
                    api_key=candidate.get("key"),
                    base_url=candidate.get("base_url") or tts_base_url,
                )
                return {
                    "success": True,
                    "service": service,
                    "model": model_name,
                    "result": {
                        "url": f"/static/audio/{os.path.basename(output_path)}",
                        "type": mime_type,
                        "voice": voice,
                    },
                }
            except Exception as exc:
                last_error = str(exc)
        raise HTTPException(status_code=502, detail=last_error or "TTS failed")

    if service == "video":
        prompt = (req.prompt or "测试视频生成").strip()
        video_base_url = _get_video_base_url()
        image_url = (req.image_url or "").strip() or None
        if (video_gen._is_sora_model(model_name) or video_gen._is_bailian_i2v_model(model_name)) and not image_url:
            raise HTTPException(status_code=400, detail="Video test requires image_url for this model.")
        for candidate in candidates:
            response = video_gen.submit_task(
                prompt=prompt,
                model=model_name,
                image_url=image_url,
                api_key=candidate.get("key"),
                base_url=candidate.get("base_url") or video_base_url,
                platform=candidate.get("platform") or req.platform,
                resolution=req.resolution,
                duration_seconds=req.duration_seconds,
            )
            error = video_gen.extract_error(response)
            if not error:
                return {"success": True, "service": service, "model": model_name, "result": response}
            last_error = error
        raise HTTPException(status_code=502, detail=last_error or "Video test failed")

    if service == "digital_human":
        if not req.image_url or not req.audio_url:
            raise HTTPException(status_code=400, detail="Digital human test requires image_url and audio_url")
        prompt = (req.prompt or "").strip() or None
        for candidate in candidates:
            response = digital_human_gen.submit_task(
                image_url=req.image_url,
                audio_url=req.audio_url,
                prompt=prompt,
                resolution=480,
                api_key=candidate.get("key"),
                base_url=candidate.get("base_url"),
                model=model_name,
            )
            error = digital_human_gen.extract_error(response)
            if not error:
                return {"success": True, "service": service, "model": model_name, "result": response}
            last_error = error
        raise HTTPException(status_code=502, detail=last_error or "Digital human test failed")

    if service == "prompt":
        prompt = (req.prompt or "测试提示词优化").strip()
        for candidate in candidates:
            try:
                optimized = img_gen.optimize_prompt(
                    raw_prompt=prompt,
                    subject="general",
                    model=model_name,
                    api_key=candidate.get("key"),
                    base_url=candidate.get("base_url"),
                )
                if optimized:
                    return {"success": True, "service": service, "model": model_name, "result": {"text": optimized}}
            except Exception as exc:
                last_error = str(exc)
        raise HTTPException(status_code=502, detail=last_error or "Prompt test failed")

    raise HTTPException(status_code=400, detail="Unsupported service")


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


@router.post("/api/admin/users/batch")
async def admin_batch_create_users(req: AdminBulkCreateUsersRequest, current_user: Dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    created = []
    skipped = []
    failed = []
    for item in req.users:
        username = item.username.strip()
        if db.get_user_by_username(username):
            info = {"username": username, "reason": "Username already registered"}
            if req.skip_existing:
                skipped.append(info)
            else:
                failed.append(info)
            continue

        user_id = db.create_user(
            username,
            get_password_hash(item.password),
            is_pro=item.is_pro,
            quota_limit=item.quota_limit,
        )
        if user_id:
            created.append({"username": username, "user_id": user_id})
        else:
            failed.append({"username": username, "reason": "Create user failed"})

    return {
        "success": True,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "created": created,
        "skipped": skipped,
        "failed": failed,
    }


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
