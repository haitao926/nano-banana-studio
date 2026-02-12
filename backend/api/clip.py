import json
import os
import secrets
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app_state import BASE_DIR, CLIP_DIR
from deps import get_current_user
from helpers import _resolve_clip_asset_path
from schemas import ClipRenderRequest

router = APIRouter()


@router.post("/api/clip/render")
async def render_clip(req: ClipRenderRequest, current_user: Dict = Depends(get_current_user)):
    try:
        cfg = req.config or {}
        if not isinstance(cfg, dict):
            raise HTTPException(status_code=400, detail="Invalid config")

        bg_raw = cfg.get("background")
        bg_path = _resolve_clip_asset_path(bg_raw)
        if not bg_path:
            raise HTTPException(status_code=400, detail="Invalid background path")

        left_cfg = cfg.get("left") or {}
        right_cfg = cfg.get("right") or {}

        left_items = left_cfg.get("items") or []
        right_items = right_cfg.get("items") or []
        if not right_items:
            raise HTTPException(status_code=400, detail="Right videos required")

        def map_items(items: List[Dict]) -> List[Dict]:
            mapped: List[Dict] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                file_raw = item.get("file")
                file_path = _resolve_clip_asset_path(file_raw)
                if not file_path:
                    raise HTTPException(status_code=400, detail=f"Invalid asset path: {file_raw}")
                new_item = dict(item)
                new_item["file"] = file_path
                mapped.append(new_item)
            return mapped

        left_mapped = map_items(left_items)
        right_mapped = map_items(right_items)

        audio_cfg = cfg.get("audio") if isinstance(cfg.get("audio"), dict) else None
        audio_mapped = None
        if audio_cfg and audio_cfg.get("file"):
            audio_path = _resolve_clip_asset_path(audio_cfg.get("file"))
            if not audio_path:
                raise HTTPException(status_code=400, detail="Invalid audio path")
            audio_mapped = dict(audio_cfg)
            audio_mapped["file"] = audio_path

        output_name = f"clip_{int(time.time())}_{secrets.token_hex(3)}.mp4"
        output_path = os.path.join(CLIP_DIR, output_name)
        config_path = os.path.join(CLIP_DIR, f"clip_{int(time.time())}_{secrets.token_hex(3)}.json")

        render_cfg = {
            "canvas": cfg.get("canvas") or {},
            "background": bg_path,
            "left": {**left_cfg, "items": left_mapped},
            "right": {**right_cfg, "items": right_mapped},
            "output": output_path,
        }
        if audio_mapped:
            render_cfg["audio"] = audio_mapped

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(render_cfg, f, ensure_ascii=False, indent=2)

        root_dir = os.path.abspath(os.path.join(BASE_DIR, ".."))
        render_script = os.path.join(root_dir, "AI 剪辑", "render.py")
        if not os.path.exists(render_script):
            raise HTTPException(status_code=500, detail="Render script not found")

        import subprocess

        subprocess.run(["python3", render_script, "--config", config_path], check=True)
        return {"success": True, "url": f"/static/clips/{output_name}"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
