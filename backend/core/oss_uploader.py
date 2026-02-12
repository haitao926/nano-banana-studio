import os
import secrets
import time
from typing import Dict
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile


def _get_env(name: str) -> str:
    return os.getenv(name, "").strip()


def get_oss_config() -> Dict[str, str]:
    return {
        "bucket": _get_env("OSS_BUCKET"),
        "endpoint": _get_env("OSS_ENDPOINT"),
        "access_key_id": _get_env("OSS_ACCESS_KEY_ID"),
        "access_key_secret": _get_env("OSS_ACCESS_KEY_SECRET"),
        "public_base_url": _get_env("OSS_PUBLIC_BASE_URL"),
        "prefix": _get_env("OSS_UPLOAD_PREFIX") or "uploads",
    }


def _normalize_endpoint(endpoint: str) -> str:
    if not endpoint:
        return ""
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return f"https://{endpoint}"


def _build_public_base_url(bucket: str, endpoint: str, public_base_url: str) -> str:
    if public_base_url:
        return public_base_url.rstrip("/")
    normalized = _normalize_endpoint(endpoint)
    parsed = urlparse(normalized)
    host = parsed.netloc or parsed.path
    if not host:
        raise HTTPException(status_code=500, detail="Invalid OSS endpoint")
    scheme = parsed.scheme or "https"
    if host.startswith(f"{bucket}."):
        return f"{scheme}://{host}"
    return f"{scheme}://{bucket}.{host}"


def upload_file_to_oss(file: UploadFile) -> str:
    cfg = get_oss_config()
    if not cfg["bucket"] or not cfg["endpoint"] or not cfg["access_key_id"] or not cfg["access_key_secret"]:
        raise HTTPException(status_code=500, detail="OSS is not configured. Set OSS_BUCKET/OSS_ENDPOINT/OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET.")

    try:
        import oss2
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OSS SDK not installed: {exc}")

    filename = file.filename or "upload.bin"
    _, ext = os.path.splitext(filename)
    safe_ext = ext if ext else ""
    key_base = f"upload_{int(time.time())}_{secrets.token_hex(4)}{safe_ext}"
    prefix = cfg["prefix"].strip("/")
    object_key = f"{prefix}/{key_base}" if prefix else key_base

    auth = oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])
    endpoint = _normalize_endpoint(cfg["endpoint"])
    bucket = oss2.Bucket(auth, endpoint, cfg["bucket"])

    try:
        file.file.seek(0)
        headers = {}
        if file.content_type:
            headers["Content-Type"] = file.content_type
        result = bucket.put_object(object_key, file.file, headers=headers)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OSS upload failed: {exc}")

    if not (200 <= result.status < 300):
        raise HTTPException(status_code=500, detail=f"OSS upload failed with status {result.status}")

    public_base = _build_public_base_url(cfg["bucket"], cfg["endpoint"], cfg["public_base_url"])
    return f"{public_base}/{object_key}"
