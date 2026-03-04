import json
import re
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_SERVICES = {"image", "audio", "video"}
ALLOWED_SERVICES = {"image", "audio", "video", "digital_human", "prompt"}
PROVIDER_ALIASES = {
    "openai": "openai",
    "gpt": "openai",
    "oai": "openai",
    "gemini": "gemini",
    "google": "gemini",
    "ark": "ark",
    "volcengine": "ark",
    "volc": "ark",
    "火山": "ark",
    "方舟": "ark",
    "bailian": "bailian",
    "百炼": "bailian",
    "aliyun": "bailian",
    "dashscope": "bailian",
    "tongyi": "bailian",
    "qwen": "bailian",
    "wanx": "bailian",
    "other": "other",
    "custom": "other",
}


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


def _coerce_int(value: Any, default: int = 100) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_services(value: Any) -> List[str]:
    if value is None:
        return sorted(DEFAULT_SERVICES)
    if isinstance(value, str):
        parts = [v.strip().lower() for v in value.replace(";", ",").split(",") if v.strip()]
    elif isinstance(value, Iterable):
        parts = [str(v).strip().lower() for v in value if str(v).strip()]
    else:
        parts = []
    services = [s for s in parts if s in ALLOWED_SERVICES]
    return services or sorted(DEFAULT_SERVICES)

def _normalize_provider(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in ("any", "all", "*", "不限"):
        return None
    return PROVIDER_ALIASES.get(text, text)

def _infer_provider(model: Optional[str]) -> Optional[str]:
    if not model:
        return None
    text = str(model).strip().lower()
    if not text:
        return None
    if "ark" in text or "volc" in text or "volcengine" in text or "ark.cn-beijing" in text:
        return "ark"
    # Ark Wan2 models (hyphenated) should map to ark instead of bailian.
    if "wan2-" in text:
        return "ark"
    if "doubao" in text or "seedance" in text or "seedream" in text:
        return "ark"
    if "gemini" in text or "imagen" in text or "veo" in text or "sora" in text:
        return "gemini"
    if "gpt" in text or "openai" in text or "claude" in text or text.startswith(("o1", "o3", "o4")):
        return "openai"
    if any(token in text for token in ("bailian", "百炼", "aliyun", "dashscope", "tongyi", "qwen", "wanx", "wan")):
        return "bailian"
    return "other"


def _normalize_models(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]
    elif isinstance(value, Iterable):
        parts = [str(v).strip() for v in value if str(v).strip()]
    else:
        parts = []
    return parts


def _normalize_key_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [v.strip() for v in re.split(r"[\\n,;]+", value) if v.strip()]
    elif isinstance(value, Iterable):
        parts = [str(v).strip() for v in value if str(v).strip()]
    else:
        parts = []
    seen = set()
    out: List[str] = []
    for key in parts:
        if key and key not in seen:
            out.append(key)
            seen.add(key)
    return out


def normalize_key_pools(raw: Any) -> List[Dict[str, Any]]:
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if isinstance(data, dict):
        data = data.get("key_pools") or data.get("pools") or []
    if not isinstance(data, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        access_key_id = str(item.get("access_key_id") or item.get("accessKeyId") or item.get("accessKeyID") or "").strip()
        secret_access_key = str(item.get("secret_access_key") or item.get("secretAccessKey") or item.get("secretKey") or "").strip()
        if not key and not access_key_id:
            continue
        base_url = str(item.get("base_url") or "").strip() or None
        services = _normalize_services(item.get("services"))
        models = _normalize_models(item.get("models"))
        provider = _normalize_provider(item.get("provider"))
        backup_keys = _normalize_key_list(item.get("backup_keys"))
        if key in backup_keys:
            backup_keys = [k for k in backup_keys if k != key]
        priority = _coerce_int(item.get("priority"), 100)
        enabled = _coerce_bool(item.get("enabled"), True)
        normalized.append({
            "key": key,
            "base_url": base_url,
            "services": services,
            "models": models,
            "provider": provider,
            "backup_keys": backup_keys,
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
            "priority": priority,
            "enabled": enabled,
        })
    return normalized


def select_key_pools(pools: List[Dict[str, Any]], service: str, model: Optional[str] = None) -> List[Dict[str, Any]]:
    if not pools:
        return []
    service = (service or "").strip().lower()
    model_lower = (model or "").strip().lower()
    req_provider = _infer_provider(model_lower)
    candidates: List[Dict[str, Any]] = []
    for item in pools:
        if not item.get("enabled", True):
            continue
        item_provider = _normalize_provider(item.get("provider"))
        if item_provider and req_provider and item_provider != req_provider:
            continue
        services = item.get("services") or []
        if service and service not in services:
            continue
        models = item.get("models") or []
        if models and model_lower:
            match = any(model_lower == m.lower() for m in models)
            if not match:
                continue
        candidates.append(item)
    candidates.sort(key=lambda x: _coerce_int(x.get("priority"), 100))
    return candidates
