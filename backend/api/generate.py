import base64
import copy
import os
import time
from typing import Dict, List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app_state import GENERATED_DIR, MAX_BATCH_TASKS, BATCH_WORKERS, BATCH_DELAY_SECONDS, batch_gen, db, img_gen
from deps import get_current_user_optional
from helpers import (
    _build_model_candidates,
    _dedupe_preserve_order,
    _download_reference_image,
    _download_public_image_bytes,
    _enforce_rate_limit,
    _get_default_model,
    _get_model_catalog,
    _get_model_cost,
    _resolve_reference_image_path,
    create_thumbnail,
    determine_execution_mode,
    sanitize_filename,
)
from schemas import BatchGenRequest, ModifyGenRequest, OptimizePromptRequest, SingleGenRequest

router = APIRouter()


def _build_seedream_image_param(image_url: str) -> Optional[str]:
    if not image_url:
        return None
    if image_url.startswith(("http://", "https://")):
        return image_url
    payload = _download_public_image_bytes(image_url)
    if not payload:
        return None
    mime_type = payload.get("mime_type") or "image/png"
    encoded = base64.b64encode(payload["bytes"]).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _build_seedream_image_params(image_urls: list[str]) -> Optional[list[str]]:
    if not image_urls:
        return None
    params = []
    for url in image_urls:
        param = _build_seedream_image_param(url)
        if not param:
            return None
        params.append(param)
    return params


PROMPT_BACKUP_MODELS = ["claude-sonnet-4-6", "gpt-5.2-chat", "gemini-3.1-pro-preview"]
PROMPT_CHANNEL_MODEL_CHAIN = {
    "google": ["gemini-3.1-pro-preview", "claude-sonnet-4-6", "gpt-5.2-chat"],
    "byte": ["claude-sonnet-4-6", "gpt-5.2-chat", "gemini-3.1-pro-preview"],
    "aliyun": ["gpt-5.2-chat", "claude-sonnet-4-6", "gemini-3.1-pro-preview"],
}


def _normalize_prompt_channel(channel: Optional[str]) -> Optional[str]:
    text = str(channel or "").strip().lower()
    if text in ("google", "byte", "aliyun"):
        return text
    return None


def _build_prompt_model_chain(preferred_model: Optional[str], channel: Optional[str] = None) -> List[str]:
    normalized_channel = _normalize_prompt_channel(channel)
    prompt_models = [
        str(item.get("model") or "").strip()
        for item in _get_model_catalog()
        if item.get("enabled", True) and str(item.get("service") or "").strip().lower() == "prompt"
    ]
    if normalized_channel:
        channel_models = PROMPT_CHANNEL_MODEL_CHAIN.get(normalized_channel, [])
        chain = channel_models + [str(preferred_model or "").strip()] + prompt_models + PROMPT_BACKUP_MODELS
    else:
        chain = [str(preferred_model or "").strip()] + prompt_models + PROMPT_BACKUP_MODELS
    seen = set()
    ordered: List[str] = []
    for model in chain:
        if not model or model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


