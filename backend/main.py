from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import glob
import sys
import json
import secrets
import shutil
from urllib.parse import quote

# 确保能导入 core 模块
# 获取当前文件 (main.py) 所在目录 (backend/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.image_generator import ImageGenerator
from core.batch_image_generator import BatchImageGenerator
from core.rate_limiter import RateLimiter

app = FastAPI(title="ReOpenInnoLab API")

# --- 路径配置 (适配 PyInstaller 打包) ---
if getattr(sys, 'frozen', False):
    # PyInstaller 打包模式
    # BUNDLE_DIR: 临时解压目录 (放代码、前端网页、内置资源) -> 只读
    BUNDLE_DIR = sys._MEIPASS
    # EXEC_DIR: exe 所在目录 (放生成的图片、数据库) -> 可读写
    EXEC_DIR = os.path.dirname(sys.executable)
else:
    # 开发模式
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXEC_DIR = BUNDLE_DIR

# 确保能导入 core 模块 (从 BUNDLE_DIR 找代码)
if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)

# 动态配置: 优先读取 exe 同级目录的 config，如果没有则读取内置的
# 这里 core 模块已经在上面导入了

from core.image_generator import ImageGenerator
from core.batch_image_generator import BatchImageGenerator
from core.rate_limiter import RateLimiter

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

# --- 静态资源路径 (使用 EXEC_DIR 以便持久化) ---
# 定义 static 目录: 放在 exe 同级目录下，确保用户数据不丢失
STATIC_DIR = os.path.join(EXEC_DIR, "static")
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")
BATCH_DIR = os.path.join(STATIC_DIR, "batch")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")

