from fastapi import APIRouter

from helpers import _get_model_catalog

router = APIRouter()


@router.get("/api/models")
async def get_models():
    catalog = _get_model_catalog()
    public_models = []
    for item in catalog:
        if not item.get("enabled", True):
            continue
        public_models.append(
            {
                "model": item.get("model"),
                "label": item.get("label") or item.get("model"),
                "service": item.get("service"),
                "platform": item.get("platform"),
                "cost": item.get("cost"),
            }
        )
    return {"models": public_models}
