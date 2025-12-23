import os
import shutil

# 定义目录结构
dirs = ["backend", "backend/core", "backend/static", "backend/data"]

# 核心文件映射 (源文件 -> 目标目录)
moves = {
    "image_generator.py": "backend/core/",
    "batch_image_generator.py": "backend/core/",
    "config.json": "backend/data/",
    "batch_config.json": "backend/data/",
}

def setup_backend():
    print("正在初始化后端架构...")
    
    # 1. 创建目录
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"Created: {d}")

    # 2. 移动核心文件
    for src, dest_folder in moves.items():
        if os.path.exists(src):
            shutil.move(src, os.path.join(dest_folder, src))
            print(f"Moved: {src} -> {dest_folder}")
        else:
            print(f"Skipped (Not Found): {src}")
            
    # 3. 创建空的 __init__.py 以便导入
    open("backend/__init__.py", "w").close()
    open("backend/core/__init__.py", "w").close()
    
    print("后端结构初始化完成。")

if __name__ == "__main__":
    setup_backend()