# 确保目录存在
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(BATCH_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- 初始化核心类 ---
# 确保 data 目录存在
DATA_DIR = os.path.join(EXEC_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

img_gen = ImageGenerator()
batch_gen = BatchImageGenerator()
# 显式指定 DB 路径，防止写入临时目录
rate_limiter = RateLimiter(db_path=os.path.join(DATA_DIR, "rate_limit.db"))

@app.on_event("startup")
async def startup_event():
    """服务启动后的提示信息"""
    print("\n" + "="*50)
    print("🍌 ReOpenInnoLab-教学绘画 is READY!")
    print("👉 Open in Browser: http://localhost:6060")
    print("="*50 + "\n")

# --- 数据模型 ---
class SingleGenRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"
    subject: str = "general"
    grade: str = "general"
    reference_image_url: Optional[str] = None # Deprecated, keep for compat
    reference_image_urls: List[str] = []      # New standard

class BatchGenRequest(BaseModel):
    system_keys: List[str]
    requirement_indices: List[int]

class ModifyGenRequest(BaseModel):
    prompt: str
    original_image_url: str

class OptimizePromptRequest(BaseModel):
    prompt: str

class AdminLoginRequest(BaseModel):
    password: str

class FeatureRequest(BaseModel):
    filename: str
    featured: bool

# --- API 接口 ---

@app.get("/api/status")
async def get_status():
    return {"status": "running", "service": "Nano Banana AI", "static_dir": STATIC_DIR}

@app.get("/api/quota")
async def get_quota(request: Request):
    """获取当前IP的剩余额度"""
    client_ip = request.client.host
    remaining = rate_limiter.get_remaining_quota(client_ip)
    return {"ip": client_ip, "remaining": remaining, "max": 20}

# --- 管理员接口 ---

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "SKD-NB-ADMIN")
admin_tokens = set()

@app.post("/api/admin/login")
async def admin_login(req: AdminLoginRequest):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = secrets.token_urlsafe(32)
    admin_tokens.add(token)
    return {"success": True, "token": token}

def _check_admin(token: Optional[str]) -> bool:
    return token in admin_tokens

@app.get("/api/admin/stats")
async def admin_stats(x_admin_token: Optional[str] = Header(None)):
    if not _check_admin(x_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # 1. IP 统计
    ip_stats = rate_limiter.get_all_stats()
    
    # 2. 学科和年级统计 (扫描 metadata)
    subject_counts = {}
    grade_counts = {}
    
    single_pattern = os.path.join(GENERATED_DIR, "*.json")
    for json_path in glob.glob(single_pattern):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                sub = meta.get("subject", "general")
                grd = meta.get("grade", "general")
                subject_counts[sub] = subject_counts.get(sub, 0) + 1
                grade_counts[grd] = grade_counts.get(grd, 0) + 1
        except: pass
        
    return {
        "ip_stats": ip_stats,
        "subject_counts": subject_counts,
        "grade_counts": grade_counts
    }

@app.post("/api/admin/toggle_feature")
async def toggle_feature(req: FeatureRequest, x_admin_token: Optional[str] = Header(None)):
    if not _check_admin(x_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    json_filename = req.filename.replace(".png", ".json")
    json_path = os.path.join(GENERATED_DIR, json_filename)
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            meta["featured"] = req.featured
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
            return {"success": True, "featured": req.featured}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # 如果没有 JSON，创建一个
        meta = {"featured": req.featured}
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return {"success": True, "featured": req.featured}

@app.post("/api/optimize_prompt")
async def optimize_prompt_endpoint(req: OptimizePromptRequest):
    """优化提示词"""
    try:
        optimized = img_gen.optimize_prompt(req.prompt)
        return {"success": True, "optimized_prompt": optimized}
    except Exception as e:
        print(f"Error optimizing prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config():
    """获取当前的配置（Prompts）"""
    try:
        batch_gen.load_config() # 刷新配置
        return {
            "system_prompts": batch_gen.system_prompts,
            "requirement_prompts": batch_gen.requirement_prompts
        }
    except Exception as e:
        print(f"Error loading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/modify")
async def generate_modify(req: ModifyGenRequest, request: Request):
    """基于原图修改"""
    try:
        # 1. 速率限制检查
        client_ip = request.client.host
        allowed, message = rate_limiter.check_limit(client_ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=message)

        # 2. 解析原图路径
        # URL 格式 /static/generated/filename.png
        if not req.original_image_url.startswith("/static/generated/"):
            raise HTTPException(status_code=400, detail="Invalid image URL")
        
        filename = os.path.basename(req.original_image_url)
        original_path = os.path.join(GENERATED_DIR, filename)
        
        if not os.path.exists(original_path):
            raise HTTPException(status_code=404, detail="Original image not found")

        # 3. 生成新文件名
        import time
        timestamp = int(time.time())
        new_filename = f"modified_{timestamp}.png"
        new_meta_filename = f"modified_{timestamp}.json"
        
        # 4. 调用修改生成
        # 临时借用 generate_and_download 里的 download 逻辑，但这里我们直接调 img_gen.generate_modified_image
        # 然后手动下载
        
        # generate_modified_image 现在接受 list
        image_url = img_gen.generate_modified_image(req.prompt, [original_path])
        
        if image_url:
            save_path = os.path.join(GENERATED_DIR, new_filename)
            if img_gen.download_image(image_url, save_path):
                # 记录使用
                rate_limiter.record_usage(client_ip)
                remaining = rate_limiter.get_remaining_quota(client_ip)
                
                # 保存元数据
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

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error modifying image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件接口"""
    try:
        # 生成安全的文件名
        import time
        file_ext = os.path.splitext(file.filename)[1]
        if not file_ext: file_ext = ".png"
        filename = f"upload_{int(time.time())}_{secrets.token_hex(4)}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"success": True, "url": f"/static/uploads/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/api/generate/single")
async def generate_single(req: SingleGenRequest, request: Request):
    """单图生成 (支持参考图)"""
    try:
        # 1. 速率限制检查
        client_ip = request.client.host
        allowed, message = rate_limiter.check_limit(client_ip)
        
        if not allowed:
            print(f"⛔️ Rate limit denied for {client_ip}: {message}")
            raise HTTPException(status_code=429, detail=message)

        import time
        timestamp = int(time.time())
        filename = f"single_{timestamp}.png"
        meta_filename = f"single_{timestamp}.json"
        
        # --- 智能提示词增强 ---
        # 根据学科和年级，自动调整提示词，让生成结果更贴合场景
        enhanced_prompt = req.prompt
        context_prompts = []
        
        if req.subject and req.subject != "general":
            context_prompts.append(f"Subject: {req.subject}")
        
        if req.grade and req.grade != "general":
            if "primary" in req.grade.lower() or "kindergarten" in req.grade.lower():
                context_prompts.append(f"Target Audience: {req.grade} students (cute, friendly, easy to understand)")
            else:
                context_prompts.append(f"Target Audience: {req.grade} students")
        
        if context_prompts:
             enhanced_prompt += " (" + ", ".join(context_prompts) + ")"
        
        # --- 智能文字语言适配 ---
        # 如果学科是英语，自然应该显示英文；否则默认显示中文
        is_english_subject = req.subject and ("english" in req.subject.lower() or "英语" in req.subject.lower())
        
        if is_english_subject:
             enhanced_prompt += ", (text in image must be in English, text must be clear and legible, high quality typography)"
        else:
             enhanced_prompt += ", (text in image must be in Chinese, text must be clear and legible, high quality typography)"
        
        print(f"🧠 Enhanced Prompt: {enhanced_prompt}")

        # 临时修改配置
        original_config = img_gen.config.copy()
        img_gen.config["image"]["size"] = req.size
        if "image" not in img_gen.config: img_gen.config["image"] = {}
        img_gen.config["image"]["quality"] = req.quality
        img_gen.config["image"]["style"] = req.style
        
        final_path = None
        
        # ⚠️ 核心分支：是否有参考图
        # 统一收集所有参考图 URL
        all_ref_urls = []
        if req.reference_image_url:
            all_ref_urls.append(req.reference_image_url)
        if req.reference_image_urls:
            all_ref_urls.extend(req.reference_image_urls)
            
        # 去重
        all_ref_urls = list(set(all_ref_urls))
        
        if all_ref_urls:
            print(f"🖼️ 使用参考图 ({len(all_ref_urls)}): {all_ref_urls}")
            
            ref_paths = []
            for ref_url in all_ref_urls:
                # 解析本地路径
                ref_filename = os.path.basename(ref_url)
                if "uploads" in ref_url:
                    p = os.path.join(UPLOAD_DIR, ref_filename)
                else:
                    p = os.path.join(GENERATED_DIR, ref_filename)
                
                if os.path.exists(p):
                    ref_paths.append(p)
            
            if ref_paths:
                # 使用 modify 的逻辑（传入路径列表）
                image_url = img_gen.generate_modified_image(enhanced_prompt, ref_paths)
                if image_url:
                    save_path = os.path.join(GENERATED_DIR, filename)
                    if img_gen.download_image(image_url, save_path):
                        final_path = save_path
            else:
                print(f"⚠️ 所有参考图路径都不存在，降级为纯文本生成")
                
        
        # 如果没有参考图，或者参考图生成失败但没抛异常（逻辑降级），则执行纯文本生成
        if not final_path:
             final_path = img_gen.generate_and_download(
                enhanced_prompt,
                filename,
                folder=GENERATED_DIR 
            )
        
        # 恢复配置
        img_gen.config = original_config
        
        if final_path:
            # 2. 成功生成后记录使用
            rate_limiter.record_usage(client_ip)
            
            # 3. 保存元数据 (Metadata)
            meta_data = {
                "prompt": req.prompt, 
                "enhanced_prompt": enhanced_prompt,
                "subject": req.subject,
                "grade": req.grade,
                "size": req.size,
                "quality": req.quality,
                "style": req.style,
                "reference_images": all_ref_urls, # 记录所有参考图
                "timestamp": timestamp,
                "ip": client_ip,
                "featured": False 
            }
            try:
                with open(os.path.join(GENERATED_DIR, meta_filename), 'w', encoding='utf-8') as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Failed to save metadata: {e}")

            remaining = rate_limiter.get_remaining_quota(client_ip)
            print(f"✅ Generated for {client_ip}. Remaining quota: {remaining}")
            
            # 返回 URL
            return {
                "success": True, 
                "url": f"/static/generated/{filename}",
                "remaining_quota": remaining
            }
        else:
            raise HTTPException(status_code=500, detail="Generation failed")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error generating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gallery")
async def get_gallery():
    """获取图库列表"""
    try:
        files = []
        import json
        
        # 扫描所有图片格式
        # 增加大写支持，防止漏网
        extensions = ["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"]
        all_images = []
        for ext in extensions:
            all_images.extend(glob.glob(os.path.join(GENERATED_DIR, ext)))
            
        # 去重（不同后缀可能匹配到同一文件？不，glob是精确匹配）
        # 但为了保险转成 set 再转回
        all_images = list(set(all_images))

        for f in all_images:
            # 尝试寻找对应的 json 元数据
            # 兼容 .png.json 或 .json 替换
            basename = os.path.basename(f)
            name_without_ext = os.path.splitext(basename)[0]
            
            # 优先找同名json
            json_path = os.path.join(GENERATED_DIR, f"{name_without_ext}.json")
            
            meta = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as jf:
                        meta = json.load(jf)
                except: pass
            
            # 关键修复：URL 编码处理文件名中的空格和特殊字符
            encoded_name = quote(basename)
            
            files.append({
                "url": f"/static/generated/{encoded_name}",
                "name": basename,
                "type": "single",
                "time": os.path.getmtime(f),
                "subject": meta.get("subject", "general"),
                "grade": meta.get("grade", "general"),
                "prompt": meta.get("prompt", name_without_ext), # 没prompt就用文件名
                "featured": meta.get("featured", False)
            })
        
        # 按时间倒序
        files.sort(key=lambda x: x["time"], reverse=True)
        return files
    except Exception as e:
        print(f"Error loading gallery: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 前端托管配置 (生产环境模式) ---
# 这部分必须放在所有 API 路由之后
if getattr(sys, 'frozen', False):
    # 打包模式: 前端资源被打入 exe 内部的 dist 目录
    FRONTEND_DIST_DIR = os.path.join(BUNDLE_DIR, "dist")
else:
    # 开发模式
    FRONTEND_DIST_DIR = os.path.join(BUNDLE_DIR, "..", "frontend", "dist")

FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")

if os.path.exists(FRONTEND_DIST_DIR):
    print(f"📦 Found frontend build at {FRONTEND_DIST_DIR}, enabling static serving...")
    
    # 1. 挂载 assets 目录 (CSS/JS/Images)
    if os.path.exists(FRONTEND_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="assets")

    # 2. 挂载根路径和其他前端路由
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # 排除已知的 API 前缀
        if full_path.startswith("api/") or full_path.startswith("static/"):
            raise HTTPException(status_code=404)
        
        # 1. 尝试直接从 dist 根目录服务静态文件 (如 logo.png, favicon.ico)
        file_path = os.path.join(FRONTEND_DIST_DIR, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # 2. 否则返回 index.html (SPA 路由)
        index_path = os.path.join(FRONTEND_DIST_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
            
        return {"error": "Frontend build not found"}
else:
    print("⚠️ Frontend dist not found. Run 'npm run build' in frontend/ first.")
