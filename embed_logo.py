import base64
import os

def embed_logo():
    logo_path = "logo.png"
    app_vue_path = "frontend/src/App.vue"
    
    if not os.path.exists(logo_path):
        print("Error: logo.png not found!")
        return

    # 1. 读取图片并转换为 Base64
    with open(logo_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        base64_src = f"data:image/png;base64,{encoded_string}"
    
    print(f"Logo encoded, length: {len(base64_src)}")

    # 2. 读取 App.vue
    with open(app_vue_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 3. 替换 src="/logo.png" 为 src="data:image/..."
    # 我们查找特定的字符串进行替换
    target_str = 'src="/logo.png"'
    if target_str in content:
        new_content = content.replace(target_str, f'src="{base64_src}"')
        
        with open(app_vue_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Success: App.vue updated with base64 logo!")
    else:
        print("Warning: Could not find 'src=\"/logo.png\"' in App.vue")

if __name__ == "__main__":
    embed_logo()
