import os
from typing import Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends

from app_state import GENERATED_DIR, db
from deps import get_current_user_optional

router = APIRouter()


@router.get("/api/gallery")
async def get_gallery(current_user: Optional[Dict] = Depends(get_current_user_optional)):
    """
    Returns:
    1. Images owned by current_user
    2. Images marked as featured
    """
    user_id = current_user["id"] if current_user else None

    images = db.get_gallery_images(user_id=user_id)

    results = []
    for img in images:
        filename = img["filename"]
        base, _ = os.path.splitext(filename)
        thumb_name = f"{base}.thumb.jpg"

        if not os.path.exists(os.path.join(GENERATED_DIR, filename)):
            continue

        thumb_path = os.path.join(GENERATED_DIR, thumb_name)
        thumb_url = (
            f"/static/generated/{quote(thumb_name)}"
            if os.path.exists(thumb_path)
            else f"/static/generated/{quote(filename)}"
        )

        results.append(
            {
                "id": filename,
                "name": filename,
                "url": f"/static/generated/{quote(filename)}",
                "thumbnail_url": thumb_url,
                "prompt": img["prompt"],
                "subject": img["subject"],
                "grade": img["grade"],
                "featured": bool(img["featured"]),
                "time": img["timestamp"],
                "is_mine": (user_id is not None) and (img["user_id"] == user_id),
            }
        )

    return results
