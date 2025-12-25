import json
import os
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")

KEYWORDS = ["robot", "drone", "marl", "transformer", "blueprint", "schematic"]

def migrate():
    json_files = glob.glob(os.path.join(GENERATED_DIR, "*.json"))
    count = 0
    for path in json_files:
        with open(path, 'r') as f:
            try:
                meta = json.load(f)
            except:
                continue
        
        # 检查是否包含关键词
        filename = os.path.basename(path).lower()
        matched = False
        for kw in KEYWORDS:
            if kw in filename:
                matched = True
                break
        
        if matched:
            meta["subject"] = "it_ai"
            with open(path, 'w') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            print(f"✅ Migrated {os.path.basename(path)} to IT & AI")
            count += 1
            
    print(f"Done. Migrated {count} files.")

if __name__ == "__main__":
    migrate()
