import glob
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")

def test_scan():
    print(f"Scanning: {GENERATED_DIR}")
    extensions = ["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"]
    all_images = []
    for ext in extensions:
        pattern = os.path.join(GENERATED_DIR, ext)
        found = glob.glob(pattern)
        print(f"Pattern {ext}: found {len(found)} files")
        all_images.extend(found)
    
    unique_images = list(set(all_images))
    print(f"Total unique images: {len(unique_images)}")
    
    # 检查特定文件
    target = "Generated Image November 23, 2025 - 10_09AM.jpeg"
    found_target = False
    for path in unique_images:
        if target in path:
            print(f"✅ Found target: {path}")
            found_target = True
            break
    
    if not found_target:
        print(f"❌ Target NOT found: {target}")

if __name__ == "__main__":
    test_scan()
