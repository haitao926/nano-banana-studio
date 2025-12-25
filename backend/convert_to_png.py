import os
import subprocess
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")

def convert_to_png():
    # 查找所有 jpg/jpeg
    extensions = ["*.jpg", "*.jpeg", "*.JPG", "*.JPEG"]
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(GENERATED_DIR, ext)))
    
    files = list(set(files)) # 去重
    
    if not files:
        print("✅ No JPG/JPEG files found to convert.")
        return

    print(f"🔄 Found {len(files)} images to convert...")

    for jpg_path in files:
        # 构建新的 png 路径
        base_name = os.path.splitext(jpg_path)[0]
        png_path = f"{base_name}.png"
        
        # 使用 macOS 自带的 sips 工具转换 (System Image Processing Service)
        # sips -s format png source.jpg --out dest.png
        try:
            cmd = ["sips", "-s", "format", "png", jpg_path, "--out", png_path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            
            print(f"✅ Converted: {os.path.basename(jpg_path)} -> PNG")
            
            # 删除原文件
            os.remove(jpg_path)
        except Exception as e:
            print(f"❌ Failed to convert {os.path.basename(jpg_path)}: {e}")

if __name__ == "__main__":
    convert_to_png()