@router.post("/api/generate/single")
async def generate_single(
    req: SingleGenRequest,
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    try:
        request_model = (req.model or _get_default_model("image") or "").strip()
        if not request_model:
            raise HTTPException(status_code=400, detail="请先在模型配置中添加绘图模型")
        model_cost = _get_model_cost("image", request_model)
        model_text = (request_model or "").lower()
        cost = model_cost if isinstance(model_cost, int) else (2 if "gemini" in model_text else 1)
        is_seedream = img_gen._is_seedream_model(request_model)

        mode, runtime_key, runtime_base_url = determine_execution_mode(
            current_user,
            x_model_key,
            cost=cost,
            service="image",
            model=request_model,
        )
        if runtime_base_url is None and x_model_base_url:
            runtime_base_url = x_model_base_url
        _enforce_rate_limit(request, current_user)

        timestamp = int(time.time())
        safe_prompt = sanitize_filename(req.prompt)
        filename = f"{safe_prompt}_{timestamp}.png"

        enhanced_prompt = req.prompt
        context_prompts = []
        if req.subject and req.subject != "general":
            context_prompts.append(f"Subject: {req.subject}")
        if req.grade and req.grade != "general":
            context_prompts.append(f"Target Audience: {req.grade} students")
        if context_prompts:
            enhanced_prompt += " (" + ", ".join(context_prompts) + ")"

        original_config = copy.deepcopy(img_gen.config)
        try:
            img_gen.config.setdefault("image", {})
            img_gen.config["image"]["size"] = req.size
            img_gen.config["image"]["quality"] = req.quality
            img_gen.config["image"]["style"] = req.style

            final_path = None
            seedream_files = []
            seedream_urls = []
            seedream_group = bool(req.seedream_group and img_gen._supports_seedream_group(request_model))
            seedream_max_images = req.seedream_max_images if req.seedream_max_images and req.seedream_max_images > 0 else 4
            if seedream_max_images < 1:
                seedream_max_images = 1

            all_ref_urls = _dedupe_preserve_order(
                [u for u in [req.reference_image_url] + (req.reference_image_urls or []) if u]
            )
            if is_seedream and len(all_ref_urls) > 14:
                raise HTTPException(status_code=400, detail="Seedream supports at most 14 reference images.")
            if seedream_group:
                remaining = 15 - len(all_ref_urls)
                if remaining < 1:
                    raise HTTPException(status_code=400, detail="Seedream group mode supports up to 15 total images (reference + generated).")
                seedream_max_images = min(seedream_max_images, remaining)
            if all_ref_urls:
                if is_seedream:
                    seedream_image = (
                        _build_seedream_image_param(all_ref_urls[0])
                        if len(all_ref_urls) == 1
                        else _build_seedream_image_params(all_ref_urls)
                    )
                    if not seedream_image:
                        raise HTTPException(status_code=400, detail="Failed to read reference image")
                    candidates = _build_model_candidates(
                        "image",
                        model=request_model,
                        runtime_key=runtime_key,
                        runtime_base_url=runtime_base_url,
                        fallback_base_url=runtime_base_url,
                    )
                    for candidate in candidates:
                        seedream_urls = img_gen.generate_seedream_images(
                            enhanced_prompt,
                            size=req.size,
                            image_url=seedream_image,
                            max_images=seedream_max_images,
                            group_mode=seedream_group,
                            base_url=candidate.get("base_url"),
                            api_key=candidate.get("key"),
                            model=request_model,
                        )
                        if seedream_urls:
                            break
                    if seedream_urls:
                        for idx, image_url in enumerate(seedream_urls):
                            suffix = f"_{idx + 1}" if len(seedream_urls) > 1 else ""
                            filename_i = f"{safe_prompt}_{timestamp}{suffix}.png"
                            save_path = os.path.join(GENERATED_DIR, filename_i)
                            if img_gen.download_image(image_url, save_path):
                                create_thumbnail(save_path)
                                seedream_files.append(filename_i)
                        if not seedream_files:
                            last_error = getattr(img_gen, "last_error", None) or {}
                            if last_error.get("message"):
                                status_code = int(last_error.get("status_code") or 502)
                                if status_code < 400:
                                    status_code = 502
                                raise HTTPException(status_code=status_code, detail=last_error.get("message"))
                            raise HTTPException(status_code=500, detail="Failed to download generated image")
                    else:
                        last_error = getattr(img_gen, "last_error", None) or {}
                        if last_error.get("message"):
                            status_code = int(last_error.get("status_code") or 502)
                            if status_code < 400:
                                status_code = 502
                            raise HTTPException(status_code=status_code, detail=last_error.get("message"))
                        raise HTTPException(status_code=500, detail="Seedream generation failed")
                else:
                    ref_paths = []
                    for ref_url in all_ref_urls:
                        local_path = _resolve_reference_image_path(ref_url)
                        if local_path:
                            ref_paths.append(local_path)
                            continue
                        downloaded_path = _download_reference_image(ref_url)
                        if downloaded_path:
                            ref_paths.append(downloaded_path)

                    if ref_paths:
                        image_url = None
                        candidates = _build_model_candidates(
                            "image",
                            model=request_model,
                            runtime_key=runtime_key,
                            runtime_base_url=runtime_base_url,
                            fallback_base_url=runtime_base_url,
                        )
                        for candidate in candidates:
                            image_url = img_gen.generate_modified_image(
                                enhanced_prompt,
                                ref_paths,
                                base_url=candidate.get("base_url"),
                                api_key=candidate.get("key"),
                                model=request_model,
                            )
                            if image_url:
                                break
                        if image_url:
                            save_path = os.path.join(GENERATED_DIR, filename)
                            if img_gen.download_image(image_url, save_path):
                                final_path = save_path
                            else:
                                raise HTTPException(status_code=500, detail="Failed to download generated image")
                        else:
                            raise HTTPException(
                                status_code=500,
                                detail="Reference image modification failed. The model may have refused the edit or the reference image is invalid.",
                            )

            if not final_path and not seedream_files:
                if is_seedream:
                    candidates = _build_model_candidates(
                        "image",
                        model=request_model,
                        runtime_key=runtime_key,
                        runtime_base_url=runtime_base_url,
                        fallback_base_url=runtime_base_url,
                    )
                    for candidate in candidates:
                        seedream_urls = img_gen.generate_seedream_images(
                            enhanced_prompt,
                            size=req.size,
                            image_url=None,
                            max_images=seedream_max_images,
                            group_mode=seedream_group,
                            base_url=candidate.get("base_url"),
                            api_key=candidate.get("key"),
                            model=request_model,
                        )
                        if seedream_urls:
                            break
                    if seedream_urls:
                        for idx, image_url in enumerate(seedream_urls):
                            suffix = f"_{idx + 1}" if len(seedream_urls) > 1 else ""
                            filename_i = f"{safe_prompt}_{timestamp}{suffix}.png"
                            save_path = os.path.join(GENERATED_DIR, filename_i)
                            if img_gen.download_image(image_url, save_path):
                                create_thumbnail(save_path)
                                seedream_files.append(filename_i)
                    if not seedream_files and not seedream_urls:
                        last_error = getattr(img_gen, "last_error", None) or {}
                        if last_error.get("message"):
                            status_code = int(last_error.get("status_code") or 502)
                            if status_code < 400:
                                status_code = 502
                            raise HTTPException(status_code=status_code, detail=last_error.get("message"))
                else:
                    candidates = _build_model_candidates(
                        "image",
                        model=request_model,
                        runtime_key=runtime_key,
                        runtime_base_url=runtime_base_url,
                        fallback_base_url=runtime_base_url,
                    )
                    for candidate in candidates:
                        final_path = img_gen.generate_and_download(
                            enhanced_prompt,
                            filename,
                            folder=GENERATED_DIR,
                            base_url=candidate.get("base_url"),
                            api_key=candidate.get("key"),
                            model=request_model,
                        )
                        if final_path:
                            break
        finally:
            img_gen.config = original_config

        if seedream_files:
            if mode == "system" and current_user:
                db.update_user_quota(current_user["id"], cost)

            meta = {
                "size": req.size,
                "quality": req.quality,
                "style": req.style,
                "model": request_model,
                "reference_image_url": req.reference_image_url,
                "reference_image_urls": req.reference_image_urls,
                "seedream_group": True,
                "group_total": len(seedream_files),
            }
            urls = []
            for idx, name in enumerate(seedream_files):
                urls.append(f"/static/generated/{name}")
                db.log_image(
                    user_id=current_user["id"] if current_user else None,
                    filename=name,
                    prompt=req.prompt,
                    subject=req.subject,
                    grade=req.grade,
                    metadata={**meta, "group_index": idx + 1},
                )

            remaining = None
            if current_user:
                updated_user = db.get_user_by_id(current_user["id"])
                remaining = max(0, updated_user["quota_limit"] - updated_user["quota_used"])

            return {
                "success": True,
                "url": urls[0],
                "urls": urls,
                "remaining_quota": remaining,
            }

        if final_path:
            create_thumbnail(final_path)

            if mode == "system" and current_user:
                db.update_user_quota(current_user["id"], cost)

            meta = {
                "size": req.size,
                "quality": req.quality,
                "style": req.style,
                "model": request_model,
                "reference_image_url": req.reference_image_url,
                "reference_image_urls": req.reference_image_urls,
            }
            db.log_image(
                user_id=current_user["id"] if current_user else None,
                filename=filename,
                prompt=req.prompt,
                subject=req.subject,
                grade=req.grade,
                metadata=meta,
            )

            remaining = None
            if current_user:
                updated_user = db.get_user_by_id(current_user["id"])
                remaining = max(0, updated_user["quota_limit"] - updated_user["quota_used"])

            return {
                "success": True,
                "url": f"/static/generated/{filename}",
                "remaining_quota": remaining,
            }

        raise HTTPException(status_code=500, detail="Generation failed")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/generate/modify")
async def generate_modify(
    req: ModifyGenRequest,
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    try:
        base_model = (_get_default_model("image") or "").strip()
        if not base_model:
            raise HTTPException(status_code=400, detail="请先在模型配置中添加绘图模型")
        model_cost = _get_model_cost("image", base_model)
        cost = model_cost if isinstance(model_cost, int) else (2 if base_model and "gemini" in base_model.lower() else 1)

        mode, runtime_key, runtime_base_url = determine_execution_mode(
            current_user,
            x_model_key,
            cost=cost,
            service="image",
            model=base_model,
        )
        if runtime_base_url is None and x_model_base_url:
            runtime_base_url = x_model_base_url
        _enforce_rate_limit(request, current_user)

        if not req.original_image_url.startswith("/static/generated/"):
            raise HTTPException(status_code=400, detail="Invalid image URL")

        filename = unquote(os.path.basename(req.original_image_url))
        original_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(original_path):
            raise HTTPException(status_code=404, detail="Original image not found")

        timestamp = int(time.time())
        safe_prompt = sanitize_filename(req.prompt)
        new_filename = f"modified_{safe_prompt}_{timestamp}.png"

        image_url = None
        candidates = _build_model_candidates(
            "image",
            model=base_model,
            runtime_key=runtime_key,
            runtime_base_url=runtime_base_url,
            fallback_base_url=runtime_base_url,
        )
        for candidate in candidates:
            image_url = img_gen.generate_modified_image(
                req.prompt,
                [original_path],
                base_url=candidate.get("base_url"),
                api_key=candidate.get("key"),
                model=base_model,
            )
            if image_url:
                break

        if image_url:
            save_path = os.path.join(GENERATED_DIR, new_filename)
            if img_gen.download_image(image_url, save_path):
                create_thumbnail(save_path)

                if mode == "system" and current_user:
                    db.update_user_quota(current_user["id"], cost)

                parent_meta = db.get_image_metadata(filename)
                subject = parent_meta["subject"] if parent_meta else "general"
                grade = parent_meta["grade"] if parent_meta else "general"

                db.log_image(
                    user_id=current_user["id"] if current_user else None,
                    filename=new_filename,
                    prompt=req.prompt,
                    subject=subject,
                    grade=grade,
                    metadata={"parent": filename, "type": "modification"},
                )

                remaining = 0
                if current_user:
                    updated_user = db.get_user_by_id(current_user["id"])
                    remaining = updated_user["quota_limit"] - updated_user["quota_used"]

                return {
                    "success": True,
                    "url": f"/static/generated/{new_filename}",
                    "remaining_quota": max(0, remaining),
                }
        raise HTTPException(status_code=500, detail="Modification failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/generate/batch")
async def generate_batch(
    req: BatchGenRequest,
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    try:
        if current_user is None:
            raise HTTPException(status_code=403, detail="Batch generation requires login.")
        system_keys = req.system_keys or list(batch_gen.system_prompts.keys())
        req_indices = req.requirement_indices or list(range(len(batch_gen.requirement_prompts)))
        if not system_keys or not req_indices:
            raise HTTPException(status_code=400, detail="No batch tasks selected")

        total_tasks = len(system_keys) * len(req_indices)
        if total_tasks > MAX_BATCH_TASKS:
            raise HTTPException(status_code=400, detail=f"Batch task limit exceeded ({total_tasks}/{MAX_BATCH_TASKS}).")

        request_model = (req.model or _get_default_model("image") or "").strip()
        if not request_model:
            raise HTTPException(status_code=400, detail="请先在模型配置中添加绘图模型")
        model_cost = _get_model_cost("image", request_model)
        cost_per = model_cost if isinstance(model_cost, int) else (2 if request_model and "gemini" in request_model.lower() else 1)
        total_cost = cost_per * (len(system_keys) * len(req_indices))

        mode, runtime_key, runtime_base_url = determine_execution_mode(
            current_user,
            x_model_key,
            cost=total_cost,
            service="image",
            model=request_model,
        )
        if runtime_base_url is None and x_model_base_url:
            runtime_base_url = x_model_base_url
        _enforce_rate_limit(request, current_user)

        combos = [{"system_key": sk, "requirement_index": idx} for sk in system_keys for idx in req_indices]
        candidates = _build_model_candidates(
            "image",
            model=request_model,
            runtime_key=runtime_key,
            runtime_base_url=runtime_base_url,
            fallback_base_url=runtime_base_url,
        )
        results = None
        for candidate in candidates:
            results = batch_gen.generate_batch(
                custom_combinations=combos,
                model=request_model,
                base_url=candidate.get("base_url"),
                api_key=candidate.get("key"),
                optimize=req.optimize,
                output_dir=GENERATED_DIR,
                max_workers=BATCH_WORKERS,
                delay_seconds=BATCH_DELAY_SECONDS,
            )
            if results and results.get("successful", 0) > 0:
                break
        if not isinstance(results, dict):
            raise HTTPException(status_code=502, detail="Batch generation failed. Please check model/key or try again.")

        items_out = []
        for item in results.get("items", []):
            file_path = item.get("file_path")
            if file_path:
                create_thumbnail(file_path)
                filename = os.path.basename(file_path)
                url = f"/static/generated/{filename}"
                items_out.append(
                    {
                        "id": item.get("id"),
                        "url": url,
                        "prompt": item.get("prompt"),
                        "system_prompt": item.get("system_prompt"),
                        "requirement_prompt": item.get("requirement_prompt"),
                    }
                )
                try:
                    db.log_image(
                        user_id=current_user["id"] if current_user else None,
                        filename=filename,
                        prompt=item.get("prompt") or "",
                        subject="general",
                        grade="general",
                        metadata={
                            "batch": True,
                            "system_prompt": item.get("system_prompt"),
                            "requirement_prompt": item.get("requirement_prompt"),
                            "model": request_model,
                        },
                    )
                except Exception:
                    pass

        if mode == "system" and current_user:
            db.update_user_quota(current_user["id"], cost_per * results.get("successful", 0))

        return {
            "success": results.get("success", True),
            "total_tasks": results.get("total_tasks", 0),
            "successful": results.get("successful", 0),
            "failed": results.get("failed", 0),
            "items": items_out,
            "errors": results.get("errors", []),
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/optimize_prompt")
async def optimize_prompt_endpoint(
    req: OptimizePromptRequest,
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    try:
        prompt_default = _get_default_model("prompt")
        preferred_model = (req.model or prompt_default or "").strip()
        prompt_channel = _normalize_prompt_channel(req.channel)
        prompt_model_chain = _build_prompt_model_chain(preferred_model, prompt_channel)
        if not prompt_model_chain:
            image_default = (req.model or _get_default_model("image") or "").strip()
            if not image_default:
                raise HTTPException(status_code=400, detail="请先在模型配置中添加提示词优化模型")
            prompt_model_chain = [image_default]
        _enforce_rate_limit(request, current_user)

        errors: List[str] = []
        attempted_models: List[str] = []
        last_auth_error: Optional[HTTPException] = None

        for prompt_model in prompt_model_chain:
            # Prefer dedicated prompt service; fallback to image service for legacy compatibility.
            for prompt_service in ("prompt", "image"):
                if prompt_service == "image" and prompt_channel:
                    # Channel mode is prompt-first, no cross-service fallback.
                    continue
                try:
                    _, runtime_key, runtime_base_url = determine_execution_mode(
                        current_user,
                        x_model_key,
                        cost=1,
                        service=prompt_service,
                        model=prompt_model,
                    )
                except HTTPException as auth_error:
                    if auth_error.status_code in (401, 403):
                        last_auth_error = auth_error
                        errors.append(f"{prompt_model}@{prompt_service}: {auth_error.detail}")
                        continue
                    raise

                if runtime_base_url is None and x_model_base_url:
                    runtime_base_url = x_model_base_url

                candidates = _build_model_candidates(
                    prompt_service,
                    model=prompt_model,
                    runtime_key=runtime_key,
                    runtime_base_url=runtime_base_url,
                    fallback_base_url=runtime_base_url,
                )
                if not candidates:
                    errors.append(f"{prompt_model}@{prompt_service}: no available key candidates")
                    continue

                for candidate in candidates:
                    attempted_models.append(prompt_model)
                    optimized = img_gen.optimize_prompt(
                        req.prompt,
                        subject=req.subject,
                        model=prompt_model,
                        api_key=candidate.get("key"),
                        base_url=candidate.get("base_url"),
                    )
                    if optimized:
                        return {
                            "success": True,
                            "optimized_prompt": optimized,
                            "model": prompt_model,
                            "channel": prompt_channel,
                        }
                    last_error = getattr(img_gen, "last_error", None) or {}
                    if last_error.get("message"):
                        errors.append(f"{prompt_model}@{prompt_service}: {last_error.get('message')}")
                    else:
                        errors.append(f"{prompt_model}@{prompt_service}: optimization returned empty")

        if last_auth_error and not attempted_models:
            raise last_auth_error

        model_chain_text = ", ".join(prompt_model_chain[:6])
        detail = f"Prompt optimization failed. Tried models: {model_chain_text}"
        if errors:
            detail = f"{detail}. Last errors: {' | '.join(errors[-3:])}"
        raise HTTPException(status_code=502, detail=detail)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
