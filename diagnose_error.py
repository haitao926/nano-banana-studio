import sys
import os
import traceback
import asyncio

# 设置环境
current_dir = os.getcwd()
backend_dir = os.path.join(current_dir, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.image_generator import ImageGenerator

async def diagnose():
    print("🚑 开始深度诊断后端生成功能...")
    print(f"📂 Backend Path: {backend_dir}")

    try:
        # 1. 初始化生成器
        print("\n[1] 初始化 ImageGenerator...")
        img_gen = ImageGenerator()
        
        # 打印配置信息 (隐藏 Key)
        api_config = img_gen.config.get('api', {})
        auth_config = img_gen.config.get('auth', {})
        key = auth_config.get('api_key', '')
        masked_key = key[:5] + "***" + key[-4:] if key else "None"
        
        print(f"    - API URL: {api_config.get('base_url')}")
        print(f"    - API Key: {masked_key}")
        
        if not key:
            print("    ❌ 错误: API Key 为空！请检查 backend/data/config.json")
            return

        # 2. 测试生成
        print("\n[2] 尝试调用 API 生成图片...")
        prompt = "A cute yellow banana, 3d render, minimal"
        
        # 模拟 main.py 的调用方式
        save_folder = os.path.join(backend_dir, "static", "generated")
        os.makedirs(save_folder, exist_ok=True)
        filename = "debug_test.png"
        
        print(f"    - 目标路径: {save_folder}")
        
        # 调用核心方法
        result = img_gen.generate_and_download(prompt, filename, save_folder)
        
        if result:
            print(f"\n✅ 成功！图片已保存至: {result}")
        else:
            print("\n❌ 失败: generate_and_download 返回 None")
            print("   请检查上方是否有 API 请求失败的日志")

    except Exception as e:
        print("\n💥 发生严重异常！")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose())
