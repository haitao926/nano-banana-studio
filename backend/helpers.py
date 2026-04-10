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
from core.oss_uploader import upload_path_to_oss

MODEL_PLATFORM_BASE_URLS = {
    "vector": "https://api.vectorengine.ai",
    "bailian": "https://dashscope.aliyuncs.com/api/v1",
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
}
PROMPT_CHANNEL_KEYS = ("google", "bytedance", "aliyun")
DEFAULT_PROMPT_CHANNEL_MODELS = {
    "google": ["gemini-3.1-pro-preview", "claude-sonnet-4-6", "MiniMax-M2.7"],
    "bytedance": ["gemini-3.1-pro-preview", "claude-sonnet-4-6", "MiniMax-M2.7"],
    "aliyun": ["gemini-3.1-pro-preview", "claude-sonnet-4-6", "MiniMax-M2.7"],
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

    _sanitize_generated_filenames()

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
    clean_text = (text or "").strip()
    if not clean_text:
        return "image"
    clean_text = re.sub(r"\s+", "_", clean_text)
    clean_text = re.sub(r'[\\/:*?"<>|]', "", clean_text)
    clean_text = re.sub(r"[\u0000-\u001f]", "", clean_text)
    clean_text = re.sub(r"_+", "_", clean_text).strip("_")
    return clean_text[:50] or "image"


def _sanitize_existing_basename(name: str) -> str:
    clean_text = (name or "").strip()
    if not clean_text:
        return "image"
    clean_text = re.sub(r"\s+", "_", clean_text)
    clean_text = re.sub(r'[\\/:*?"<>|]', "", clean_text)
    clean_text = re.sub(r"[\u0000-\u001f]", "", clean_text)
    clean_text = re.sub(r"_+", "_", clean_text).strip("_")
    return clean_text or "image"


def _ensure_unique_generated_name(filename: str) -> str:
    if not os.path.exists(os.path.join(GENERATED_DIR, filename)):
        return filename
    base, ext = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = f"{base}_{counter}{ext}"
        if not os.path.exists(os.path.join(GENERATED_DIR, candidate)):
            return candidate
        counter += 1


def _sanitize_generated_filenames():
    try:
        entries = os.listdir(GENERATED_DIR)
    except Exception as e:
        print(f"Error reading generated dir: {e}")
        return
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    for filename in entries:
        if not filename or filename.startswith("."):
            continue
        if filename.endswith(".thumb.jpg") or filename.endswith(".json"):
            continue
        base, ext = os.path.splitext(filename)
        if ext.lower() not in image_exts:
            continue
        safe_base = _sanitize_existing_basename(base)
        if safe_base == base:
            continue
        new_filename = _ensure_unique_generated_name(f"{safe_base}{ext}")
        old_path = os.path.join(GENERATED_DIR, filename)
        new_path = os.path.join(GENERATED_DIR, new_filename)
        try:
            os.rename(old_path, new_path)
        except Exception as e:
            print(f"Rename failed: {filename} -> {new_filename}, {e}")
            continue

        old_thumb = os.path.join(GENERATED_DIR, f"{base}.thumb.jpg")
        new_thumb = os.path.join(GENERATED_DIR, f"{os.path.splitext(new_filename)[0]}.thumb.jpg")
        if os.path.exists(old_thumb):
            try:
                os.rename(old_thumb, new_thumb)
            except Exception as e:
                print(f"Rename thumb failed: {old_thumb} -> {new_thumb}, {e}")

        old_json = os.path.join(GENERATED_DIR, f"{base}.json")
        new_json = os.path.join(GENERATED_DIR, f"{os.path.splitext(new_filename)[0]}.json")
        if os.path.exists(old_json):
            try:
                os.rename(old_json, new_json)
            except Exception as e:
                print(f"Rename json failed: {old_json} -> {new_json}, {e}")

        try:
            conn = db._get_conn()
            conn.execute("UPDATE images SET filename = ? WHERE filename = ?", (new_filename, filename))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB filename update failed: {filename} -> {new_filename}, {e}")


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
    if url.startswith("oss://"):
        return
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail=f"{label} must be a public http(s) URL.")
    parsed = urlparse(url)
    if not parsed.hostname or _is_private_host(parsed.hostname):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label} must be publicly accessible. "
                "Set EXTERNAL_BASE_URL to a public domain, "
                "or upload via /api/upload_public (OSS/public URL)."
            ),
        )


def _resolve_oss_url(url: str, expires: int = 3600) -> str:
    if not url or not url.startswith("oss://"):
        return url

    parsed = urlparse(url)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        return url

    public_base = os.getenv("OSS_PUBLIC_BASE_URL", "").strip()
    endpoint = os.getenv("OSS_ENDPOINT", "").strip()
    access_key_id = os.getenv("OSS_ACCESS_KEY_ID", "").strip()
    access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "").strip()

    def _normalize_endpoint(endpoint_value: str) -> str:
        value = endpoint_value.strip()
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return f"https://{value}"

    normalized_endpoint = _normalize_endpoint(endpoint)

    if normalized_endpoint and access_key_id and access_key_secret:
        try:
            import oss2

            auth = oss2.Auth(access_key_id, access_key_secret)
            bucket_obj = oss2.Bucket(auth, normalized_endpoint, bucket)
            return bucket_obj.sign_url("GET", key, expires)
        except Exception:
            pass

    if public_base:
        return f"{public_base.rstrip('/')}/{key}"

    if normalized_endpoint:
        parsed_endpoint = urlparse(normalized_endpoint)
        host = parsed_endpoint.netloc or parsed_endpoint.path
        scheme = parsed_endpoint.scheme or "https"
        if host:
            return f"{scheme}://{bucket}.{host}/{key}"

    return url


