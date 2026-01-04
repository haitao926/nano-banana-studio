from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import glob
import sys
import json
import secrets
import shutil
from urllib.parse import quote
import zipfile
import io
import re
import time
from PIL import Image

# 确保能导入 core 模块
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.image_generator import ImageGenerator
from core.batch_image_generator import BatchImageGenerator
from core.rate_limiter import RateLimiter

app = FastAPI(title="智绘工坊 API")

# --- 配置 ---
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin888")
# 简单的 token 存储 (生产环境应使用 Redis 或 JWT)
ADMIN_TOKENS = set()

# --- 路径配置 (适配 PyInstaller 打包) ---
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
    EXEC_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXEC_DIR = BUNDLE_DIR

if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)

# --- CORS 设置 ---
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

# --- 静态资源路径 ---
STATIC_DIR = os.path.join(EXEC_DIR, "static")
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")
BATCH_DIR = os.path.join(STATIC_DIR, "batch")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")

os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(BATCH_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- 初始化核心类 ---
DATA_DIR = os.path.join(EXEC_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

img_gen = ImageGenerator()
batch_gen = BatchImageGenerator()
rate_limiter = RateLimiter(db_path=os.path.join(DATA_DIR, "rate_limit.db"))

# --- 缩略图工具 ---
def create_thumbnail(image_path: str):
    """为指定图片生成缩略图 (.thumb.jpg)"""
    try:
        if not os.path.exists(image_path): return None
        
        # 构造缩略图路径: name.png -> name.thumb.jpg
        base, _ = os.path.splitext(image_path)
        thumb_path = f"{base}.thumb.jpg"
        
        if os.path.exists(thumb_path):
            return thumb_path
            
        with Image.open(image_path) as img:
            # 转换为 RGB (防止 PNG 透明度问题)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # 缩略图尺寸: 400x400 (保持比例)
            img.thumbnail((400, 400))
            img.save(thumb_path, "JPEG", quality=70)
            return thumb_path
    except Exception as e:
        print(f"Error creating thumbnail for {image_path}: {e}")
        return None

def scan_and_create_thumbnails():
    """后台任务：扫描文件夹并补充缺失的缩略图"""
    print("🔄 Starting background thumbnail generation...")
    extensions = ["*.png", "*.jpg", "*.jpeg"]
    count = 0
    for ext in extensions:
        # 大小写敏感系统可能需要扫描大写，这里主要针对生成出的 .png
        files = glob.glob(os.path.join(GENERATED_DIR, ext))
        for f in files:
            if f.endswith(".thumb.jpg"): continue
            
            # 检查是否有对应 thumb
            base, _ = os.path.splitext(f)
            thumb_path = f"{base}.thumb.jpg"
            if not os.path.exists(thumb_path):
                create_thumbnail(f)
                count += 1
    if count > 0:
        print(f"✅ Generated {count} missing thumbnails.")
    else:
        print("✅ No missing thumbnails found.")

# --- 访问控制 ---
USER_ACCESS_KEYS = set([k.strip() for k in os.getenv("USER_ACCESS_KEYS", "skd-user-key").split(",") if k.strip()])

def check_access_permission(request: Request, x_model_key: Optional[str] = None) -> Dict:
    client_ip = request.client.host
    if x_model_key:
        return {"type": "custom", "api_key": x_model_key}
    is_lan = client_ip.startswith("10.20.") or client_ip in ["127.0.0.1", "::1", "localhost"]
    if is_lan:
        allowed, msg = rate_limiter.check_limit(client_ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=f"LAN Rate Limit Exceeded: {msg}")
        return {"type": "lan"}
    raise HTTPException(status_code=403, detail="Access denied. Please input your own API Key.")

def check_admin_token(x_admin_token: str = Header(None)):
    """管理员鉴权依赖"""
    if not x_admin_token or x_admin_token not in ADMIN_TOKENS:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return x_admin_token

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*50)
    print("🍌 ReOpenInnoLab-智绘工坊 is READY!")
    print("👉 Open in Browser: http://localhost:6060")
    print("="*50 + "\n")
    # 启动后台任务生成缩略图
    import threading
    threading.Thread(target=scan_and_create_thumbnails, daemon=True).start()

# --- 辅助函数 ---
def sanitize_filename(text: str) -> str:
    clean_text = text.replace(" ", "_")
    clean_text = re.sub(r'[\\/:*?"<>|]', '', clean_text)
    return clean_text[:50]

# --- 数据模型 ---
class SingleGenRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"
    subject: str = "general"
    grade: str = "general"
    reference_image_url: Optional[str] = None
    reference_image_urls: List[str] = []

class BatchGenRequest(BaseModel):
    system_keys: List[str]
    requirement_indices: List[int]

class DownloadBatchRequest(BaseModel):
    filenames: List[str]

class ModifyGenRequest(BaseModel):
    prompt: str
    original_image_url: str

class OptimizePromptRequest(BaseModel):
    prompt: str
    subject: str = "general"

class ApiSettingsRequest(BaseModel):
    base_url: str
    model: str
    api_key: Optional[str] = None

class AdminLoginRequest(BaseModel):
    password: str

class ToggleFeatureRequest(BaseModel):
    filename: str
    featured: bool

# --- Admin API ---

@app.post("/api/admin/login")
async def admin_login(req: AdminLoginRequest):
    if req.password == ADMIN_PASSWORD:
        token = secrets.token_hex(16)
        ADMIN_TOKENS.add(token)
        return {"success": True, "token": token}
    raise HTTPException(status_code=401, detail="Incorrect password")

@app.get("/api/admin/stats")
async def admin_stats(token: str = Depends(check_admin_token)):
    # 1. IP Stats
    ip_stats = rate_limiter.get_all_stats()
    
    # 2. Subject & Grade Stats (Scanning JSONs)
    subject_counts = {}
    grade_counts = {}
    
    # Scan all json files in generated dir
    json_files = glob.glob(os.path.join(GENERATED_DIR, "*.json"))
    for jf in json_files:
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sub = data.get("subject", "general")
                grad = data.get("grade", "general")
                subject_counts[sub] = subject_counts.get(sub, 0) + 1
                grade_counts[grad] = grade_counts.get(grad, 0) + 1
        except: pass
        
    return {
        "ip_stats": ip_stats,
        "subject_counts": subject_counts,
        "grade_counts": grade_counts
    }

@app.post("/api/admin/toggle_feature")
async def toggle_feature(req: ToggleFeatureRequest, token: str = Depends(check_admin_token)):
    # req.filename 通常是 "abc.png"
    # 我们需要找到对应的 metadata json
    # 可能是 "abc.json" (新版) 或 "abc.png.json" (旧版兼容?)
    # 目前主要是 "abc.json" (name without ext)
    
    base_name = os.path.splitext(req.filename)[0]
    json_path = os.path.join(GENERATED_DIR, f"{base_name}.json")
    
    if not os.path.exists(json_path):
        # 如果不存在 metadata，可能需要创建一个？
        # 或者尝试找 png 对应的
        pass
        
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data['featured'] = req.featured
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            return {"success": True, "featured": req.featured}
        except Exception as e:
             raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Metadata not found")

# --- Normal API ---

@app.get("/api/quota")
async def get_quota_endpoint(request: Request):
    client_ip = request.client.host
    try:
        remaining = rate_limiter.get_remaining_quota(client_ip)
    except Exception:
        remaining = 0
    return {"remaining": remaining, "max": 20}

@app.post("/api/optimize_prompt")
async def optimize_prompt_endpoint(
    req: OptimizePromptRequest,
    request: Request,
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url")
):
    try:
        access_info = check_access_permission(request, x_model_key)
        # 暂不使用 custom key 进行 optimize，沿用系统默认 (Token消耗低)
        optimized = img_gen.optimize_prompt(req.prompt, subject=req.subject)
        return {"success": True, "optimized_prompt": optimized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings/api")
async def get_api_settings():
    try:
        current_cfg = img_gen.config or {}
        api_cfg = current_cfg.get("api", {}) or {}
        auth_cfg = current_cfg.get("auth", {}) or {}
        api_key = auth_cfg.get("api_key", "")
        return {
            "base_url": api_cfg.get("base_url", ""),
            "model": api_cfg.get("model", ""),
            "has_api_key": bool(api_key),
            "api_key_preview": api_key[-4:] if api_key else ""
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/api")
async def update_api_settings(req: ApiSettingsRequest):
    try:
        base_url = req.base_url.strip()
        model = req.model.strip()
        if not base_url or not model:
            raise HTTPException(status_code=400, detail="Required fields missing")

        new_api_key = req.api_key.strip() if req.api_key is not None else None
        if new_api_key == "": new_api_key = None

        img_gen.update_config(base_url=base_url, model=model, api_key=new_api_key)
        if hasattr(batch_gen, "generator") and batch_gen.generator:
            batch_gen.generator.reload_config()

        return {"success": True}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config():
    batch_gen.load_config()
    return {
        "system_prompts": batch_gen.system_prompts,
        "requirement_prompts": batch_gen.requirement_prompts
    }

@app.post("/api/generate/batch")
async def generate_batch_endpoint(req: BatchGenRequest, request: Request, x_access_key: Optional[str] = Header(None)):
    try:
        check_access_permission(request, x_access_key)
        custom_combinations = []
        target_systems = req.system_keys or list(batch_gen.system_prompts.keys())
        target_reqs = req.requirement_indices or list(range(len(batch_gen.requirement_prompts)))
             
        for sys_key in target_systems:
            for req_idx in target_reqs:
                custom_combinations.append({"system_key": sys_key, "requirement_index": req_idx})
        
        results = batch_gen.generate_batch(custom_combinations=custom_combinations, output_dir=BATCH_DIR)
        
        generated_files = []
        for task_id, path in results.get("files", {}).items():
            filename = os.path.basename(path)
            generated_files.append({
                "id": task_id,
                "url": f"/static/batch/{quote(filename)}",
                "filename": filename
            })
            
        return {
            "success": True,
            "results": generated_files,
            "total": results["total_tasks"],
            "successful": results["successful"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/batch")
async def download_batch_endpoint(req: DownloadBatchRequest):
    try:
        if not req.filenames: raise HTTPException(status_code=400, detail="No files")
        import time
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in req.filenames:
                p1 = os.path.join(BATCH_DIR, filename)
                p2 = os.path.join(GENERATED_DIR, filename)
                target = p1 if os.path.exists(p1) else (p2 if os.path.exists(p2) else None)
                if target: zf.write(target, filename)
        
        zip_buffer.seek(0)
        zip_filename = f"batch_download_{int(time.time())}.zip"
        return StreamingResponse(
            iter([zip_buffer.getvalue()]), 
            media_type="application/zip", 
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/modify")
async def generate_modify(
    req: ModifyGenRequest, 
    request: Request, 
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url")
):
    try:
        access_info = check_access_permission(request, x_model_key)
        client_ip = request.client.host
        
        runtime_api_key = access_info.get("api_key")
        runtime_base_url = x_model_base_url

        if not req.original_image_url.startswith("/static/generated/"):
            raise HTTPException(status_code=400, detail="Invalid image URL")
        
        filename = os.path.basename(req.original_image_url)
        original_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(original_path):
            raise HTTPException(status_code=404, detail="Original image not found")

        timestamp = int(time.time())
        safe_prompt = sanitize_filename(req.prompt)
        new_filename = f"modified_{safe_prompt}_{timestamp}.png"
        new_meta_filename = f"modified_{safe_prompt}_{timestamp}.json"
        
        image_url = img_gen.generate_modified_image(
            req.prompt, 
            [original_path],
            base_url=runtime_base_url,
            api_key=runtime_api_key
        )
        
        if image_url:
            save_path = os.path.join(GENERATED_DIR, new_filename)
            if img_gen.download_image(image_url, save_path):
                # 生成缩略图
                create_thumbnail(save_path)

                if access_info["type"] == "lan":
                    rate_limiter.record_usage(client_ip)
                remaining = rate_limiter.get_remaining_quota(client_ip)
                
                meta_data = {
                    "prompt": req.prompt,
                    "parent_image": filename,
                    "type": "modification",
                    "timestamp": timestamp,
                    "ip": client_ip
                }
                with open(os.path.join(GENERATED_DIR, new_meta_filename), 'w', encoding='utf-8') as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)

                return {
                    "success": True,
                    "url": f"/static/generated/{new_filename}",
                    "remaining_quota": remaining
                }
        raise HTTPException(status_code=500, detail="Modification failed")
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        timestamp = int(time.time())
        file_ext = os.path.splitext(file.filename)[1] or ".png"
        filename = f"upload_{timestamp}_{secrets.token_hex(4)}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"success": True, "url": f"/static/uploads/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/single")
async def generate_single(
    req: SingleGenRequest, 
    request: Request, 
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url")
):
    try:
        access_info = check_access_permission(request, x_model_key)
        client_ip = request.client.host
        
        runtime_api_key = access_info.get("api_key")
        runtime_base_url = x_model_base_url

        timestamp = int(time.time())
        safe_prompt = sanitize_filename(req.prompt)
        filename = f"{safe_prompt}_{timestamp}.png"
        meta_filename = f"{safe_prompt}_{timestamp}.json"
        
        enhanced_prompt = req.prompt
        context_prompts = []
        if req.subject and req.subject != "general":
            context_prompts.append(f"Subject: {req.subject}")
        if req.grade and req.grade != "general":
            context_prompts.append(f"Target Audience: {req.grade} students")
        
        if context_prompts:
             enhanced_prompt += " (" + ", ".join(context_prompts) + ")"
        
        is_english = req.subject and ("english" in req.subject.lower() or "英语" in req.subject.lower())
        enhanced_prompt += ", (text in image must be in English)" if is_english else ", (text in image must be in Chinese)"

        # 临时配置
        original_config = img_gen.config.copy()
        img_gen.config["image"]["size"] = req.size
        if "image" not in img_gen.config: img_gen.config["image"] = {}
        img_gen.config["image"]["quality"] = req.quality
        img_gen.config["image"]["style"] = req.style
        
        final_path = None
        
        all_ref_urls = list(set([u for u in [req.reference_image_url] + req.reference_image_urls if u]))
        
        if all_ref_urls:
            ref_paths = []
            for ref_url in all_ref_urls:
                ref_filename = os.path.basename(ref_url)
                p = os.path.join(UPLOAD_DIR, ref_filename) if "uploads" in ref_url else os.path.join(GENERATED_DIR, ref_filename)
                if os.path.exists(p): ref_paths.append(p)
            
            if ref_paths:
                image_url = img_gen.generate_modified_image(
                    enhanced_prompt, 
                    ref_paths,
                    base_url=runtime_base_url,
                    api_key=runtime_api_key
                )
                if image_url:
                    save_path = os.path.join(GENERATED_DIR, filename)
                    if img_gen.download_image(image_url, save_path):
                        final_path = save_path
        
        if not final_path:
             final_path = img_gen.generate_and_download(
                enhanced_prompt,
                filename,
                folder=GENERATED_DIR,
                base_url=runtime_base_url,
                api_key=runtime_api_key
            )
        
        img_gen.config = original_config
        
        if final_path:
            # 生成缩略图
            create_thumbnail(final_path)

            if access_info["type"] == "lan":
                rate_limiter.record_usage(client_ip)
            
            meta_data = {
                "prompt": req.prompt, 
                "enhanced_prompt": enhanced_prompt,
                "subject": req.subject,
                "grade": req.grade,
                "size": req.size,
                "quality": req.quality,
                "style": req.style,
                "reference_images": all_ref_urls,
                "timestamp": timestamp,
                "ip": client_ip,
                "featured": False 
            }
            with open(os.path.join(GENERATED_DIR, meta_filename), 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)

            remaining = rate_limiter.get_remaining_quota(client_ip)
            return {
                "success": True, 
                "url": f"/static/generated/{filename}",
                "remaining_quota": remaining
            }
        else:
            raise HTTPException(status_code=500, detail="Generation failed")
            
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gallery")
async def get_gallery():
    try:
        files = []
        # 扫描所有图片
        extensions = ["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"]
        all_images = []
        for ext in extensions:
            all_images.extend(glob.glob(os.path.join(GENERATED_DIR, ext)))
            
        all_images = list(set(all_images))

        for f in all_images:
            if f.endswith(".thumb.jpg"): continue # 跳过缩略图文件

            basename = os.path.basename(f)
            name_without_ext = os.path.splitext(basename)[0]
            json_path = os.path.join(GENERATED_DIR, f"{name_without_ext}.json")
            
            meta = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as jf:
                        meta = json.load(jf)
                except: pass
            
            encoded_name = quote(basename)
            url = f"/static/generated/{encoded_name}"
            
            # 检查是否有缩略图
            thumb_name = f"{name_without_ext}.thumb.jpg"
            thumb_path = os.path.join(GENERATED_DIR, thumb_name)
            if os.path.exists(thumb_path):
                thumbnail_url = f"/static/generated/{quote(thumb_name)}"
            else:
                thumbnail_url = url # 降级为原图

            files.append({
                "url": url,
                "thumbnail_url": thumbnail_url,
                "name": basename,
                "type": "single",
                "time": os.path.getmtime(f),
                "subject": meta.get("subject", "general"),
                "grade": meta.get("grade", "general"),
                "prompt": meta.get("prompt", name_without_ext),
                "featured": meta.get("featured", False)
            })
        
        files.sort(key=lambda x: x["time"], reverse=True)
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if getattr(sys, 'frozen', False):
    FRONTEND_DIST_DIR = os.path.join(BUNDLE_DIR, "dist")
else:
    FRONTEND_DIST_DIR = os.path.join(BUNDLE_DIR, "..", "frontend", "dist")

FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")

if os.path.exists(FRONTEND_DIST_DIR):
    print(f"📦 Found frontend build at {FRONTEND_DIST_DIR}")
    if os.path.exists(FRONTEND_ASSETS_DIR):
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
else:
    print("⚠️ Frontend dist not found.")