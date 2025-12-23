import sys
import os
import traceback

print("🔍 开始诊断后端环境...")

# 添加 backend 到路径，模拟 main.py 的环境
current_dir = os.getcwd()
backend_dir = os.path.join(current_dir, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

print(f"📂 当前工作目录: {current_dir}")
print(f"📂 Backend 目录: {backend_dir}")

try:
    print("\n1️⃣ 尝试导入 ImageGenerator...")
    from core.image_generator import ImageGenerator
    print("   ✅ 导入成功")
    
    print("\n2️⃣ 尝试初始化 ImageGenerator...")
    img_gen = ImageGenerator()
    print(f"   ✅ 初始化成功，API Key: {img_gen.config['auth']['api_key'][:5]}***")

    print("\n3️⃣ 尝试导入 BatchImageGenerator...")
    from core.batch_image_generator import BatchImageGenerator
    print("   ✅ 导入成功")

    print("\n4️⃣ 尝试初始化 BatchImageGenerator...")
    batch_gen = BatchImageGenerator()
    print(f"   ✅ 初始化成功，加载了 {len(batch_gen.system_prompts)} 个系统提示词")
    
    print("\n🎉 核心逻辑似乎没有问题！")
    print("问题可能出在 FastAPI 的路径挂载上。")

except Exception as e:
    print("\n❌ 发现错误！")
    print("=" * 40)
    traceback.print_exc()
    print("=" * 40)