def _resolve_public_media_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("oss://"):
        return _resolve_oss_url(url)
    if url.startswith(("http://", "https://")):
        parsed = urlparse(url)
        host = (parsed.hostname or "").strip().lower()
        # Local absolute URLs (e.g. http://localhost:8000/static/...) are not
        # reachable by upstream providers. Treat them like /static paths so we
        # can upload to OSS and return a public URL.
        if _is_private_host(host):
            path = parsed.path or ""
            if path.startswith("/static/") or path.startswith("static/"):
                url = path
            else:
                return url
        else:
            return url
    if url.startswith("/static/") or url.startswith("static/"):
        if url.startswith("/static/"):
            relative_path = url[len("/static/"):]
        else:
            relative_path = url[len("static/"):]
        safe_relative = os.path.normpath(unquote(relative_path).lstrip("/"))
        if safe_relative.startswith(".."):
            return url
        local_path = os.path.abspath(os.path.join(STATIC_DIR, safe_relative))
        static_root = os.path.abspath(STATIC_DIR)
        if local_path != static_root and not local_path.startswith(f"{static_root}{os.sep}"):
            return url
        if os.path.exists(local_path):
            content_type, _ = mimetypes.guess_type(local_path)
            try:
                return upload_path_to_oss(local_path, content_type or "")
            except Exception:
                return url
    return url


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
    cfg = _merge_explicit_config(cfg)
    cfg["prompt_channels"] = normalize_prompt_channels(
        cfg.get("prompt_channels"),
        normalize_model_catalog(cfg.get("model_catalog") or cfg.get("models") or []),
    )

    return cfg


def _get_tts_config() -> Dict:
    cfg = _get_system_config_with_env()
    return cfg.get("tts", {}) or {}


def _get_image_config() -> Dict:
    cfg = _get_system_config_with_env()
    auth_cfg = cfg.get("auth", {}) or {}
    api_cfg = cfg.get("api", {}) or {}
    return {
        "api_key": auth_cfg.get("api_key", ""),
        "backup_keys": normalize_key_list(auth_cfg.get("backup_keys", [])),
        "base_url": api_cfg.get("base_url", ""),
    }


def _get_image_keys() -> List[str]:
    image_cfg = _get_image_config()
    primary = image_cfg.get("api_key", "")
    backups = normalize_key_list(image_cfg.get("backup_keys", []))
    return [k for k in [primary] + backups if k]


def _get_image_base_url() -> Optional[str]:
    image_cfg = _get_image_config()
    base_url = image_cfg.get("base_url")
    return base_url.strip() if isinstance(base_url, str) and base_url.strip() else None


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


