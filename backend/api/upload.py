import os
import secrets
import shutil
import time
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app_state import (
    UPLOAD_AUDIO_EXTS,
    UPLOAD_IMAGE_EXTS,
    UPLOAD_MAX_BYTES,
    UPLOAD_MAX_MB,
    UPLOAD_VIDEO_EXTS,
    UPLOAD_DIR,
)
from core.oss_uploader import upload_file_to_oss
from helpers import _enforce_upload_rate_limit, _get_upload_size

router = APIRouter()


@router.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    try:
        _enforce_upload_rate_limit(request)
        size = _get_upload_size(file)
        if size is not None and size > UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large (max {UPLOAD_MAX_MB}MB).")
        timestamp = int(time.time())
        file_ext = os.path.splitext(file.filename)[1] or ".png"
        filename = f"upload_{timestamp}_{secrets.token_hex(4)}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"success": True, "url": f"/static/uploads/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/upload_public")
async def upload_public_file(request: Request, file: UploadFile = File(...)):
    try:
        _enforce_upload_rate_limit(request)
        size = _get_upload_size(file)
        if size is not None and size > UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large (max {UPLOAD_MAX_MB}MB).")
        url = upload_file_to_oss(file)
        return {"success": True, "url": url}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uploads")
async def list_uploads():
    try:
        images = []
        videos = []
        audio = []
        if not os.path.exists(UPLOAD_DIR):
            return {"images": images, "videos": videos, "audio": audio}
        for entry in os.scandir(UPLOAD_DIR):
            if not entry.is_file():
                continue
            name = entry.name
            ext = os.path.splitext(name)[1].lower()
            url = f"/static/uploads/{quote(name)}"
            item = {
                "name": name,
                "url": url,
                "size": entry.stat().st_size,
                "created_at": int(entry.stat().st_mtime),
            }
            if ext in UPLOAD_IMAGE_EXTS:
                images.append(item)
            elif ext in UPLOAD_VIDEO_EXTS:
                videos.append(item)
            elif ext in UPLOAD_AUDIO_EXTS:
                audio.append(item)
        images.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        videos.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        audio.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return {"images": images, "videos": videos, "audio": audio}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
