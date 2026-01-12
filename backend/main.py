from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, UploadFile, File, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import glob
import sys
import json
import secrets
import shutil
from urllib.parse import quote, unquote
import zipfile
import io
import re
import time
from jose import JWTError, jwt
from PIL import Image

# 确保能导入 core 模块
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.image_generator import ImageGenerator
from core.batch_image_generator import BatchImageGenerator
from core.digital_human import DigitalHumanGenerator
from core.db_manager import DBManager
from core.auth_utils import verify_password, get_password_hash, create_access_token, SECRET_KEY, ALGORITHM

app = FastAPI(title="智绘工坊 API")

# --- 配置 ---
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin888")

# --- 路径配置 ---
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
    EXEC_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXEC_DIR = BUNDLE_DIR

if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)

# --- CORS ---
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

# --- 静态资源 ---
STATIC_DIR = os.path.join(EXEC_DIR, "static")
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")
BATCH_DIR = os.path.join(STATIC_DIR, "batch")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")

os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(BATCH_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- 初始化核心 ---
DATA_DIR = os.path.join(EXEC_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

img_gen = ImageGenerator()
batch_gen = BatchImageGenerator()
digital_human_gen = DigitalHumanGenerator()
db = DBManager(db_path=os.path.join(DATA_DIR, "app.db"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# --- 缩略图工具 ---
def create_thumbnail(image_path: str):
    try:
        if not os.path.exists(image_path): return None
        base, _ = os.path.splitext(image_path)
        thumb_path = f"{base}.thumb.jpg"
        if os.path.exists(thumb_path): return thumb_path
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
            img.thumbnail((400, 400))
            img.save(thumb_path, "JPEG", quality=70)
            return thumb_path
    except Exception as e:
        print(f"Error thumbnail: {e}")
        return None

def scan_and_sync_db():
    """后台任务：扫描文件夹，生成缩略图，同步DB"""
    print("🔄 Syncing files and database...")
    
    # 1. 扫描并生成缩略图
    extensions = ["*.png", "*.jpg", "*.jpeg"]
    files = glob.glob(os.path.join(GENERATED_DIR, "*.png"))
    for f in files:
        base, _ = os.path.splitext(f)
        thumb_path = f"{base}.thumb.jpg"
        if not os.path.exists(thumb_path):
            create_thumbnail(f)

    # 2. 恢复 Metadata 到 DB (从 JSON)
    json_files = glob.glob(os.path.join(GENERATED_DIR, "*.json"))
    restored_count = 0
    
    # 获取 DB 中已有的 filename，避免重复插入
    # 这里简单处理：db.log_image 不会检查重复，但 schema 有 UNIQUE 约束
    # 我们应该先查询。但在 db_manager 中没有批量查询。
    # 简单策略：遍历 JSON，如果 DB 里没有记录，就插入。
    # 为了效率，可以先获取所有 filenames。
    
    # 由于 db_manager 接口有限，我们在循环中用 try-except 捕获 UNIQUE constraint error 是一种简单方案
    # 或者扩展 db_manager，但这里直接用 SQL 操作
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        # 获取所有已存在的 filenames
        cursor.execute("SELECT filename FROM images")
        existing_filenames = set(row[0] for row in cursor.fetchall())
        
        for jf in json_files:
            try:
                # 文件名: abc.json -> abc.png
                base_name = os.path.splitext(os.path.basename(jf))[0]
                # 兼容旧命名 (可能 image 是 .png, json 是 .json)
                # 假设图片是 png
                image_filename = f"{base_name}.png"
                
                # 如果 DB 已存在，跳过
                if image_filename in existing_filenames:
                    continue
                
                # 读取 JSON
                with open(jf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 提取字段
                prompt = data.get("prompt", "")
                subject = data.get("subject", "general")
                grade = data.get("grade", "general")
                featured = data.get("featured", False)
                timestamp = data.get("timestamp", time.time())
                
                # Owner? 旧数据可能没有 owner，或者 owner 格式不同。
                # 设为 None (系统归属) 或 default admin? 
                # 既然是恢复，且之前没有用户系统，设为 NULL (user_id=None) 是合理的，
                # 这样它们不会出现在任何特定用户的 "我的图片" 中，但如果 featured=True 会出现在画廊。
                # 之前的逻辑：所有 LAN 用户都能看到。现在的逻辑：只能看自己的 + Featured。
                # 所以旧图片只有被 Featured 才能被看到。这符合 "之前的精选图片不见了" 的需求。
                
                # 插入 DB
                cursor.execute(
                    "INSERT INTO images (user_id, filename, prompt, subject, grade, timestamp, featured, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (None, image_filename, prompt, subject, grade, timestamp, featured, json.dumps(data))
                )
                restored_count += 1
                
            except Exception as e:
                # print(f"Skipping {jf}: {e}")
                pass
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"DB Sync Error: {e}")

    if restored_count > 0:
        print(f"✅ Restored {restored_count} images from metadata.")
    else:
        print("✅ Sync complete (No new metadata restored).")

# --- 辅助函数 ---
def sanitize_filename(text: str) -> str:
    clean_text = text.replace(" ", "_")
    clean_text = re.sub(r'[\\/:*?"<>|]', '', clean_text)
    return clean_text[:50]

# --- Auth Dependency ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_optional(token: Optional[str] = Header(None, alias="Authorization")):
    # For gallery (if we want to allow guests to see featured only without 401)
    if not token: return None
    try:
        if token.startswith("Bearer "): token = token.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username:
            return db.get_user_by_username(username)
    except:
        return None
    return None

# --- Models ---
class UserRegister(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class SingleGenRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"
    subject: str = "general"
    grade: str = "general"
    model: Optional[str] = None # Added model selection
    reference_image_url: Optional[str] = None
    reference_image_urls: List[str] = []

class ModifyGenRequest(BaseModel):
    prompt: str
    original_image_url: str

class OptimizePromptRequest(BaseModel):
    prompt: str
    subject: str = "general"
    model: Optional[str] = None

class ToggleFeatureRequest(BaseModel):
    filename: str
    featured: bool

class UserUpdateRequest(BaseModel):
    user_id: int
    is_pro: bool
    quota_limit: int

class BatchDownloadRequest(BaseModel):
    filenames: List[str]

class DigitalHumanRequest(BaseModel):
    image_url: str
    audio_url: str
    prompt: Optional[str] = None
    seed: int = -1
    resolution: int = 1080
    fast_mode: bool = False

# --- Auth Endpoints ---

@app.post("/api/auth/register")
async def register(user: UserRegister):
    if db.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    db.create_user(user.username, get_password_hash(user.password))
    return {"success": True}

@app.post("/api/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user['username']})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
async def read_users_me(current_user: Dict = Depends(get_current_user)):
    remaining = current_user['quota_limit'] - current_user['quota_used']
    return {
        "id": current_user['id'],
        "username": current_user['username'],
        "is_pro": bool(current_user['is_pro']),
        "quota_limit": current_user['quota_limit'],
        "quota_used": current_user['quota_used'],
        "quota_remaining": max(0, remaining)
    }

# --- Batch Download Endpoint ---

@app.post("/api/download/batch")
async def download_batch(req: BatchDownloadRequest):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in req.filenames:
            fpath = os.path.join(GENERATED_DIR, fname)
            if not os.path.exists(fpath):
                fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, fname)
    
    zip_buffer.seek(0)
    zip_filename = f"Batch_{int(time.time())}.zip"
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )

# --- Helpers ---

def determine_execution_mode(current_user: Optional[Dict], x_model_key: Optional[str], cost: int = 1):
    # Priority 1: User provided Key (BYOK)
    if x_model_key:
        return "user", x_model_key, None

    # Priority 2: System Quota (Pro/Standard User)
    if current_user:
        # Refetch to ensure fresh quota
        user = db.get_user_by_id(current_user['id'])
        if user['quota_used'] + cost <= user['quota_limit']:
            return "system", None, None 
        
        # Quota exceeded
        raise HTTPException(status_code=403, detail=f"Quota exceeded (Cost: {cost}, Remaining: {user['quota_limit'] - user['quota_used']}). Please provide Custom API Key.")

    raise HTTPException(status_code=401, detail="Login required or provide x-model-key.")

# ...

@app.post("/api/generate/single")
async def generate_single(
    req: SingleGenRequest, 
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url")
):
    try:
        # Determine Cost
        request_model = req.model if req.model else img_gen.model
        cost = 2 if "gemini" in request_model.lower() else 1
        
        mode, runtime_key, runtime_base_url = determine_execution_mode(current_user, x_model_key, cost=cost)
        if runtime_base_url is None and x_model_base_url:
            runtime_base_url = x_model_base_url

        timestamp = int(time.time())
        safe_prompt = sanitize_filename(req.prompt)
        filename = f"{safe_prompt}_{timestamp}.png"
        
        # Enhanced Prompt Logic
        enhanced_prompt = req.prompt
        context_prompts = []
        if req.subject and req.subject != "general": context_prompts.append(f"Subject: {req.subject}")
        if req.grade and req.grade != "general": context_prompts.append(f"Target Audience: {req.grade} students")
        if context_prompts: enhanced_prompt += " (" + ", ".join(context_prompts) + ")"
        
        # Run Generation
        original_config = img_gen.config.copy()
        img_gen.config["image"]["size"] = req.size
        img_gen.config["image"]["quality"] = req.quality
        img_gen.config["image"]["style"] = req.style
        
        # Use request model if provided, else keep default
        request_model = req.model if req.model else img_gen.model

        final_path = None
        
        # Handle References
        all_ref_urls = list(set([u for u in [req.reference_image_url] + req.reference_image_urls if u]))
        if all_ref_urls:
            ref_paths = []
            for ref_url in all_ref_urls:
                ref_filename = os.path.basename(ref_url)
                p = os.path.join(UPLOAD_DIR, ref_filename) if "uploads" in ref_url else os.path.join(GENERATED_DIR, ref_filename)
                if os.path.exists(p): ref_paths.append(p)
            
            if ref_paths:
                print(f"🖼️ Attempting generation with {len(ref_paths)} reference images...")
                image_url = img_gen.generate_modified_image(
                    enhanced_prompt, 
                    ref_paths,
                    base_url=runtime_base_url,
                    api_key=runtime_key,
                    model=request_model
                )
                if image_url:
                    print(f"✅ Reference generation returned URL: {image_url[:50]}...")
                    save_path = os.path.join(GENERATED_DIR, filename)
                    if img_gen.download_image(image_url, save_path):
                        final_path = save_path
                    else:
                        print("❌ Failed to download reference generated image.")
                else:
                    print("❌ Reference generation returned None (Model declined or failed).")
        
        if not final_path:
            if all_ref_urls and 'ref_paths' in locals() and ref_paths:
                 print("⚠️ Ref gen failed, falling back to Text-to-Image (Ref ignored).")
            
            final_path = img_gen.generate_and_download(
                enhanced_prompt,
                filename,
                folder=GENERATED_DIR,
                base_url=runtime_base_url,
                api_key=runtime_key,
                model=request_model
            )
        
        img_gen.config = original_config
        
        if final_path:
            create_thumbnail(final_path)
            
            # Record Usage if System (Only for logged in users)
            if mode == "system" and current_user:
                db.update_user_quota(current_user['id'], cost)

            # Log to DB
            meta = {
                "size": req.size,
                "quality": req.quality,
                "style": req.style,
                "enhanced_prompt": enhanced_prompt,
                "refs": all_ref_urls
            }
            db.log_image(
                user_id=current_user['id'] if current_user else None,
                filename=filename,
                prompt=req.prompt,
                subject=req.subject,
                grade=req.grade,
                metadata=meta
            )
            
            # Save JSON for backup/legacy compatibility
            json_meta = meta.copy()
            json_meta.update({
                "prompt": req.prompt,
                "subject": req.subject,
                "grade": req.grade,
                "timestamp": timestamp,
                "featured": False,
                "owner": current_user['username'] if current_user else "guest"
            })
            with open(os.path.join(GENERATED_DIR, f"{safe_prompt}_{timestamp}.json"), 'w', encoding='utf-8') as f:
                json.dump(json_meta, f, ensure_ascii=False, indent=2)

            # Return Updated Quota
            remaining = 0
            is_pro = False
            if current_user:
                updated_user = db.get_user_by_id(current_user['id'])
                remaining = updated_user['quota_limit'] - updated_user['quota_used']
                is_pro = bool(updated_user['is_pro'])
            
            return {
                "success": True,
                "url": f"/static/generated/{filename}",
                "remaining_quota": max(0, remaining),
                "is_pro": is_pro
            }
        else:
            raise HTTPException(status_code=500, detail="Generation failed")
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/modify")
async def generate_modify(
    req: ModifyGenRequest,
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url")
):
    try:
        # Determine Cost (Modify uses system default model)
        cost = 2 if "gemini" in img_gen.model.lower() else 1
        
        mode, runtime_key, runtime_base_url = determine_execution_mode(current_user, x_model_key, cost=cost)
        if runtime_base_url is None and x_model_base_url: runtime_base_url = x_model_base_url

        if not req.original_image_url.startswith("/static/generated/"):
            raise HTTPException(status_code=400, detail="Invalid image URL")
        
        filename = os.path.basename(req.original_image_url)
        original_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(original_path):
            raise HTTPException(status_code=404, detail="Original image not found")

        timestamp = int(time.time())
        safe_prompt = sanitize_filename(req.prompt)
        new_filename = f"modified_{safe_prompt}_{timestamp}.png"
        
        image_url = img_gen.generate_modified_image(
            req.prompt, [original_path], base_url=runtime_base_url, api_key=runtime_key
        )
        
        if image_url:
            save_path = os.path.join(GENERATED_DIR, new_filename)
            if img_gen.download_image(image_url, save_path):
                create_thumbnail(save_path)
                
                if mode == "system" and current_user:
                    db.update_user_quota(current_user['id'], cost)
                
                # Try to inherit metadata
                parent_meta = db.get_image_metadata(filename)
                subject = parent_meta['subject'] if parent_meta else 'general'
                grade = parent_meta['grade'] if parent_meta else 'general'

                db.log_image(
                    user_id=current_user['id'] if current_user else None,
                    filename=new_filename,
                    prompt=req.prompt,
                    subject=subject,
                    grade=grade,
                    metadata={"parent": filename, "type": "modification"}
                )

                remaining = 0
                if current_user:
                    updated_user = db.get_user_by_id(current_user['id'])
                    remaining = updated_user['quota_limit'] - updated_user['quota_used']

                return {
                    "success": True,
                    "url": f"/static/generated/{new_filename}",
                    "remaining_quota": max(0, remaining)
                }
        raise HTTPException(status_code=500, detail="Modification failed")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gallery")
async def get_gallery(current_user: Optional[Dict] = Depends(get_current_user_optional)):
    """
    Returns:
    1. Images owned by current_user
    2. Images marked as featured
    """
    user_id = current_user['id'] if current_user else None
    
    images = db.get_gallery_images(user_id=user_id)
    
    # Transform for frontend
    results = []
    for img in images:
        filename = img['filename']
        base, _ = os.path.splitext(filename)
        thumb_name = f"{base}.thumb.jpg"
        
        # Check files exist
        if not os.path.exists(os.path.join(GENERATED_DIR, filename)): continue
        
        thumb_path = os.path.join(GENERATED_DIR, thumb_name)
        thumb_url = f"/static/generated/{quote(thumb_name)}" if os.path.exists(thumb_path) else f"/static/generated/{quote(filename)}"
        
        results.append({
            "id": filename, # frontend uses filename/name as id key sometimes
            "name": filename,
            "url": f"/static/generated/{quote(filename)}",
            "thumbnail_url": thumb_url,
            "prompt": img['prompt'],
            "subject": img['subject'],
            "grade": img['grade'],
            "featured": bool(img['featured']),
            "time": img['timestamp'],
            "is_mine": (user_id is not None) and (img['user_id'] == user_id)
        })
    
    return results

class CropRequest(BaseModel):
    image_url: str
    crops: List[Dict[str, int]] # [{x, y, w, h}, ...]

@app.post("/api/tools/crop_and_zip")
async def crop_and_zip(req: CropRequest):
    try:
        # Extract filename from URL
        filename = unquote(os.path.basename(req.image_url))
        # Check generated and uploads
        file_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(file_path):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Image not found")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            with Image.open(file_path) as img:
                for i, crop in enumerate(req.crops):
                    # Validate coords
                    x, y, w, h = crop['x'], crop['y'], crop['w'], crop['h']
                    if w <= 0 or h <= 0: continue
                    
                    # Crop
                    cropped = img.crop((x, y, x+w, y+h))
                    
                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    # Keep original format or default to PNG
                    fmt = img.format or "PNG"
                    cropped.save(img_byte_arr, format=fmt)
                    
                    # Add to zip
                    zf.writestr(f"scene_{i+1}.{fmt.lower()}", img_byte_arr.getvalue())

        zip_buffer.seek(0)
        zip_filename = f"scenes_{int(time.time())}.zip"
        return StreamingResponse(
            iter([zip_buffer.getvalue()]), 
            media_type="application/zip", 
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tools/crop_to_urls")
async def crop_to_urls(req: CropRequest):
    try:
        # Extract filename from URL (handle encoding)
        filename = unquote(os.path.basename(req.image_url))
        # Search in generated or uploads
        file_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(file_path):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail=f"Image not found: {filename}")

        urls = []
        with Image.open(file_path) as img:
            for i, crop in enumerate(req.crops):
                x, y, w, h = crop['x'], crop['y'], crop['w'], crop['h']
                if w <= 0 or h <= 0: continue
                
                cropped = img.crop((x, y, x+w, y+h))
                
                # Save as new upload
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

@app.post("/api/admin/toggle_feature")
async def toggle_feature(req: ToggleFeatureRequest, current_user: Dict = Depends(get_current_user)):
    # Simple admin check (assuming admin is a specific user or flag, for now let's just use the global password approach or check user role)
    # The requirement didn't specify Admin Role in DB, so we'll stick to the token header for Admin operations or add 'is_admin' to DB.
    # But wait, existing admin uses a separate login endpoint returning a token in memory.
    # Let's keep the existing Admin Token logic for admin specific ops to minimize friction, OR upgrade user to Admin.
    # For now, let's use the DB approach: if user is logged in, check if they are "admin" (maybe username=admin?)
    if current_user['username'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    db.toggle_feature(req.filename, req.featured)
    return {"success": True, "featured": req.featured}

@app.get("/api/admin/users")
async def get_all_users(current_user: Dict = Depends(get_current_user)):
    if current_user['username'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    return db.get_all_users()

@app.post("/api/admin/update_user")
async def update_user(req: UserUpdateRequest, current_user: Dict = Depends(get_current_user)):
    if current_user['username'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    db.update_user_status(req.user_id, req.is_pro, req.quota_limit)
    return {"success": True}

@app.post("/api/optimize_prompt")
async def optimize_prompt_endpoint(
    req: OptimizePromptRequest,
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    x_model_key: Optional[str] = Header(None, alias="x-model-key")
):
    try:
        # Check Access: Either Logged In OR Guest with Key
        if not current_user and not x_model_key:
             raise HTTPException(status_code=403, detail="Login required or provide x-model-key header.")
        
        optimized = img_gen.optimize_prompt(req.prompt, subject=req.subject, model=req.model)
        return {"success": True, "optimized_prompt": optimized}
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
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/digital_human/submit")
async def submit_digital_human_task(
    req: DigitalHumanRequest,
    current_user: Optional[Dict] = Depends(get_current_user_optional)
):
    # Check quota or auth if needed...
    
    # URL Handling
    ext_base = os.getenv("EXTERNAL_BASE_URL", "").rstrip("/")
    img_url = req.image_url
    audio_url = req.audio_url
    
    if ext_base:
        if img_url.startswith("/"):
            img_url = f"{ext_base}{img_url}"
        if audio_url.startswith("/"):
            audio_url = f"{ext_base}{audio_url}"
    else:
        # Fallback: warn or try anyway. Volcengine requires public URL.
        # If running locally without EXTERNAL_BASE_URL, this will likely fail.
        pass

    result = digital_human_gen.submit_task(
        image_url=img_url,
        audio_url=audio_url,
        prompt=req.prompt,
        seed=req.seed,
        resolution=req.resolution,
        fast_mode=req.fast_mode
    )
    
    if "error" in result:
        # Check for specific error codes if needed
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result

@app.get("/api/digital_human/status/{task_id}")
async def get_digital_human_status(task_id: str):
    result = digital_human_gen.get_task_result(task_id)
    if "error" in result:
         raise HTTPException(status_code=500, detail=result["error"])
    return result

# --- Startup ---
@app.on_event("startup")
async def startup_event():
    print("🍌 ReOpenInnoLab-智绘工坊 Backend Started")
    # Scan thumbnails
    import threading
    threading.Thread(target=scan_and_sync_db, daemon=True).start()
    
    # Ensure default admin user exists
    if not db.get_user_by_username("admin"):
        db.create_user("admin", get_password_hash(ADMIN_PASSWORD), is_pro=True)
        print("👤 Default admin user created (password: admin888)")

# --- Frontend Static Serving ---
if getattr(sys, 'frozen', False):
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
