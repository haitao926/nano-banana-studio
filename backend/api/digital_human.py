import json
import math
import os
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app_state import db, digital_human_gen
from deps import get_current_user_optional
from helpers import (
    _build_model_candidates,
    _ensure_public_url,
    _get_default_model,
    _get_model_cost,
    _get_video_base_url,
    _get_wav_duration_seconds,
    _resolve_public_media_url,
    _resolve_oss_url,
    _resolve_local_audio_path,
    _safe_log_payload,
    determine_key_execution_mode,
)
from schemas import DigitalHumanRequest

router = APIRouter()


@router.post("/api/digital_human/submit")
async def submit_digital_human_task(
    req: DigitalHumanRequest,
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_video_key: Optional[str] = Header(None, alias="x-video-key"),
    x_video_base_url: Optional[str] = Header(None, alias="x-video-base-url"),
):
    ext_base = os.getenv("EXTERNAL_BASE_URL", "").rstrip("/")
    if not ext_base:
        ext_base = str(request.base_url).rstrip("/")

    img_url = req.image_url.strip()
    raw_audio_url = req.audio_url.strip()
    audio_url = raw_audio_url

    img_url = _resolve_public_media_url(img_url)
    audio_url = _resolve_public_media_url(audio_url)

    if ext_base:
        if img_url.startswith("/"):
            img_url = f"{ext_base}{img_url}"
        if audio_url.startswith("/"):
            audio_url = f"{ext_base}{audio_url}"
    if img_url.startswith("oss://") or audio_url.startswith("oss://"):
        raise HTTPException(
            status_code=400,
            detail="oss:// URL is not supported for digital human. Please provide a public http(s) URL or configure OSS credentials.",
        )
    _ensure_public_url(img_url, "image_url")
    _ensure_public_url(audio_url, "audio_url")

    prompt = req.prompt.strip() if req.prompt else None
    model_name = (req.model or _get_default_model("digital_human") or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="请先在模型配置中添加数字人模型")

    duration_sec = req.audio_duration
    if duration_sec is None:
        local_audio_path = _resolve_local_audio_path(raw_audio_url)
        duration_sec = _get_wav_duration_seconds(local_audio_path)
    cost_per_sec = _get_model_cost("digital_human", model_name) or 1
    if duration_sec:
        cost = max(1, int(math.ceil(duration_sec * cost_per_sec)))
    else:
        cost = max(1, int(cost_per_sec))

    mode, runtime_key = determine_key_execution_mode(
        current_user,
        x_video_key,
        cost=cost,
        header_name="x-video-key",
        service="digital_human",
        model=req.model,
    )

    result = None
    last_error = None
    error_msg = None
    provider = "dashscope"

    video_base_url = _get_video_base_url()
    runtime_base_url = x_video_base_url if runtime_key else None
    candidates = _build_model_candidates(
        "digital_human",
        model=model_name,
        runtime_key=runtime_key,
        runtime_base_url=runtime_base_url,
        fallback_base_url=video_base_url,
    )
    for candidate in candidates:
        result = digital_human_gen.submit_task(
            image_url=img_url,
            audio_url=audio_url,
            prompt=prompt,
            seed=req.seed,
            resolution=req.resolution,
            fast_mode=req.fast_mode,
            style=req.style,
            api_key=candidate.get("key") or runtime_key,
            base_url=candidate.get("base_url") or video_base_url,
            model=model_name,
        )
        error_msg = digital_human_gen.extract_error(result)
        if not error_msg:
            break
        last_error = error_msg
    if error_msg:
        print(f"[digital_human] submit failed provider={provider} error={error_msg} raw={_safe_log_payload(result)}")
        raise HTTPException(status_code=502, detail=last_error or "Digital human request failed")

    normalized = digital_human_gen.normalize_submit_response(result)
    task_id = normalized.get("task_id")
    if not task_id:
        return {"success": False, "message": "Task ID missing in response", "raw": result}

    if current_user:
        db.create_video_task(
            user_id=current_user["id"],
            task_id=task_id,
            image_url=img_url,
            audio_url=audio_url,
            prompt=prompt,
            resolution=req.resolution,
            style=req.style,
            duration=duration_sec,
            status="processing",
            metadata={
                "mode": "digital_human",
                "model": model_name,
                "provider": provider,
                "resolution": req.resolution,
                "style": req.style,
            },
        )
        if mode == "system":
            db.update_user_quota(current_user["id"], cost)

    remaining = None
    if current_user:
        updated_user = db.get_user_by_id(current_user["id"])
        remaining = max(0, updated_user["quota_limit"] - updated_user["quota_used"])

    return {"success": True, "data": normalized, "raw": result, "remaining_quota": remaining}


@router.get("/api/digital_human/status/{task_id}")
async def get_digital_human_status(
    task_id: str,
    x_video_key: Optional[str] = Header(None, alias="x-video-key"),
    x_video_base_url: Optional[str] = Header(None, alias="x-video-base-url"),
    current_user: Optional[Dict] = Depends(get_current_user_optional),
):
    result = None
    last_error = None
    error_msg = None
    provider = "dashscope"

    video_base_url = _get_video_base_url()
    model_name = _get_default_model("digital_human") or ""
    if not model_name:
        return {"error": "Missing digital human model configuration."}
    if current_user:
        task = db.get_video_task(task_id)
        if task:
            raw_meta = task.get("metadata")
            try:
                meta = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
            except Exception:
                meta = {}
            model_name = meta.get("model") or model_name

    candidates = _build_model_candidates(
        "digital_human",
        model=model_name,
        runtime_key=x_video_key,
        runtime_base_url=x_video_base_url,
        fallback_base_url=video_base_url,
    )
    for candidate in candidates:
        result = digital_human_gen.get_task_result(
            task_id,
            api_key=candidate.get("key"),
            base_url=candidate.get("base_url") or video_base_url,
            model=model_name,
        )
        error_msg = digital_human_gen.extract_error(result)
        if not error_msg:
            break
        last_error = error_msg
    if error_msg:
        print(f"[digital_human] status failed provider={provider} error={error_msg} raw={_safe_log_payload(result)}")
        raise HTTPException(status_code=502, detail=last_error or "Digital human status failed")

    normalized = digital_human_gen.normalize_status_response(result)
    if current_user:
        status_value = normalized.get("status")
        video_url = normalized.get("video_url")
        if status_value in ("done", "failed", "expired"):
            db.update_video_task(task_id, video_url=video_url, status=status_value)
    return {"success": True, "data": normalized, "raw": result}
