import os
import glob
import json

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")

# 关键词映射规则
RULES = {
    "it_ai": ["robot", "drone", "marl", "transformer", "blueprint", "schematic", "tech", "ai", "data", "cyber", "code", "programming", "network"],
    "science": ["heat", "dynamics", "physics", "infographic", "biology", "chemistry", "experiment", "lab"],
    "history": ["权力的游戏", "红楼梦", "history", "ancient", "war", "empire", "dynasty", "china", "chinese"],
    "art": ["watercolor", "oil", "painting", "sketch", "drawing", "art", "style"],
    "math": ["math", "geometry", "algebra", "equation", "graph"],
    "english": ["translate", "english"]
}

def infer_subject(filename):
    lower_name = filename.lower()
    for subject, keywords in RULES.items():
        for kw in keywords:
            if kw in lower_name:
                return subject
    return "general"

def fix_metadata():
    print(f"📂 Scanning directory: {GENERATED_DIR}")
    
    extensions = ["*.png", "*.jpg", "*.jpeg"]
    images = []
    for ext in extensions:
        images.extend(glob.glob(os.path.join(GENERATED_DIR, ext)))
    
    count = 0
    for img_path in images:
        basename = os.path.basename(img_path)
        name_without_ext = os.path.splitext(basename)[0]
        json_path = os.path.join(GENERATED_DIR, f"{name_without_ext}.json")
        
        # 检查逻辑：如果不存在，或者存在但 subject 是 general，则尝试更新
        should_update = False
        meta = {}
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                current_subject = meta.get("subject", "general")
                # 如果当前是 general，尝试推断更具体的
                if current_subject == "general":
                    inferred = infer_subject(name_without_ext)
                    if inferred != "general":
                        meta["subject"] = inferred
                        should_update = True
                        print(f"🔄 Updating subject for: {basename} -> [{inferred}]")
            except:
                should_update = True # 读取失败，重新创建
        else:
            should_update = True
            
        if should_update:
            if not meta: # 如果是全新的
                subject = infer_subject(name_without_ext)
                meta = {
                    "prompt": name_without_ext.replace("_", " ").replace("-", " "),
                    "subject": subject,
                    "grade": "general",
                    "quality": "standard",
                    "style": "vivid",
                    "timestamp": os.path.getmtime(img_path),
                    "featured": True
                }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            
            if not os.path.exists(json_path): # 只有新创建才计数
                 print(f"✅ Generated metadata for: {basename}")
            count += 1

    print(f"✨ Process complete. Updated/Created {count} metadata files.")

if __name__ == "__main__":
    fix_metadata()
