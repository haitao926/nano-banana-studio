import io
import os
import time
import zipfile

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app_state import AUDIO_DIR, BATCH_DIR, GENERATED_DIR, UPLOAD_DIR, batch_gen
from schemas import BatchDownloadRequest

router = APIRouter()


@router.post("/api/download/batch")
async def download_batch(req: BatchDownloadRequest):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in req.filenames:
            for base_dir in (GENERATED_DIR, UPLOAD_DIR, AUDIO_DIR, BATCH_DIR):
                fpath = os.path.join(base_dir, fname)
                if os.path.exists(fpath):
                    zf.write(fpath, fname)
                    break

    zip_buffer.seek(0)
    zip_filename = f"Batch_{int(time.time())}.zip"
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"},
    )


@router.get("/api/config")
async def get_batch_config():
    return {
        "system_prompts": batch_gen.system_prompts,
        "requirement_prompts": batch_gen.requirement_prompts,
        "generation_history": batch_gen.generation_history[-20:],
    }
