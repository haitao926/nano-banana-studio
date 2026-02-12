import base64
import glob
import io
import json
import mimetypes
import os
import re
import secrets
import time
import wave
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

import ipaddress
import requests
from fastapi import HTTPException, Request, UploadFile
from PIL import Image

from core.env_utils import get_env_list, get_env_str, normalize_key_list
from core.key_pools import normalize_key_pools, select_key_pools

MODEL_PLATFORM_BASE_URLS = {
    "vector": "https://api.vectorengine.ai",
    "bailian": "https://dashscope.aliyuncs.com/api/v1",
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
}
from core.video_generator import VideoGenerator
from app_state import (
    AUDIO_DIR,
    BATCH_DIR,
    CLIP_DIR,
    GENERATED_DIR,
    RATE_LIMIT_ENABLED,
    STATIC_DIR,
    SYSTEM_CONFIG_PATH,
    UPLOAD_AUDIO_EXTS,
    UPLOAD_IMAGE_EXTS,
    UPLOAD_RATE_MAX,
    UPLOAD_RATE_WINDOW_SEC,
    UPLOAD_VIDEO_EXTS,
    UPLOAD_DIR,
    batch_gen,
    db,
    img_gen,
    rate_limiter,
)


def create_thumbnail(image_path: str):
    try:
        if not os.path.exists(image_path):
            return None
        base, _ = os.path.splitext(image_path)
        thumb_path = f"{base}.thumb.jpg"
        if os.path.exists(thumb_path):
            return thumb_path
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((400, 400))
            img.save(thumb_path, "JPEG", quality=70)
            return thumb_path
    except Exception as e:
        print(f"Error thumbnail: {e}")
        return None


def scan_and_sync_db():
    """后台任务：扫描文件夹，生成缩略图，同步DB"""
    print("🔄 Syncing files and database...")

    # 1. 扫描并生成缩略图
    files = glob.glob(os.path.join(GENERATED_DIR, "*.png"))
    for f in files:
        base, _ = os.path.splitext(f)
        thumb_path = f"{base}.thumb.jpg"
        if not os.path.exists(thumb_path):
            create_thumbnail(f)

    # 2. 恢复 Metadata 到 DB (从 JSON)
    json_files = glob.glob(os.path.join(GENERATED_DIR, "*.json"))
    restored_count = 0

    try:
        conn = db._get_conn()
        cursor = conn.cursor()

        # 获取所有已存在的 filenames
        cursor.execute("SELECT filename FROM images")
        existing_filenames = set(row[0] for row in cursor.fetchall())

        for jf in json_files:
            try:
                # 文件名: abc.json -> abc.png
                base_name = os.path.splitext(os.path.basename(jf))[0]
                image_filename = f"{base_name}.png"

                if image_filename in existing_filenames:
                    continue

                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                prompt = data.get("prompt", "")
                subject = data.get("subject", "general")
                grade = data.get("grade", "general")
                featured = data.get("featured", False)
                timestamp = data.get("timestamp", time.time())

                cursor.execute(
                    "INSERT INTO images (user_id, filename, prompt, subject, grade, timestamp, featured, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (None, image_filename, prompt, subject, grade, timestamp, featured, json.dumps(data)),
                )
                restored_count += 1

            except Exception:
                pass

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"DB Sync Error: {e}")

    if restored_count > 0:
        print(f"✅ Restored {restored_count} images from metadata.")
    else:
        print("✅ Sync complete (No new metadata restored).")


def sanitize_filename(text: str) -> str:
    clean_text = text.replace(" ", "_")
    clean_text = re.sub(r'[\\/:*?"<>|]', "", clean_text)
    return clean_text[:50]


def _is_private_host(host: Optional[str]) -> bool:
    if not host:
        return True
    host = host.strip().lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True
    if host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def _ensure_public_url(url: str, label: str):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail=f"{label} must be a public http(s) URL.")
    parsed = urlparse(url)
    if not parsed.hostname or _is_private_host(parsed.hostname):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label} must be publicly accessible. "
                "Set EXTERNAL_BASE_URL to a public domain or use a public URL."
            ),
        )


def _load_system_config() -> Dict:
    try:
        if os.path.exists(SYSTEM_CONFIG_PATH):
            with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Config load error: {e}")
    return {}


