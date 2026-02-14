import os
import secrets
import time
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app_state import AUDIO_DIR, db
from core.qwen_tts import synthesize_tts
from deps import get_current_user, get_current_user_optional
from helpers import (
    _build_model_candidates,
    _get_default_model,
    _get_model_cost,
    _get_tts_base_url,
    _get_wav_duration_seconds,
    determine_key_execution_mode,
)
from schemas import TTSRequest

router = APIRouter()


@router.get("/api/audio/history")
async def get_audio_history(current_user: Dict = Depends(get_current_user)):
    items = db.get_audio_history(user_id=current_user["id"])
    results = []
    for item in items:
        results.append(
            {
                "id": item.get("id"),
                "url": item.get("url"),
                "type": "audio/wav",
                "prompt": item.get("prompt"),
                "mode": item.get("mode") or "speech",
                "voice": item.get("voice"),
                "model": item.get("model"),
                "duration": item.get("duration"),
                "created_at": item.get("created_at"),
            }
        )
    return results


@router.post("/api/audio/tts")
async def generate_tts(
    req: TTSRequest,
    x_tts_key: Optional[str] = Header(None, alias="x-tts-key"),
    current_user: Optional[Dict] = Depends(get_current_user_optional),
):
    try:
        text = req.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        if req.response_format != "wav":
            raise HTTPException(status_code=400, detail="REST TTS only supports wav output")

        model_name = (req.model or _get_default_model("audio") or "").strip()
        if not model_name:
            raise HTTPException(status_code=400, detail="请先在模型配置中添加音频模型")
        model_cost = _get_model_cost("audio", model_name)
        cost = model_cost if isinstance(model_cost, int) else 1
        mode, runtime_key = determine_key_execution_mode(
            current_user,
            x_tts_key,
            cost=cost,
            header_name="x-tts-key",
            service="audio",
            model=req.model,
        )

        audio_id = f"tts_{int(time.time())}_{secrets.token_hex(4)}"
        tts_base_url = _get_tts_base_url()
        candidates = _build_model_candidates(
            "audio",
            model=model_name,
            runtime_key=runtime_key,
            fallback_base_url=tts_base_url,
        )

        last_error = None
        output_path = None
        mime_type = None
        for candidate in candidates:
            try:
                output_path, mime_type = synthesize_tts(
                    text=text,
                    output_dir=AUDIO_DIR,
                    filename_base=audio_id,
                    voice=req.voice,
                    model=model_name,
                    instructions=req.instructions,
                    optimize_instructions=req.optimize_instructions,
                    response_format=req.response_format,
                    sample_rate=req.sample_rate,
                    mode=req.mode,
                    api_key=candidate.get("key") or runtime_key,
                    base_url=candidate.get("base_url") or tts_base_url,
                    language_type=req.language_type,
                )
                break
            except Exception as e:
                last_error = str(e)
                output_path = None
                mime_type = None
        if not output_path:
            raise HTTPException(status_code=502, detail=f"TTS failed: {last_error or 'unknown error'}")

        duration = _get_wav_duration_seconds(output_path)
        history_item = None
        if current_user:
            history_item = db.log_audio(
                user_id=current_user["id"],
                filename=os.path.basename(output_path),
                url=f"/static/audio/{os.path.basename(output_path)}",
                prompt=text,
                voice=req.voice,
                model=model_name,
                duration=duration,
                mode="speech",
            )
            if mode == "system":
                db.update_user_quota(current_user["id"], 1)

        remaining = None
        if current_user:
            updated_user = db.get_user_by_id(current_user["id"])
            remaining = max(0, updated_user["quota_limit"] - updated_user["quota_used"])

        return {
            "success": True,
            "url": f"/static/audio/{os.path.basename(output_path)}",
            "type": mime_type,
            "voice": req.voice,
            "model": model_name,
            "format": "pcm" if mime_type == "audio/pcm" else "wav",
            "duration": duration,
            "remaining_quota": remaining,
            "history_item": history_item,
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
