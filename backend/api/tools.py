import io
import os
import secrets
import time
import zipfile
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from app_state import GENERATED_DIR, UPLOAD_DIR
from schemas import CropRequest

router = APIRouter()


@router.post("/api/tools/crop_and_zip")
async def crop_and_zip(req: CropRequest):
    try:
        filename = unquote(os.path.basename(req.image_url))
        file_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(file_path):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Image not found")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            with Image.open(file_path) as img:
                for i, crop in enumerate(req.crops):
                    x, y, w, h = crop["x"], crop["y"], crop["w"], crop["h"]
                    if w <= 0 or h <= 0:
                        continue
                    cropped = img.crop((x, y, x + w, y + h))
                    img_byte_arr = io.BytesIO()
                    fmt = img.format or "PNG"
                    cropped.save(img_byte_arr, format=fmt)
                    zf.writestr(f"scene_{i + 1}.{fmt.lower()}", img_byte_arr.getvalue())

        zip_buffer.seek(0)
        zip_filename = f"scenes_{int(time.time())}.zip"
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"},
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/tools/crop_to_urls")
async def crop_to_urls(req: CropRequest):
    try:
        filename = unquote(os.path.basename(req.image_url))
        file_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(file_path):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail=f"Image not found: {filename}")

        urls = []
        with Image.open(file_path) as img:
            for i, crop in enumerate(req.crops):
                x, y, w, h = crop["x"], crop["y"], crop["w"], crop["h"]
                if w <= 0 or h <= 0:
                    continue

                cropped = img.crop((x, y, x + w, y + h))

                timestamp = int(time.time())
                new_filename = f"crop_{timestamp}_{i}_{secrets.token_hex(4)}.png"
                save_path = os.path.join(UPLOAD_DIR, new_filename)

                cropped.save(save_path, "PNG")
                urls.append(f"/static/uploads/{new_filename}")

        return {"success": True, "urls": urls}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Crop Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
