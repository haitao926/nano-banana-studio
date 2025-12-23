from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import glob
import sys

# 确保能导入 core 模块
# 获取当前文件 (main.py) 所在目录 (backend/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.image_generator import ImageGenerator
from core.batch_image_generator import BatchImageGenerator

app = FastAPI(title="Nano Banana API")

# --- CORS 设置 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 路径配置 (使用绝对路径) ---
# 定义 static 目录的绝对路径: backend/static
STATIC_DIR = os.path.join(BASE_DIR, "static")
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")
BATCH_DIR = os.path.join(STATIC_DIR, "batch")

# 确保目录存在
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(BATCH_DIR, exist_ok=True)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- 初始化核心类 ---
img_gen = ImageGenerator()
batch_gen = BatchImageGenerator()

# --- 数据模型 ---
class SingleGenRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"

class BatchGenRequest(BaseModel):
    system_keys: List[str]
    requirement_indices: List[int]

# --- API 接口 ---

@app.get("/api/status")
async def get_status():
    return {"status": "running", "service": "Nano Banana AI", "static_dir": STATIC_DIR}

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

@app.post("/api/generate/single")
async def generate_single(req: SingleGenRequest):
    """单图生成"""
    try:
        import time
        filename = f"single_{int(time.time())}.png"
        
        # 临时修改配置
        original_config = img_gen.config.copy()
        img_gen.config["image"]["size"] = req.size
        img_gen.config["image"]["quality"] = req.quality
        img_gen.config["image"]["style"] = req.style
        
        # 传入绝对路径给生成器
        save_path = os.path.join(GENERATED_DIR, filename)
        
        # 调用生成
        # generate_and_download 内部用的是 requests.get 下载
        # 我们这里直接传完整路径
        final_path = img_gen.generate_and_download(
            req.prompt,
            filename,
            folder=GENERATED_DIR 
        )
        
        # 恢复配置
        img_gen.config = original_config
        
        if final_path:
            # 返回 URL (前端访问用)
            return {"success": True, "url": f"/static/generated/{filename}"}
        else:
            raise HTTPException(status_code=500, detail="Generation failed")
            
    except Exception as e:
        print(f"Error generating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gallery")
async def get_gallery():
    """获取图库列表"""
    try:
        files = []
        
        # 扫描 batch (使用绝对路径)
        batch_pattern = os.path.join(BATCH_DIR, "*.png")
        for f in glob.glob(batch_pattern):
            files.append({
                "url": f"/static/batch/{os.path.basename(f)}",
                "name": os.path.basename(f),
                "type": "batch",
                "time": os.path.getmtime(f)
            })
            
        # 扫描 single
        single_pattern = os.path.join(GENERATED_DIR, "*.png")
        for f in glob.glob(single_pattern):
            files.append({
                "url": f"/static/generated/{os.path.basename(f)}",
                "name": os.path.basename(f),
                "type": "single",
                "time": os.path.getmtime(f)
            })
        
        # 按时间倒序
        files.sort(key=lambda x: x["time"], reverse=True)
        return files
    except Exception as e:
        print(f"Error loading gallery: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)