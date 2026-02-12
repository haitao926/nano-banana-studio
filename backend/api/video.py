import json
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app_state import db, video_gen
from core.video_generator import VideoGenerator
from deps import get_current_user, get_current_user_optional
from helpers import (
    _build_model_candidates,
    _download_public_image_bytes,
    _get_default_model,
    _get_video_base_url,
    _get_video_credit_cost,
    _normalize_video_status,
    determine_key_execution_mode,
)
from schemas import VideoGenerateRequest

router = APIRouter()


@router.get("/api/video/history")
async def get_video_history(current_user: Dict = Depends(get_current_user)):
    items = db.get_video_history(user_id=current_user["id"])
    results = []
    for item in items:
        meta = {}
        raw_meta = item.get("metadata")
        if raw_meta:
            try:
                meta = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
            except Exception:
                meta = {}
        results.append(
            {
                "id": item.get("id"),
                "task_id": item.get("task_id"),
                "image_url": item.get("image_url"),
                "audio_url": item.get("audio_url"),
                "video_url": item.get("video_url"),
                "prompt": item.get("prompt"),
                "resolution": item.get("resolution"),
                "style": item.get("style"),
                "duration": item.get("duration"),
                "status": item.get("status"),
                "created_at": item.get("created_at"),
                "metadata": meta,
                "mode": meta.get("mode") or "text",
            }
        )
    return results


@router.post("/api/video/generate")
async def generate_video(
    req: VideoGenerateRequest,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_video_key: Optional[str] = Header(None, alias="x-video-key"),
    x_video_base_url: Optional[str] = Header(None, alias="x-video-base-url"),
):
    try:
        model = (req.model or _get_default_model("video") or "").strip()
        if not model:
            raise HTTPException(status_code=400, detail="请先在模型配置中添加视频模型")
        cost = _get_video_credit_cost(model)
        mode, runtime_key = determine_key_execution_mode(
            current_user, x_video_key, cost=cost, header_name="x-video-key"
        )

        prompt = req.prompt.strip()
        is_sora = video_gen._is_sora_model(model)
        if req.mode == "image" and not (req.image_url or (req.images and len(req.images) > 0)):
            raise HTTPException(status_code=400, detail="image_url or images required for image mode")
        if is_sora and not (req.image_url or (req.images and len(req.images) > 0)):
            raise HTTPException(status_code=400, detail="Sora requires image_url or images")

        image_url = None
        image_urls = None
        image_bytes = None
        image_mime = None

        if req.mode == "image" or is_sora:
            if req.images:
                image_urls = [u.strip() for u in req.images if u and u.strip()]
            if not image_urls:
                image_url = req.image_url.strip()
            else:
                image_url = image_urls[0]

            image_payload = _download_public_image_bytes(image_url)
            if not image_payload:
                raise HTTPException(status_code=400, detail="Failed to fetch image_url content")
            image_bytes = image_payload.get("bytes")
            image_mime = image_payload.get("mime_type")

        video_base_url = _get_video_base_url()
        candidates = _build_model_candidates(
            "video",
            model=model,
            runtime_key=x_video_key,
            runtime_base_url=x_video_base_url,
            fallback_base_url=video_base_url,
        )

        result = None
        last_error = None
        for candidate in candidates:
            result = video_gen.submit_task(
                prompt=prompt,
                model=model,
                image_url=image_url,
                image_urls=image_urls,
                image_bytes=image_bytes,
                image_mime=image_mime,
                aspect_ratio=req.aspect_ratio,
                resolution=req.resolution,
                duration_seconds=req.duration_seconds,
                api_key=candidate.get("key") or runtime_key,
                base_url=candidate.get("base_url") or video_base_url,
                platform=candidate.get("platform"),
            )
            error_msg = video_gen.extract_error(result)
            if not error_msg:
                break
            last_error = error_msg
        if last_error:
            raise HTTPException(status_code=502, detail=last_error or "Video generation failed")

        task_id = VideoGenerator._extract_value(
            result,
            ["id", "task_id", "taskId", "name", "operation", "operationName", "operation_name"],
        )
        if not task_id:
            raise HTTPException(status_code=502, detail="Missing operation name in response")

        if current_user:
            provider = "ark" if video_gen._is_ark_model(model) else "gemini"
            db.create_video_task(
                user_id=current_user["id"],
                task_id=task_id,
                image_url=image_url,
                audio_url=None,
                prompt=prompt,
                resolution=req.resolution,
                style=req.aspect_ratio,
                duration=req.duration_seconds,
                status="processing",
                metadata={
                    "mode": req.mode,
                    "model": model,
                    "provider": provider,
                    "aspect_ratio": req.aspect_ratio,
                    "resolution": req.resolution,
                    "duration_seconds": req.duration_seconds,
                },
            )
            if mode == "system":
                db.update_user_quota(current_user["id"], cost)

        remaining = None
        if current_user:
            updated_user = db.get_user_by_id(current_user["id"])
            remaining = max(0, updated_user["quota_limit"] - updated_user["quota_used"])

        return {"success": True, "data": {"task_id": task_id}, "raw": result, "remaining_quota": remaining}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/video/status")
async def get_video_status(
    task_id: str,
    x_video_key: Optional[str] = Header(None, alias="x-video-key"),
    x_video_base_url: Optional[str] = Header(None, alias="x-video-base-url"),
    current_user: Optional[Dict] = Depends(get_current_user_optional),
):
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id required")

    provider = None
    model_hint = None
    if current_user:
        task = db.get_video_task(task_id)
        if task:
            raw_meta = task.get("metadata")
            try:
                meta = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
            except Exception:
                meta = {}
            provider = meta.get("provider")
            model_hint = meta.get("model")

    video_base_url = _get_video_base_url()
    candidates = _build_model_candidates(
        "video",
        model=model_hint,
        runtime_key=x_video_key,
        runtime_base_url=x_video_base_url,
        fallback_base_url=video_base_url,
    )

    result = None
    last_error = None
    for candidate in candidates:
        result = video_gen.get_task_result(
            task_id,
            api_key=candidate.get("key"),
            base_url=candidate.get("base_url") or video_base_url,
            model=model_hint,
        )
        error_msg = video_gen.extract_error(result)
        if not error_msg:
            break
        last_error = error_msg
    if last_error:
        raise HTTPException(status_code=502, detail=last_error or "Video status failed")

    status_value = _normalize_video_status(result)
    video_url = video_gen.extract_video_url(result)
    normalized = {"task_id": task_id, "status": status_value, "video_url": video_url}

    if current_user and status_value in ("done", "failed", "expired"):
        db.update_video_task(task_id, video_url=video_url, status=status_value)

    return {"success": True, "data": normalized, "raw": result}
