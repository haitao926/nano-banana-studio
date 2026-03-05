import os
import sys
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app_state import ADMIN_PASSWORD, BUNDLE_DIR, STATIC_DIR, db
from core.auth_utils import get_password_hash
from helpers import scan_and_sync_db

from api import assistant, admin, audio, auth, batch, clip, digital_human, gallery, generate, models, tools, upload, video

app = FastAPI(title="智绘工坊 API")


def _parse_origins(raw: str) -> List[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:6060"
ALLOWED_ORIGINS = _parse_origins(os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS)) or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routers
app.include_router(auth.router)
app.include_router(batch.router)
app.include_router(generate.router)
app.include_router(models.router)
app.include_router(clip.router)
app.include_router(gallery.router)
app.include_router(upload.router)
app.include_router(audio.router)
app.include_router(video.router)
app.include_router(digital_human.router)
app.include_router(tools.router)
app.include_router(assistant.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup_event():
    print("🍌 ReOpenInnoLab-智绘工坊 Backend Started")
    import threading

    threading.Thread(target=scan_and_sync_db, daemon=True).start()

    if not db.get_user_by_username("admin"):
        db.create_user("admin", get_password_hash(ADMIN_PASSWORD), is_pro=True)
        print("👤 Default admin user created (password: admin888)")


# Frontend Static Serving
if getattr(sys, "frozen", False):
    FRONTEND_DIST_DIR = os.path.join(BUNDLE_DIR, "dist")
else:
    FRONTEND_DIST_DIR = os.path.join(BUNDLE_DIR, "..", "frontend", "dist")

FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")

if os.path.exists(FRONTEND_DIST_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("static/"):
            raise HTTPException(status_code=404)

        file_path = os.path.join(FRONTEND_DIST_DIR, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)

        index_path = os.path.join(FRONTEND_DIST_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend build not found"}
