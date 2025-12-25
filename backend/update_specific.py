import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")

files_to_update = [
    {"name": "image.json", "subject": "science", "prompt": "System Architecture Diagram"},
    {"name": "Projectile_Motion_Textbook_Diagram.json", "subject": "science", "prompt": "Physics Projectile Motion"},
    {"name": "Generated Image November 23, 2025 - 10_09AM.json", "subject": "science", "prompt": "Advanced Concept Illustration"}
]

for item in files_to_update:
    path = os.path.join(GENERATED_DIR, item["name"])
    
    # 读取现有内容或创建新的
    meta = {}
    if os.path.exists(path):
        with open(path, 'r') as f:
            meta = json.load(f)
    
    # 强制更新关键字段
    meta["subject"] = item["subject"]
    meta["featured"] = True
    meta["timestamp"] = time.time() # 更新时间戳让它排到最前面
    if "prompt" not in meta or meta["prompt"] == "image":
        meta["prompt"] = item["prompt"]

    with open(path, 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"✅ Updated {item['name']}")
