import os
import time
import tempfile
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app_state import AUDIO_DIR, BATCH_DIR, GENERATED_DIR, UPLOAD_DIR, batch_gen
from schemas import BatchDownloadRequest

router = APIRouter()


def _cleanup_temp_file(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


@router.post("/api/download/batch")
async def download_batch(req: BatchDownloadRequest):
    if not req.filenames and not req.items:
        raise HTTPException(status_code=400, detail="No files selected")

    normalized_items = []
    seen = set()
    if req.items:
        for raw_item in req.items:
            if not isinstance(raw_item, dict):
                continue
            safe_name = os.path.basename(str(raw_item.get("filename") or "").strip())
            download_name = os.path.basename(str(raw_item.get("download_name") or "").strip())
            if not safe_name or safe_name in seen:
                continue
            seen.add(safe_name)
            normalized_items.append(
                {
                    "filename": safe_name,
                    "download_name": download_name or safe_name,
                }
            )
    else:
        for raw_name in req.filenames:
            safe_name = os.path.basename(str(raw_name or "").strip())
            if not safe_name or safe_name in seen:
                continue
            seen.add(safe_name)
            normalized_items.append({"filename": safe_name, "download_name": safe_name})

    if not normalized_items:
        raise HTTPException(status_code=400, detail="No valid files selected")

    fd, tmp_zip_path = tempfile.mkstemp(prefix="batch_", suffix=".zip")
    os.close(fd)

    found_count = 0
    used_archive_names = set()
    try:
        # Most generated media files are already compressed; ZIP_STORED avoids
        # CPU-heavy re-compression and significantly reduces package wait time.
        with zipfile.ZipFile(tmp_zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
            for item in normalized_items:
                fname = item["filename"]
                archive_name = item["download_name"]
                if archive_name in used_archive_names:
                    name, ext = os.path.splitext(archive_name)
                    suffix = 2
                    while f"{name}_{suffix}{ext}" in used_archive_names:
                        suffix += 1
                    archive_name = f"{name}_{suffix}{ext}"
                for base_dir in (GENERATED_DIR, UPLOAD_DIR, AUDIO_DIR, BATCH_DIR):
                    base_abs = os.path.abspath(base_dir)
                    fpath = os.path.abspath(os.path.join(base_abs, fname))
                    if not fpath.startswith(base_abs + os.sep):
                        continue
                    if os.path.isfile(fpath):
                        zf.write(fpath, archive_name)
                        found_count += 1
                        used_archive_names.add(archive_name)
                        break
    except Exception as exc:
        _cleanup_temp_file(tmp_zip_path)
        raise HTTPException(status_code=500, detail=f"Failed to prepare zip: {exc}") from exc

    if found_count <= 0:
        _cleanup_temp_file(tmp_zip_path)
        raise HTTPException(status_code=404, detail="No downloadable files found")

    zip_filename = f"Batch_{int(time.time())}.zip"
    return FileResponse(
        tmp_zip_path,
        media_type="application/zip",
        filename=zip_filename,
        background=BackgroundTask(_cleanup_temp_file, tmp_zip_path),
    )


@router.get("/api/config")
async def get_batch_config():
    return {
        "system_prompts": batch_gen.system_prompts,
        "requirement_prompts": batch_gen.requirement_prompts,
        "generation_history": batch_gen.generation_history[-20:],
    }