def _normalize_prompt_channel_name(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    if text == "byte":
        return "bytedance"
    if text in PROMPT_CHANNEL_KEYS:
        return text
    return None


def _normalize_prompt_channel_models(value: Any, fallback: List[str]) -> List[str]:
    if isinstance(value, str):
        raw_items = [v.strip() for v in re.split(r"[\\n,;]+", value) if v.strip()]
    elif isinstance(value, list):
        raw_items = [str(v).strip() for v in value if str(v).strip()]
    else:
        raw_items = []
    ordered = raw_items or list(fallback)
    seen = set()
    models: List[str] = []
    for model in ordered:
        if not model or model in seen:
            continue
        seen.add(model)
        models.append(model)
    return models


def _filter_prompt_channel_models(models: List[str], allowed_models: List[str]) -> List[str]:
    if not allowed_models:
        return models
    allowed = {str(model or "").strip().lower() for model in allowed_models if str(model or "").strip()}
    if not allowed:
        return models
    filtered: List[str] = []
    seen = set()
    for model in models:
        text = str(model or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered not in allowed or lowered in seen:
            continue
        seen.add(lowered)
        filtered.append(text)
    return filtered


def normalize_prompt_channels(raw: Any, prompt_model_catalog: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    prompt_models = []
    if prompt_model_catalog:
        prompt_models = [
            str(item.get("model") or "").strip()
            for item in prompt_model_catalog
            if str(item.get("service") or "").strip().lower() == "prompt"
        ]
    prompt_models = [model for model in prompt_models if model]

    def _normalize_models(value: Any, fallback_models: List[str]) -> List[str]:
        normalized = _normalize_prompt_channel_models(value, fallback_models)
        filtered = _filter_prompt_channel_models(normalized, prompt_models)
        if filtered:
            return filtered
        return _filter_prompt_channel_models(fallback_models, prompt_models) or normalized

    normalized_input: Dict[str, Dict[str, Any]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            channel = _normalize_prompt_channel_name(key)
            if not channel:
                continue
            if hasattr(value, "model_dump"):
                payload = value.model_dump()
            elif hasattr(value, "dict"):
                payload = value.dict()
            elif isinstance(value, dict):
                payload = value
            else:
                payload = {}
            fallback_models = prompt_models or (DEFAULT_PROMPT_CHANNEL_MODELS.get(channel) or [])
            normalized_input[channel] = {
                "enabled": _coerce_bool(payload.get("enabled"), True),
                "models": _normalize_models(payload.get("models"), fallback_models),
            }

    result: Dict[str, Dict[str, Any]] = {}
    for channel in PROMPT_CHANNEL_KEYS:
        fallback_models = prompt_models or (DEFAULT_PROMPT_CHANNEL_MODELS.get(channel) or [])
        payload = normalized_input.get(channel) or {}
        result[channel] = {
            "enabled": _coerce_bool(payload.get("enabled"), True),
            "models": _normalize_models(payload.get("models"), fallback_models),
        }
    return result


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
        if service not in ("image", "video", "audio", "digital_human", "prompt"):
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
            "enabled": enabled,
        })
    return normalized


def _normalize_service_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("image", "video", "audio", "digital_human", "prompt"):
        return text
    return "image"


def _slug_identifier(value: str, fallback: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return text or fallback


def _generate_credential_id(
    label: str,
    service: str,
    scope: str,
    seen: Optional[set[str]] = None,
    provider: str = "",
) -> str:
    base = _slug_identifier(label or f"{scope}_{service}_{provider or 'credential'}", f"{scope}_{service}")
    candidate = base
    suffix = 2
    seen = seen or set()
    while candidate in seen:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def normalize_credentials(raw: Any, scope: str = "system") -> List[Dict[str, Any]]:
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if isinstance(data, dict):
        data = data.get("credentials") or data.get("items") or []
    if not isinstance(data, list):
        return []

    normalized: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    normalized_scope = "personal" if str(scope or "").strip().lower() == "personal" else "system"
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        service = _normalize_service_name(item.get("service"))
        provider = _normalize_model_platform(item.get("provider"))
        label = str(item.get("label") or item.get("name") or item.get("title") or "").strip()
        base_url = str(item.get("base_url") or "").strip() or None
        primary_secret = str(
            item.get("primary_secret")
            or item.get("primarySecret")
            or item.get("key")
            or item.get("api_key")
            or ""
        ).strip()
        backup_secrets = normalize_key_list(
            item.get("backup_secrets")
            or item.get("backupSecrets")
            or item.get("backup_keys")
            or []
        )
        if primary_secret and primary_secret in backup_secrets:
            backup_secrets = [secret for secret in backup_secrets if secret != primary_secret]
        if not primary_secret and not backup_secrets:
            continue
        cred_id = str(item.get("id") or item.get("credential_id") or "").strip()
        if not cred_id:
            seed_label = label or f"{normalized_scope}_{service}_{provider or index + 1}"
            cred_id = _generate_credential_id(seed_label, service, normalized_scope, seen_ids, provider)
        if cred_id in seen_ids:
            cred_id = _generate_credential_id(cred_id, service, normalized_scope, seen_ids, provider)
        seen_ids.add(cred_id)
        normalized.append({
            "id": cred_id,
            "label": label or f"{service.upper()} Credential {len(normalized) + 1}",
            "scope": normalized_scope,
            "service": service,
            "provider": provider,
            "base_url": base_url,
            "primary_secret": primary_secret,
            "backup_secrets": backup_secrets,
            "enabled": _coerce_bool(item.get("enabled"), True),
        })
    return normalized


def normalize_model_routes(raw: Any, credentials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if isinstance(data, dict):
        data = data.get("model_routes") or data.get("routes") or []
    if not isinstance(data, list):
        return []

    valid_ids = {str(item.get("id") or "").strip() for item in credentials if str(item.get("id") or "").strip()}
    normalized: List[Dict[str, Any]] = []
    seen_models = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or item.get("model") or item.get("id") or "").strip()
        if not model_id or model_id in seen_models:
            continue
        primary_credential_id = str(item.get("primary_credential_id") or item.get("primaryCredentialId") or "").strip()
        if primary_credential_id and primary_credential_id not in valid_ids:
            primary_credential_id = ""
        fallback_credential_ids = [
            cred_id
            for cred_id in normalize_key_list(
                item.get("fallback_credential_ids") or item.get("fallbackCredentialIds") or []
            )
            if cred_id in valid_ids and cred_id != primary_credential_id
        ]
        seen_models.add(model_id)
        normalized.append({
            "model_id": model_id,
            "primary_credential_id": primary_credential_id or None,
            "fallback_credential_ids": _dedupe_preserve_order(fallback_credential_ids),
            "allow_personal_override": _coerce_bool(item.get("allow_personal_override"), True),
            "enabled": _coerce_bool(item.get("enabled"), True),
        })
    return normalized


def normalize_service_routes(raw: Any, credentials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if isinstance(data, dict):
        data = data.get("service_routes") or data.get("routes") or []
    if not isinstance(data, list):
        return []

    valid_ids = {str(item.get("id") or "").strip() for item in credentials if str(item.get("id") or "").strip()}
    normalized: List[Dict[str, Any]] = []
    seen_services = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        service = _normalize_service_name(item.get("service"))
        if service in seen_services:
            continue
        primary_credential_id = str(item.get("primary_credential_id") or item.get("primaryCredentialId") or "").strip()
        if primary_credential_id and primary_credential_id not in valid_ids:
            primary_credential_id = ""
        fallback_credential_ids = [
            cred_id
            for cred_id in normalize_key_list(
                item.get("fallback_credential_ids") or item.get("fallbackCredentialIds") or []
            )
            if cred_id in valid_ids and cred_id != primary_credential_id
        ]
        seen_services.add(service)
        normalized.append({
            "service": service,
            "primary_credential_id": primary_credential_id or None,
            "fallback_credential_ids": _dedupe_preserve_order(fallback_credential_ids),
        })
    return normalized


def _expand_credential_candidates(credential: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not credential or credential.get("enabled") is False:
        return []
    keys = [credential.get("primary_secret")] + (credential.get("backup_secrets") or [])
    seen = set()
    candidates: List[Dict[str, Any]] = []
    for key in keys:
        key = str(key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "id": credential.get("id"),
                "label": credential.get("label"),
                "key": key,
                "base_url": credential.get("base_url"),
                "platform": credential.get("provider") or None,
            }
        )
    return candidates


def _append_route_credential(target: List[str], credential_id: Optional[str]) -> None:
    cred_id = str(credential_id or "").strip()
    if cred_id and cred_id not in target:
        target.append(cred_id)


def _merge_explicit_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    next_cfg = dict(cfg or {})
    model_catalog = normalize_model_catalog(next_cfg.get("model_catalog") or next_cfg.get("models") or [])
    credentials = normalize_credentials(next_cfg.get("credentials") or [], scope="system")
    credential_map = {item["id"]: item for item in credentials}
    seen_ids = set(credential_map.keys())
    explicit_route_mode = any(
        key in next_cfg
        for key in ("credentials", "model_routes", "service_routes")
    )

    def add_credential(
        *,
        label: str,
        service: str,
        provider: str = "",
        base_url: Optional[str] = None,
        primary_secret: str = "",
        backup_secrets: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> Optional[str]:
        primary = str(primary_secret or "").strip()
        backups = normalize_key_list(backup_secrets or [])
        if primary and primary in backups:
            backups = [item for item in backups if item != primary]
        if not primary and not backups:
            return None
        cred_id = _generate_credential_id(label, service, "system", seen_ids, provider)
        seen_ids.add(cred_id)
        credential = {
            "id": cred_id,
            "label": label,
            "scope": "system",
            "service": _normalize_service_name(service),
            "provider": _normalize_model_platform(provider),
            "base_url": str(base_url or "").strip() or None,
            "primary_secret": primary,
            "backup_secrets": backups,
            "enabled": enabled is not False,
        }
        credentials.append(credential)
        credential_map[cred_id] = credential
        return cred_id

    model_route_candidates: Dict[str, List[str]] = {}
    model_route_allow: Dict[str, bool] = {}

    def route_list_for_model(model_id: str) -> List[str]:
        key = str(model_id or "").strip()
        if key not in model_route_candidates:
            model_route_candidates[key] = []
        return model_route_candidates[key]

    service_route_candidates: Dict[str, List[str]] = {}
    if not explicit_route_mode:
        for item in model_catalog:
            model_id = str(item.get("model") or "").strip()
            if not model_id:
                continue
            inline_cred_id = add_credential(
                label=f"{model_id} Inline Credential",
                service=item.get("service") or "image",
                provider=item.get("platform") or "",
                base_url=item.get("base_url"),
                primary_secret=item.get("api_key") or "",
                backup_secrets=item.get("backup_keys") or [],
                enabled=item.get("enabled", True),
            )
            if inline_cred_id:
                _append_route_credential(route_list_for_model(model_id), inline_cred_id)
            model_route_allow[model_id] = True

        legacy_pools = normalize_key_pools(next_cfg.get("key_pools") or [])
        catalog_by_service: Dict[str, List[Dict[str, Any]]] = {}
        for item in model_catalog:
            catalog_by_service.setdefault(_normalize_service_name(item.get("service")), []).append(item)

        for index, pool in enumerate(legacy_pools, start=1):
            service = _normalize_service_name((pool.get("services") or ["image"])[0] if isinstance(pool.get("services"), list) else pool.get("services"))
            provider = _normalize_model_platform(pool.get("provider"))
            cred_id = add_credential(
                label=f"Legacy {service.upper()} Credential {index}",
                service=service,
                provider=provider,
                base_url=pool.get("base_url"),
                primary_secret=pool.get("key") or "",
                backup_secrets=pool.get("backup_keys") or [],
                enabled=pool.get("enabled", True),
            )
            if not cred_id:
                continue
            pool_models = [str(model or "").strip() for model in (pool.get("models") or []) if str(model or "").strip()]
            if pool_models:
                for model_id in pool_models:
                    _append_route_credential(route_list_for_model(model_id), cred_id)
                    model_route_allow[model_id] = True
                continue
            if provider:
                for item in catalog_by_service.get(service, []):
                    model_id = str(item.get("model") or "").strip()
                    item_provider = _normalize_model_platform(item.get("platform"))
                    if model_id and (not item_provider or item_provider == provider):
                        _append_route_credential(route_list_for_model(model_id), cred_id)
                        model_route_allow[model_id] = True
                continue
            service_route_candidates.setdefault(service, [])
            _append_route_credential(service_route_candidates[service], cred_id)

        auth_cfg = next_cfg.get("auth", {}) or {}
        api_cfg = next_cfg.get("api", {}) or {}
        tts_cfg = next_cfg.get("tts", {}) or {}
        video_cfg = next_cfg.get("video", {}) or {}
        legacy_service_sources = [
            (
                "image",
                {
                    "api_key": auth_cfg.get("api_key", ""),
                    "backup_keys": normalize_key_list(auth_cfg.get("backup_keys", [])),
                    "base_url": api_cfg.get("base_url", ""),
                },
                "Legacy Image Default",
            ),
            (
                "audio",
                {
                    "api_key": tts_cfg.get("api_key", ""),
                    "backup_keys": normalize_key_list(tts_cfg.get("backup_keys", [])),
                    "base_url": tts_cfg.get("base_url", ""),
                },
                "Legacy Audio Default",
            ),
            (
                "video",
                {
                    "api_key": video_cfg.get("api_key", "") or tts_cfg.get("api_key", ""),
                    "backup_keys": normalize_key_list(video_cfg.get("backup_keys", []) or tts_cfg.get("backup_keys", [])),
                    "base_url": video_cfg.get("base_url", "") or tts_cfg.get("base_url", ""),
                },
                "Legacy Video Default",
            ),
        ]
        for service, payload, label in legacy_service_sources:
            cred_id = add_credential(
                label=label,
                service=service,
                base_url=payload.get("base_url"),
                primary_secret=payload.get("api_key") or "",
                backup_secrets=payload.get("backup_keys") or [],
                enabled=True,
            )
            if cred_id:
                service_route_candidates.setdefault(service, [])
                _append_route_credential(service_route_candidates[service], cred_id)

    model_routes = normalize_model_routes(next_cfg.get("model_routes") or [], credentials)
    route_map = {item["model_id"]: item for item in model_routes}
    if not explicit_route_mode:
        for model_id, candidate_ids in model_route_candidates.items():
            if not candidate_ids:
                continue
            existing = route_map.get(model_id)
            if existing:
                ordered_ids: List[str] = []
                _append_route_credential(ordered_ids, existing.get("primary_credential_id"))
                for cred_id in existing.get("fallback_credential_ids") or []:
                    _append_route_credential(ordered_ids, cred_id)
                for cred_id in candidate_ids:
                    _append_route_credential(ordered_ids, cred_id)
                existing["primary_credential_id"] = ordered_ids[0] if ordered_ids else None
                existing["fallback_credential_ids"] = ordered_ids[1:]
            else:
                route_map[model_id] = {
                    "model_id": model_id,
                    "primary_credential_id": candidate_ids[0] if candidate_ids else None,
                    "fallback_credential_ids": candidate_ids[1:],
                    "allow_personal_override": model_route_allow.get(model_id, True),
                    "enabled": True,
                }
    model_routes = list(route_map.values())

    service_routes = normalize_service_routes(next_cfg.get("service_routes") or [], credentials)
    service_route_map = {item["service"]: item for item in service_routes}
    if not explicit_route_mode:
        for service, candidate_ids in service_route_candidates.items():
            if not candidate_ids:
                continue
            existing = service_route_map.get(service)
            if existing:
                ordered_ids: List[str] = []
                _append_route_credential(ordered_ids, existing.get("primary_credential_id"))
                for cred_id in existing.get("fallback_credential_ids") or []:
                    _append_route_credential(ordered_ids, cred_id)
                for cred_id in candidate_ids:
                    _append_route_credential(ordered_ids, cred_id)
                existing["primary_credential_id"] = ordered_ids[0] if ordered_ids else None
                existing["fallback_credential_ids"] = ordered_ids[1:]
            else:
                service_route_map[service] = {
                    "service": service,
                    "primary_credential_id": candidate_ids[0] if candidate_ids else None,
                    "fallback_credential_ids": candidate_ids[1:],
                }
    service_routes = list(service_route_map.values())

    clean_model_catalog = []
    for item in model_catalog:
        clean_item = dict(item)
        clean_item["api_key"] = ""
        clean_item["backup_keys"] = []
        clean_model_catalog.append(clean_item)

    next_cfg["credentials"] = credentials
    next_cfg["model_catalog"] = clean_model_catalog
    next_cfg["model_routes"] = model_routes
    next_cfg["service_routes"] = service_routes
    return next_cfg


def _get_credentials(scope: str = "system") -> List[Dict[str, Any]]:
    cfg = _get_system_config_with_env()
    return normalize_credentials(cfg.get("credentials") or [], scope=scope)


def _get_credential_map(scope: str = "system") -> Dict[str, Dict[str, Any]]:
    return {item["id"]: item for item in _get_credentials(scope) if item.get("id")}


def _get_model_routes() -> List[Dict[str, Any]]:
    cfg = _get_system_config_with_env()
    return normalize_model_routes(cfg.get("model_routes") or [], _get_credentials())


def _get_service_routes() -> List[Dict[str, Any]]:
    cfg = _get_system_config_with_env()
    return normalize_service_routes(cfg.get("service_routes") or [], _get_credentials())


def _get_model_route_entry(model: Optional[str]) -> Optional[Dict[str, Any]]:
    model_id = str(model or "").strip()
    if not model_id:
        return None
    for item in _get_model_routes():
        if str(item.get("model_id") or "").strip() == model_id:
            return item
    return None


def _get_service_route_entry(service: Optional[str]) -> Optional[Dict[str, Any]]:
    service_name = _normalize_service_name(service)
    for item in _get_service_routes():
        if _normalize_service_name(item.get("service")) == service_name:
            return item
    return None


def _build_route_credential_ids(
    service: str,
    model_id: Optional[str],
    model_route_map: Dict[str, Dict[str, Any]],
    service_route_map: Dict[str, Dict[str, Any]],
) -> List[str]:
    route = model_route_map.get(str(model_id or "").strip())
    ordered_ids: List[str] = []
    if route and route.get("enabled", True):
        _append_route_credential(ordered_ids, route.get("primary_credential_id"))
        for cred_id in route.get("fallback_credential_ids") or []:
            _append_route_credential(ordered_ids, cred_id)
    if not ordered_ids:
        service_route = service_route_map.get(_normalize_service_name(service))
        if service_route:
            _append_route_credential(ordered_ids, service_route.get("primary_credential_id"))
            for cred_id in service_route.get("fallback_credential_ids") or []:
                _append_route_credential(ordered_ids, cred_id)
    return ordered_ids


def _build_route_credential_chain(service: str, model: Optional[str] = None) -> List[Dict[str, Any]]:
    credential_map = _get_credential_map()
    ordered_ids = _build_route_credential_ids(
        service,
        model,
        {item.get("model_id"): item for item in _get_model_routes() if item.get("model_id")},
        {item.get("service"): item for item in _get_service_routes() if item.get("service")},
    )
    credentials: List[Dict[str, Any]] = []
    for cred_id in ordered_ids:
        credential = credential_map.get(cred_id)
        if credential and credential.get("enabled", True):
            credentials.append(credential)
    return credentials


def _get_model_route_summary(service: str, model: Optional[str]) -> Dict[str, Any]:
    model_id = str(model or "").strip()
    route = _get_model_route_entry(model_id)
    service_route = _get_service_route_entry(service)
    credentials = _build_route_credential_chain(service, model_id)
    reasons: List[str] = []
    if route and route.get("enabled", True) and not route.get("primary_credential_id") and not (route.get("fallback_credential_ids") or []):
        reasons.append("模型已配置路由，但未绑定系统凭证")
    if not route and not service_route:
        reasons.append("未配置模型路由或服务默认路由")
    if (route or service_route) and not credentials:
        reasons.append("路由存在，但没有可用的系统凭证")
    executable = bool(credentials)
    return {
        "model_id": model_id,
        "service": _normalize_service_name(service),
        "allow_personal_override": route.get("allow_personal_override", True) if route else True,
        "primary_credential_id": route.get("primary_credential_id") if route else (service_route.get("primary_credential_id") if service_route else None),
        "fallback_credential_ids": list(route.get("fallback_credential_ids") or []) if route else list(service_route.get("fallback_credential_ids") or []) if service_route else [],
        "route_source": "model" if route else ("service" if service_route else "missing"),
        "status": "ready" if executable else ("missing_credential" if reasons else "unavailable"),
        "executable": executable,
        "reason": "；".join(reasons) if reasons else "可执行",
        "credential_ids": [item.get("id") for item in credentials if item.get("id")],
    }


def _get_model_catalog() -> List[Dict[str, Any]]:
    cfg = _get_system_config_with_env()
    return normalize_model_catalog(cfg.get("model_catalog") or cfg.get("models") or [])


def _get_prompt_channels_config(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    data = cfg if isinstance(cfg, dict) else _get_system_config_with_env()
    prompt_catalog = normalize_model_catalog(data.get("models") or data.get("model_catalog") or [])
    return normalize_prompt_channels(data.get("prompt_channels"), prompt_catalog)


def _build_prompt_model_chain(preferred_model: Optional[str], channel: Optional[str] = None) -> List[str]:
    normalized_channel = _normalize_prompt_channel_name(channel)
    prompt_models = [
        str(item.get("model") or "").strip()
        for item in _get_model_catalog()
        if item.get("enabled", True) and str(item.get("service") or "").strip().lower() == "prompt"
    ]
    channel_models: List[str] = []
    if normalized_channel:
        prompt_channels = _get_prompt_channels_config()
        channel_cfg = prompt_channels.get(normalized_channel) or {}
        if channel_cfg.get("enabled", True):
            channel_models = [str(v).strip() for v in (channel_cfg.get("models") or []) if str(v).strip()]
    chain = channel_models + [str(preferred_model or "").strip()] + prompt_models
    seen = set()
    ordered: List[str] = []
    for model in chain:
        if not model or model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


def _count_static_prompt_candidates(model_item: Dict[str, Any], pools: List[Dict[str, Any]]) -> int:
    seen = set()
    base_url = model_item.get("base_url")
    model_keys = [model_item.get("api_key")] + (model_item.get("backup_keys") or [])
    for key in model_keys:
        if not key:
            continue
        seen.add(f"{key}::{base_url or ''}")
    for pool in pools:
        pool_base = pool.get("base_url")
        keys = [pool.get("key")] + (pool.get("backup_keys") or [])
        for key in keys:
            if not key:
                continue
            seen.add(f"{key}::{pool_base or ''}")
    return len(seen)


def validate_prompt_channels_config(
    models: List[Dict[str, Any]],
    key_pools: List[Dict[str, Any]],
    prompt_channels: Dict[str, Dict[str, Any]],
    credentials: Optional[List[Dict[str, Any]]] = None,
    model_routes: Optional[List[Dict[str, Any]]] = None,
    service_routes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized_models = normalize_model_catalog(models or [])
    normalized_pools = normalize_key_pools(key_pools or [])
    normalized_channels = normalize_prompt_channels(prompt_channels, normalized_models)
    normalized_credentials = normalize_credentials(credentials or [], scope="system")
    normalized_model_routes = normalize_model_routes(model_routes or [], normalized_credentials)
    normalized_service_routes = normalize_service_routes(service_routes or [], normalized_credentials)
    prompt_route_mode = bool(normalized_credentials or normalized_model_routes or normalized_service_routes)
    prompt_credential_map = {
        item["id"]: item
        for item in normalized_credentials
        if item.get("id")
    }
    prompt_model_route_map = {
        item["model_id"]: item
        for item in normalized_model_routes
        if item.get("model_id")
    }
    prompt_service_route_map = {
        item["service"]: item
        for item in normalized_service_routes
        if item.get("service")
    }
    prompt_model_map: Dict[str, Dict[str, Any]] = {}
    for item in normalized_models:
        if str(item.get("service") or "").strip().lower() != "prompt":
            continue
        model_name = str(item.get("model") or "").strip()
        if not model_name:
            continue
        prompt_model_map[model_name.lower()] = item

    errors: List[str] = []
    warnings: List[str] = []
    channels: Dict[str, Dict[str, Any]] = {}

    for channel in PROMPT_CHANNEL_KEYS:
        channel_cfg = normalized_channels.get(channel) or {"enabled": True, "models": []}
        models_chain = [str(v).strip() for v in (channel_cfg.get("models") or []) if str(v).strip()]
        model_valid_chain: List[str] = []
        model_candidate_chain: List[str] = []
        candidate_count_total = 0

        if channel_cfg.get("enabled") is not True:
            warnings.append(f"通道 {channel} 未启用，已跳过健康校验。")
            channels[channel] = {
                "enabled": False,
                "models": models_chain,
                "valid_models": [],
                "candidate_models": [],
                "candidate_count": 0,
            }
            continue

        for model_name in models_chain:
            model_item = prompt_model_map.get(model_name.lower())
            if not model_item:
                warnings.append(f"通道 {channel} 包含未配置的提示词模型：{model_name}")
                continue
            if not model_item.get("enabled", True):
                warnings.append(f"通道 {channel} 的模型未启用：{model_name}")
                continue
            model_valid_chain.append(model_name)
            candidate_count = 0
            if prompt_route_mode:
                route_credential_ids = _build_route_credential_ids(
                    "prompt",
                    model_name,
                    prompt_model_route_map,
                    prompt_service_route_map,
                )
                for credential_id in route_credential_ids:
                    credential = prompt_credential_map.get(credential_id)
                    if credential and credential.get("enabled", True):
                        candidate_count += len(_expand_credential_candidates(credential))
            else:
                pools = select_key_pools(normalized_pools, "prompt", model_name)
                candidate_count = _count_static_prompt_candidates(model_item, pools)
            candidate_count_total += candidate_count
            if candidate_count > 0:
                model_candidate_chain.append(model_name)
            else:
                warnings.append(f"通道 {channel} 的模型 {model_name} 未找到可用 Key 候选。")

        if len(model_valid_chain) < 1:
            errors.append(f"通道 {channel} 至少需要 1 个有效提示词模型。")
        elif len(model_valid_chain) < 2:
            warnings.append(f"通道 {channel} 的有效提示词模型少于 2 个，回退能力较弱。")
        if not model_candidate_chain:
            errors.append(f"通道 {channel} 没有可用的 Key 候选链。")

        channels[channel] = {
            "enabled": channel_cfg.get("enabled") is True,
            "models": models_chain,
            "valid_models": model_valid_chain,
            "candidate_models": model_candidate_chain,
            "candidate_count": candidate_count_total,
        }

    return {
        "errors": errors,
        "warnings": warnings,
        "channels": channels,
        "prompt_channels": normalized_channels,
    }


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


def _build_pool_candidates(service: str, model: Optional[str] = None) -> List[Dict]:
    credentials = _build_route_credential_chain(service, model)
    candidates: List[Dict] = []
    for credential in credentials:
        candidates.extend(_expand_credential_candidates(credential))
    return candidates


def _build_model_candidates(
    service: str,
    model: Optional[str] = None,
    runtime_key: Optional[str] = None,
    runtime_base_url: Optional[str] = None,
    fallback_base_url: Optional[str] = None,
) -> List[Dict]:
    model_cfgs = _select_model_configs(service, model)
    if runtime_key:
        # BYOK mode: prefer model-level base_url first; global fallback can point
        # to another provider and cause wrong endpoint routing.
        preferred_base_url = runtime_base_url
        preferred_platform = None
        if model_cfgs:
            preferred_base_url = preferred_base_url or model_cfgs[0].get("base_url")
            preferred_platform = model_cfgs[0].get("platform")
        preferred_base_url = preferred_base_url or fallback_base_url
        return [{"key": runtime_key, "base_url": preferred_base_url, "platform": preferred_platform}]

    preferred_base_url = runtime_base_url or fallback_base_url
    if not preferred_base_url:
        for cfg in model_cfgs:
            if cfg.get("base_url"):
                preferred_base_url = cfg.get("base_url")
                break
    pool_candidates = _build_pool_candidates(service, model)
    if pool_candidates:
        return pool_candidates
    if preferred_base_url:
        return [{"key": None, "base_url": preferred_base_url, "platform": model_cfgs[0].get("platform") if model_cfgs else None}]
    return []


def _get_default_model(service: str, fallback: Optional[str] = None) -> Optional[str]:
    service = (service or "").strip().lower()
    candidates = [item for item in _get_model_catalog() if item.get("enabled", True) and item.get("service") == service]
    if not candidates:
        return fallback
    model = candidates[0].get("model")
    return model or fallback


def _select_service_key_pools(service: str, model: Optional[str] = None) -> List[Dict]:
    route_credentials = _build_route_credential_chain(service, model)
    if route_credentials:
        return [
            {
                "key": credential.get("primary_secret"),
                "base_url": credential.get("base_url"),
                "backup_keys": credential.get("backup_secrets") or [],
                "provider": credential.get("provider"),
                "services": [credential.get("service")],
                "models": [model] if model else [],
                "priority": index * 10,
                "enabled": credential.get("enabled", True),
                "id": credential.get("id"),
                "label": credential.get("label"),
            }
            for index, credential in enumerate(route_credentials, start=1)
        ]
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
    route_credentials = _build_route_credential_chain(service, model)
    if route_credentials:
        candidates: List[Dict] = []
        for credential in route_credentials:
            candidates.extend(_expand_credential_candidates(credential))
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
    raw_status = VideoGenerator._extract_value(payload, ["status", "state", "Status", "State", "task_status", "taskStatus"])
    if raw_status:
        text = str(raw_status).strip().upper()
        if text in ("PENDING", "QUEUED", "RUNNING"):
            return "processing"
        if text in ("EXPIRED",):
            return "expired"
        if text in ("SUCCEEDED", "SUCCESS", "DONE", "COMPLETED"):
            return "done"
        if text in ("FAILED", "ERROR", "CANCELED", "CANCELLED"):
            return "failed"
    if payload.get("done") is True:
        return "done"
    if "done" in payload:
        return "processing"
    return "processing"


def _has_system_model_key(service: Optional[str], model: Optional[str]) -> bool:
    if not service or not model:
        return False
    summary = _get_model_route_summary(service, model)
    return bool(summary.get("executable"))


def _allows_personal_override(service: Optional[str], model: Optional[str]) -> bool:
    if not service or not model:
        return True
    summary = _get_model_route_summary(service, model)
    return bool(summary.get("allow_personal_override", True))


def determine_execution_mode(
    current_user: Optional[Dict],
    x_model_key: Optional[str],
    cost: int = 1,
    service: Optional[str] = None,
    model: Optional[str] = None,
):
    if x_model_key:
        if service and model and not _allows_personal_override(service, model):
            raise HTTPException(status_code=403, detail="该模型已禁用个人凭证覆盖。")
        return "user", x_model_key, None
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required or provide x-model-key.")

    system_has_key = _has_system_model_key(service or "image", model)
    if system_has_key:
        user = db.get_user_by_id(current_user["id"])
        if user["quota_used"] + cost > user["quota_limit"]:
            if x_model_key:
                return "user", x_model_key, None
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Quota exceeded (Cost: {cost}, Remaining: "
                    f"{user['quota_limit'] - user['quota_used']}). Please provide Custom API Key."
                ),
            )
        return "system", None, None

    raise HTTPException(status_code=403, detail="系统未配置API Key，请联系管理员。")


def determine_key_execution_mode(
    current_user: Optional[Dict],
    provided_key: Optional[str],
    cost: int,
    header_name: str,
    service: Optional[str] = None,
    model: Optional[str] = None,
):
    if provided_key:
        if service and model and not _allows_personal_override(service, model):
            raise HTTPException(status_code=403, detail="该模型已禁用个人凭证覆盖。")
        return "user", provided_key
    if not current_user:
        raise HTTPException(status_code=401, detail=f"Login required or provide {header_name}.")

    system_has_key = _has_system_model_key(service, model)
    if system_has_key:
        user = db.get_user_by_id(current_user["id"])
        if user["quota_used"] + cost > user["quota_limit"]:
            if provided_key:
                return "user", provided_key
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Quota exceeded (Cost: {cost}, Remaining: "
                    f"{user['quota_limit'] - user['quota_used']}). Please provide Custom API Key."
                ),
            )
        return "system", None

    raise HTTPException(status_code=403, detail="系统未配置API Key，请联系管理员。")


def _get_wav_duration_seconds(path: str) -> Optional[float]:
    try:
        if not path or not os.path.exists(path):
            return None
        if not path.lower().endswith(".wav"):
            return None
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            if rate <= 0:
                return None
            if channels > 0 and sample_width > 0:
                bytes_per_frame = channels * sample_width
                file_size = os.path.getsize(path)
                estimated_frames = max(0, (file_size - 44) // bytes_per_frame)
                if estimated_frames > 0 and (frames <= 0 or frames > estimated_frames * 4):
                    frames = estimated_frames
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