def _save_system_config(config: Dict):
    try:
        with open(SYSTEM_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Config save error: {e}")


def _get_system_config_with_env() -> Dict:
    cfg = _load_system_config()
    if not isinstance(cfg, dict):
        cfg = {}
    cfg.setdefault("auth", {})
    cfg.setdefault("api", {})
    cfg.setdefault("tts", {})
    cfg.setdefault("video", {})

    img_key = get_env_str("IMAGE_API_KEY")
    if img_key:
        cfg["auth"]["api_key"] = img_key
    img_backups = get_env_list("IMAGE_BACKUP_KEYS")
    if img_backups is not None:
        cfg["auth"]["backup_keys"] = img_backups
    img_base = get_env_str("IMAGE_BASE_URL")
    if img_base:
        cfg["api"]["base_url"] = img_base

    tts_key = get_env_str("TTS_API_KEY")
    if tts_key:
        cfg["tts"]["api_key"] = tts_key
    tts_backups = get_env_list("TTS_BACKUP_KEYS")
    if tts_backups is not None:
        cfg["tts"]["backup_keys"] = tts_backups
    tts_base = get_env_str("TTS_BASE_URL")
    if tts_base:
        cfg["tts"]["base_url"] = tts_base

    video_key = get_env_str("VIDEO_API_KEY")
    if video_key:
        cfg["video"]["api_key"] = video_key
    video_backups = get_env_list("VIDEO_BACKUP_KEYS")
    if video_backups is not None:
        cfg["video"]["backup_keys"] = video_backups
    video_base = get_env_str("VIDEO_BASE_URL")
    if video_base:
        cfg["video"]["base_url"] = video_base

    key_pools_cfg = cfg.get("key_pools")
    if key_pools_cfg:
        cfg["key_pools"] = normalize_key_pools(key_pools_cfg)
    else:
        env_key_pools = os.getenv("KEY_POOLS", "").strip()
        if env_key_pools:
            cfg["key_pools"] = normalize_key_pools(env_key_pools)

    return cfg


def _get_tts_config() -> Dict:
    cfg = _get_system_config_with_env()
    return cfg.get("tts", {}) or {}


def _get_key_pools() -> List[Dict]:
    cfg = _get_system_config_with_env()
    return normalize_key_pools(cfg.get("key_pools") or [])


def _coerce_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("false", "0", "no", "off"):
        return False
    if text in ("true", "1", "yes", "on"):
        return True
    return default


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        parsed = int(value)
        return parsed
    except Exception:
        return default


def _normalize_model_platform(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if text in ("向量", "vector", "vectorengine"):
        return "vector"
    if text in ("阿里", "百炼", "bailian", "aliyun", "dashscope"):
        return "bailian"
    if text in ("火山", "方舟", "ark", "volc", "volcengine"):
        return "ark"
    return text


def _infer_platform_from_base_url(base_url: str, hint: str = "") -> str:
    platform = _normalize_model_platform(hint)
    if platform in ("vector", "bailian", "ark"):
        return platform
    text = (base_url or "").strip().lower()
    if "vectorengine.ai" in text:
        return "vector"
    if "dashscope.aliyuncs.com" in text:
        return "bailian"
    if "ark.cn-beijing" in text or "volcengine" in text:
        return "ark"
    return platform or ""


def normalize_model_catalog(raw: Any) -> List[Dict[str, Any]]:
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if isinstance(data, dict):
        data = data.get("models") or data.get("model_catalog") or data.get("catalog") or []
    if not isinstance(data, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model = str(item.get("model") or item.get("id") or item.get("value") or "").strip()
        if not model:
            continue
        label = str(item.get("label") or item.get("name") or model).strip()
        service = str(item.get("service") or item.get("type") or "").strip().lower()
        if service not in ("image", "video", "audio", "digital_human"):
            continue
        platform = _normalize_model_platform(item.get("platform") or item.get("provider"))
        base_url = str(item.get("base_url") or "").strip()
        if not base_url and platform in MODEL_PLATFORM_BASE_URLS:
            base_url = MODEL_PLATFORM_BASE_URLS[platform]
        api_key = str(item.get("api_key") or item.get("key") or "").strip()
        backup_keys = normalize_key_list(
            item.get("backup_keys")
            or item.get("backupKeys")
            or item.get("backup")
            or []
        )
        if api_key and api_key in backup_keys:
            backup_keys = [k for k in backup_keys if k != api_key]
        cost = _coerce_int(item.get("cost"))
        priority = _coerce_int(item.get("priority"), 100)
        enabled = _coerce_bool(item.get("enabled"), True)
        normalized.append({
            "model": model,
            "label": label or model,
            "service": service,
            "platform": platform,
            "base_url": base_url or None,
            "api_key": api_key,
            "backup_keys": backup_keys,
            "cost": cost,
            "priority": priority,
            "enabled": enabled,
        })
    return normalized


def _get_model_catalog() -> List[Dict[str, Any]]:
    cfg = _get_system_config_with_env()
    catalog = normalize_model_catalog(cfg.get("models") or cfg.get("model_catalog") or [])
    if catalog:
        return catalog
    key_pools = normalize_key_pools(cfg.get("key_pools") or [])
    if not key_pools:
        return []
    derived: List[Dict[str, Any]] = []
    for pool in key_pools:
        models = pool.get("models") or []
        services = pool.get("services") or []
        if not models or not services:
            continue
        base_url = str(pool.get("base_url") or "").strip()
        platform = _infer_platform_from_base_url(base_url, pool.get("provider"))
        for service in services:
            service_name = str(service or "").strip().lower()
            if service_name not in ("image", "video", "audio", "digital_human"):
                continue
            for model in models:
                model_id = str(model or "").strip()
                if not model_id:
                    continue
                derived.append(
                    {
                        "model": model_id,
                        "label": model_id,
                        "service": service_name,
                        "platform": platform,
                        "base_url": base_url,
                        "api_key": str(pool.get("key") or "").strip(),
                        "backup_keys": normalize_key_list(pool.get("backup_keys") or []),
                        "priority": _coerce_int(pool.get("priority"), 100),
                        "enabled": _coerce_bool(pool.get("enabled"), True),
                    }
                )
    return normalize_model_catalog(derived)


def _select_model_config(service: str, model: Optional[str]) -> Optional[Dict[str, Any]]:
    matches = _select_model_configs(service, model)
    return matches[0] if matches else None


def _select_model_configs(service: str, model: Optional[str]) -> List[Dict[str, Any]]:
    if not service or not model:
        return []
    service = service.strip().lower()
    model_lower = str(model).strip().lower()
    matches: List[Dict[str, Any]] = []
    for item in _get_model_catalog():
        if not item.get("enabled", True):
            continue
        if item.get("service") != service:
            continue
        if str(item.get("model", "")).strip().lower() != model_lower:
            continue
        matches.append(item)
    matches.sort(key=lambda x: _coerce_int(x.get("priority"), 100))
    return matches


def _get_model_cost(service: str, model: Optional[str]) -> Optional[int]:
    for item in _select_model_configs(service, model):
        cost = item.get("cost")
        if isinstance(cost, int):
            return int(cost)
        parsed = _coerce_int(cost)
        if parsed is not None:
            return parsed
    return None


def _merge_candidates(primary: List[Dict], secondary: List[Dict]) -> List[Dict]:
    merged: List[Dict] = []
    seen = set()
    for candidate in primary + secondary:
        key = candidate.get("key") or ""
        base = candidate.get("base_url") or ""
        sig = f"{key}::{base}"
        if sig in seen:
            continue
        seen.add(sig)
        merged.append(candidate)
    return merged


def _build_model_candidates(
    service: str,
    model: Optional[str] = None,
    runtime_key: Optional[str] = None,
    runtime_base_url: Optional[str] = None,
    fallback_base_url: Optional[str] = None,
) -> List[Dict]:
    if runtime_key:
        return _build_service_candidates(
            service,
            model=model,
            runtime_key=runtime_key,
            runtime_base_url=runtime_base_url,
            fallback_base_url=fallback_base_url,
        )
    model_cfgs = _select_model_configs(service, model)
    preferred: List[Dict] = []
    preferred_base_url = runtime_base_url or fallback_base_url
    if not preferred_base_url:
        for cfg in model_cfgs:
            if cfg.get("base_url"):
                preferred_base_url = cfg.get("base_url")
                break
    for cfg in model_cfgs:
        base_url = cfg.get("base_url") or preferred_base_url
        keys = [cfg.get("api_key")] + (cfg.get("backup_keys") or [])
        seen_keys = set()
        for key in keys:
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            preferred.append({"key": key, "base_url": base_url})
    pool_candidates = _build_service_candidates(
        service,
        model=model,
        runtime_key=None,
        runtime_base_url=None,
        fallback_base_url=fallback_base_url,
    )
    if preferred_base_url:
        for candidate in pool_candidates:
            if not candidate.get("base_url"):
                candidate["base_url"] = preferred_base_url
    return _merge_candidates(preferred, pool_candidates)


def _get_default_model(service: str, fallback: Optional[str] = None) -> Optional[str]:
    service = (service or "").strip().lower()
    candidates = [item for item in _get_model_catalog() if item.get("enabled", True) and item.get("service") == service]
    if not candidates:
        return fallback
    candidates.sort(key=lambda x: _coerce_int(x.get("priority"), 100))
    model = candidates[0].get("model")
    return model or fallback


def _select_service_key_pools(service: str, model: Optional[str] = None) -> List[Dict]:
    pools = _get_key_pools()
    return select_key_pools(pools, service, model)


def _build_service_candidates(
    service: str,
    model: Optional[str] = None,
    runtime_key: Optional[str] = None,
    runtime_base_url: Optional[str] = None,
    fallback_base_url: Optional[str] = None,
) -> List[Dict]:
    if runtime_key:
        return [{"key": runtime_key, "base_url": runtime_base_url}]
    pools = _select_service_key_pools(service, model)
    if pools:
        candidates: List[Dict] = []
        for pool in pools:
            base_url = pool.get("base_url")
            keys = [pool.get("key")] + (pool.get("backup_keys") or [])
            seen = set()
            for key in keys:
                if not key or key in seen:
                    continue
                seen.add(key)
                candidates.append({"key": key, "base_url": base_url})
        if candidates:
            return candidates
    return [{"key": None, "base_url": runtime_base_url or fallback_base_url}]


def _get_tts_keys() -> List[str]:
    tts_cfg = _get_tts_config()
    primary = tts_cfg.get("api_key", "")
    backups = normalize_key_list(tts_cfg.get("backup_keys", []))
    return [k for k in [primary] + backups if k]


def _get_tts_base_url() -> Optional[str]:
    tts_cfg = _get_tts_config()
    base_url = tts_cfg.get("base_url")
    return base_url.strip() if isinstance(base_url, str) and base_url.strip() else None


def _get_video_config() -> Dict:
    cfg = _get_system_config_with_env()
    video_cfg = cfg.get("video", {}) or {}
    tts_cfg = cfg.get("tts", {}) or {}

    merged = dict(tts_cfg) if isinstance(tts_cfg, dict) else {}

    if isinstance(video_cfg, dict):
        api_key = video_cfg.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            merged["api_key"] = api_key
        backups = video_cfg.get("backup_keys")
        if backups:
            merged["backup_keys"] = backups
        base_url = video_cfg.get("base_url")
        if isinstance(base_url, str) and base_url.strip():
            merged["base_url"] = base_url

    return merged


def _get_video_keys() -> List[str]:
    video_cfg = _get_video_config()
    primary = video_cfg.get("api_key", "")
    backups = normalize_key_list(video_cfg.get("backup_keys", []))
    return [k for k in [primary] + backups if k]


def _get_video_base_url() -> Optional[str]:
    video_cfg = _get_video_config()
    base_url = video_cfg.get("base_url")
    return base_url.strip() if isinstance(base_url, str) and base_url.strip() else None


def _get_video_credit_cost(model: Optional[str]) -> int:
    catalog_cost = _get_model_cost("video", model)
    if isinstance(catalog_cost, int):
        return catalog_cost
    text = (model or "").strip().lower()
    if "veo" in text:
        return 10
    if "sora" in text:
        return 10
    if "doubao" in text or "seedance" in text:
        return 5
    return 5


def _safe_log_payload(payload: Any, max_len: int = 1200) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except Exception:
        text = str(payload)
    if len(text) > max_len:
        return f"{text[:max_len]}...<truncated>"
    return text


def _normalize_video_status(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return "processing"
    if payload.get("error"):
        return "failed"
    status_code = payload.get("status_code")
    if isinstance(status_code, int) and status_code >= 400:
        return "failed"
    raw_status = VideoGenerator._extract_value(payload, ["status", "state", "Status", "State"])
    if raw_status:
        text = str(raw_status).strip().upper()
        if text in ("PENDING", "QUEUED", "RUNNING"):
            return "processing"
        if text in ("SUCCEEDED", "SUCCESS", "DONE", "COMPLETED"):
            return "done"
        if text in ("FAILED", "ERROR", "CANCELED", "CANCELLED"):
            return "failed"
    if payload.get("done") is True:
        return "done"
    if "done" in payload:
        return "processing"
    return "processing"


def _has_system_image_key() -> bool:
    if _select_service_key_pools("image"):
        return True
    if img_gen.api_keys:
        return True
    if getattr(img_gen, "special_keys", None):
        return bool(img_gen.special_keys)
    if getattr(img_gen, "model_key_map", None):
        return bool(img_gen.model_key_map)
    for item in _get_model_catalog():
        if item.get("service") == "image" and (item.get("api_key") or item.get("backup_keys")):
            return True
    return False


def determine_execution_mode(current_user: Optional[Dict], x_model_key: Optional[str], cost: int = 1):
    if x_model_key:
        return "user", x_model_key, None

    if not current_user:
        raise HTTPException(status_code=401, detail="Login required or provide x-model-key.")

    if not _has_system_image_key():
        raise HTTPException(status_code=403, detail="系统未配置API Key，请联系管理员。")

    if current_user:
        user = db.get_user_by_id(current_user["id"])
        if user["quota_used"] + cost > user["quota_limit"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Quota exceeded (Cost: {cost}, Remaining: "
                    f"{user['quota_limit'] - user['quota_used']}). Please provide Custom API Key."
                ),
            )

    return "system", None, None


def determine_key_execution_mode(current_user: Optional[Dict], provided_key: Optional[str], cost: int, header_name: str):
    if provided_key:
        return "user", provided_key
    if current_user:
        user = db.get_user_by_id(current_user["id"])
        if user["quota_used"] + cost <= user["quota_limit"]:
            return "system", None
        raise HTTPException(
            status_code=403,
            detail=(
                f"Quota exceeded (Cost: {cost}, Remaining: "
                f"{user['quota_limit'] - user['quota_used']}). Please provide Custom API Key."
            ),
        )
    raise HTTPException(status_code=401, detail=f"Login required or provide {header_name}.")


def _get_wav_duration_seconds(path: str) -> Optional[float]:
    try:
        if not path or not os.path.exists(path):
            return None
        if not path.lower().endswith(".wav"):
            return None
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate <= 0:
                return None
            return frames / float(rate)
    except Exception:
        return None


def _resolve_local_audio_path(audio_url: str) -> Optional[str]:
    if not audio_url:
        return None
    if audio_url.startswith("/static/audio/"):
        filename = unquote(os.path.basename(audio_url))
        return os.path.join(AUDIO_DIR, filename)
    if audio_url.startswith("/static/uploads/"):
        filename = unquote(os.path.basename(audio_url))
        return os.path.join(UPLOAD_DIR, filename)
    return None


def _get_client_ip(request: Request) -> str:
    try:
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
        if forwarded:
            return forwarded.split(",")[0].strip()
    except Exception:
        pass
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request, current_user: Optional[Dict]):
    if not RATE_LIMIT_ENABLED:
        return
    if current_user is not None:
        return
    ip = _get_client_ip(request)
    allowed, reason = rate_limiter.check_limit(ip)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)
    rate_limiter.record_usage(ip)


def _enforce_upload_rate_limit(request: Request):
    ip = _get_client_ip(request)
    allowed, remaining = rate_limiter.check_upload_limit(ip, UPLOAD_RATE_WINDOW_SEC, UPLOAD_RATE_MAX)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"上传过于频繁，请 {remaining} 秒后再试。")
    rate_limiter.record_upload(ip)


def _get_upload_size(upload: UploadFile) -> Optional[int]:
    try:
        file_obj = upload.file
        if hasattr(file_obj, "seek") and hasattr(file_obj, "tell"):
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(0)
            return size
    except Exception:
        return None
    return None


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _safe_static_path(static_subpath: str) -> Optional[str]:
    if not static_subpath:
        return None
    rel_path = unquote(static_subpath).lstrip("/")
    rel_path = os.path.normpath(rel_path)
    if rel_path.startswith(".."):
        return None
    return os.path.join(STATIC_DIR, rel_path)


def _resolve_clip_asset_path(path: str) -> Optional[str]:
    if not path:
        return None
    raw = str(path).strip()
    if not raw:
        return None
    if raw.startswith("/static/"):
        local = _safe_static_path(raw[len("/static/"):])
        return local if local and os.path.exists(local) else None
    if raw.startswith("backend/static/"):
        raw = raw[len("backend/"):]
    if raw.startswith("static/"):
        local = _safe_static_path(raw[len("static/"):])
        return local if local and os.path.exists(local) else None
    if not os.path.isabs(raw):
        local = os.path.join(STATIC_DIR, raw)
        return local if os.path.exists(local) else None
    abs_path = os.path.abspath(raw)
    static_root = os.path.abspath(STATIC_DIR)
    if abs_path.startswith(static_root + os.sep) and os.path.exists(abs_path):
        return abs_path
    return None


def _resolve_reference_image_path(ref_url: str) -> Optional[str]:
    if not ref_url:
        return None
    if ref_url.startswith("/static/"):
        local_path = _safe_static_path(ref_url[len("/static/"):])
        if local_path and os.path.exists(local_path):
            return local_path
        return None
    if os.path.exists(ref_url):
        return ref_url
    return None


def _save_reference_bytes(data: bytes, ext: str) -> Optional[str]:
    if not data:
        return None
    safe_ext = ext if ext and ext.startswith(".") else ".png"
    filename = f"ref_{int(time.time())}_{secrets.token_hex(4)}{safe_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    try:
        with open(file_path, "wb") as f:
            f.write(data)
        return file_path
    except Exception:
        return None


def _download_reference_image(ref_url: str) -> Optional[str]:
    if not ref_url:
        return None
    if ref_url.startswith("data:image"):
        try:
            header, encoded = ref_url.split(",", 1)
            data = base64.b64decode(encoded)
            mime_type = None
            if header.startswith("data:"):
                mime_type = header.split(";", 1)[0].split(":", 1)[-1]
            ext = mimetypes.guess_extension(mime_type or "image/png") or ".png"
            return _save_reference_bytes(data, ext)
        except Exception:
            return None
    if ref_url.startswith("http://") or ref_url.startswith("https://"):
        try:
            response = requests.get(ref_url, timeout=15)
            if response.status_code != 200:
                return None
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                return None
            parsed = urlparse(ref_url)
            ext = os.path.splitext(parsed.path)[1]
            if not ext:
                ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".png"
            return _save_reference_bytes(response.content, ext)
        except Exception:
            return None
    return None


def _download_public_image_bytes(image_url: str) -> Optional[Dict[str, Any]]:
    if not image_url:
        return None
    if image_url.startswith("data:image"):
        try:
            header, encoded = image_url.split(",", 1)
            data = base64.b64decode(encoded)
            mime_type = None
            if header.startswith("data:"):
                mime_type = header.split(";", 1)[0].split(":", 1)[-1]
            return {"bytes": data, "mime_type": mime_type or "image/png"}
        except Exception:
            return None
    if image_url.startswith("/static/"):
        local_path = _safe_static_path(image_url[len("/static/"):])
        if local_path and os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    data = f.read()
                mime_type = mimetypes.guess_type(local_path)[0] or "image/png"
                return {"bytes": data, "mime_type": mime_type}
            except Exception:
                return None
    if os.path.exists(image_url):
        try:
            with open(image_url, "rb") as f:
                data = f.read()
            mime_type = mimetypes.guess_type(image_url)[0] or "image/png"
            return {"bytes": data, "mime_type": mime_type}
        except Exception:
            return None
    if image_url.startswith("http://") or image_url.startswith("https://"):
        try:
            response = requests.get(image_url, timeout=20)
            if response.status_code != 200:
                return None
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip()
            if content_type and not content_type.startswith("image/"):
                return None
            return {"bytes": response.content, "mime_type": content_type or "image/png"}
        except Exception:
            return None
    return None
