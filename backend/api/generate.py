import base64
import copy
import os
import time
from typing import Dict, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app_state import GENERATED_DIR, MAX_BATCH_TASKS, batch_gen, db, img_gen
from deps import get_current_user_optional
from helpers import (
    _build_model_candidates,
    _dedupe_preserve_order,
    _download_reference_image,
    _download_public_image_bytes,
    _enforce_rate_limit,
    _get_default_model,
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
            seedream_max_images = req.seedream_max_images if req.seedream_max_images and req.seedream_max_images > 0 else 4

            all_ref_urls = _dedupe_preserve_order(
                [u for u in [req.reference_image_url] + (req.reference_image_urls or []) if u]
            )
            if all_ref_urls:
                if is_seedream:
                    seedream_image = _build_seedream_image_param(all_ref_urls[0])
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
                            group_mode=req.seedream_group,
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
                            group_mode=req.seedream_group,
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
        _, runtime_key, runtime_base_url = determine_execution_mode(
            current_user,
            x_model_key,
            cost=1,
            service=prompt_service,
            model=prompt_model,
        )
        if runtime_base_url is None and x_model_base_url:
            runtime_base_url = x_model_base_url
        _enforce_rate_limit(request, current_user)

        optimized = None
        prompt_default = _get_default_model("prompt")
        prompt_model = (prompt_default or req.model or "").strip()
        if not prompt_model:
            raise HTTPException(status_code=400, detail="请先在模型配置中添加绘图模型")
        prompt_service = "prompt" if prompt_default else "image"
        candidates = _build_model_candidates(
            prompt_service,
            model=prompt_model,
            runtime_key=runtime_key,
            runtime_base_url=runtime_base_url,
            fallback_base_url=runtime_base_url,
        )
        for candidate in candidates:
            optimized = img_gen.optimize_prompt(
                req.prompt,
                subject=req.subject,
                model=prompt_model,
                api_key=candidate.get("key"),
                base_url=candidate.get("base_url"),
            )
            if optimized:
                break
        if not optimized:
            raise HTTPException(status_code=502, detail="Prompt optimization failed. Check model/key or rate limit.")
        return {"success": True, "optimized_prompt": optimized}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
