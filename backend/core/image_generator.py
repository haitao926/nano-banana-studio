#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nano Banana (Gemini) 图片生成器
基于 OpenAI 兼容协议 (Requests)
"""

import json
import requests
import time
from typing import Dict, Optional
import os
import base64
import re

class ImageGenerator:
    """基于 HTTP 请求的通用图片生成器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "..", "data", "config.json")
            
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self._apply_config(self.config)

    def _load_config(self, config_path: str) -> Dict:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            return {}

    def _apply_config(self, config: Dict):
        """将配置字典应用到实例属性"""
        if not isinstance(config, dict):
            config = {}
        self.config = config
        api_cfg = self.config.get("api", {}) or {}
        auth_cfg = self.config.get("auth", {}) or {}
        # 确保 image 节点存在，避免下游 KeyError
        self.config.setdefault("image", {})

        # 加载配置（以 config 文件为主）
        self.base_url = api_cfg.get("base_url", "").rstrip("/")
        self.api_key = auth_cfg.get("api_key", "")
        self.model = api_cfg.get("model")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = api_cfg.get("timeout", 120)
        self.max_retries = api_cfg.get("max_retries", 3)

    def save_config(self):
        """持久化当前配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"配置文件保存失败: {e}")
            return False

    def reload_config(self):
        """从磁盘重新加载配置"""
        self.config = self._load_config(self.config_path)
        self._apply_config(self.config)

    def update_config(self, base_url: Optional[str] = None, model: Optional[str] = None, api_key: Optional[str] = None):
        """更新并保存配置"""
        if not isinstance(self.config, dict):
            self.config = {}
        self.config.setdefault("api", {})
        self.config.setdefault("auth", {})
        self.config.setdefault("image", {})

        if base_url is not None:
            self.config["api"]["base_url"] = base_url.rstrip("/")
        if model is not None:
            self.config["api"]["model"] = model
        if api_key is not None:
            self.config["auth"]["api_key"] = api_key

        self._apply_config(self.config)
        self.save_config()

    def _make_request(self, endpoint: str, data: Dict, retry_count: int = 0) -> Optional[Dict]:
        """发送API请求"""
        url = f"{self.base_url}{endpoint}"

        try:
            print(f"🚀 发送请求到: {url}")
            print(f"   模型: {data.get('model')}")
            
            response = requests.post(
                url,
                headers=self.headers,
                json=data,
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ API请求失败: {response.status_code}")
                print(f"   响应: {response.text}")
                
                # 可重试的状态码
                if response.status_code in [500, 502, 503, 504] and retry_count < self.max_retries:
                    print(f"🔄 正在重试 ({retry_count + 1}/{self.max_retries})...")
                    time.sleep(2)
                    return self._make_request(endpoint, data, retry_count + 1)
                return None

        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return None

    def _generate_image_via_chat(self, prompt: str, size: str = None, quality: str = None) -> Optional[str]:
        """通过 Chat API 生成图片 (针对 Gemini 等模型)"""
        
        # 针对 Gemini 的 Prompt 增强: 注入画幅比例指令
        final_prompt = prompt
        
        # 1. 画幅处理
        if size:
            if size == "1792x1024":
                final_prompt += " --ar 16:9"
            elif size == "1024x1792":
                final_prompt += " --ar 9:16"
            elif size == "1024x1024":
                final_prompt += " --ar 1:1"
        
        # 2. 画质/分辨率处理 (通过提示词增强)
        # 虽然物理分辨率受限，但通过指令可以显著提升细节密度
        if quality:
            if quality.lower() in ["2k", "high"]:
                final_prompt += ", (highly detailed, 2k resolution, sharp focus)"
            elif quality.lower() in ["4k", "ultra"]:
                final_prompt += ", (ultra detailed, 4k resolution, 8k, masterpiece, best quality, extreme detail, hyperrealistic)"

        print(f"🎨 Chat生成提示词: {final_prompt}")

        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": final_prompt}
            ],
            "n": 1
        }
        
        response = self._make_request("/v1/chat/completions", data)
        
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            # 尝试提取 markdown 图片链接或直接返回内容
            # 格式通常是 ![image](url) 或 ![image](data:image/...)
            match = re.search(r'!\[.*?\]\((.*?)\)', content)
            if match:
                return match.group(1)
            return content # 如果没找到markdown格式，直接返回内容尝试
        return None

    def optimize_prompt(self, raw_prompt: str) -> str:
        """
        使用 LLM 优化提示词
        """
        system_instruction = (
            "You are an expert prompt engineer for AI image generation. "
            "Your task is to expand the user's simple input into a detailed, high-quality prompt "
            "suitable for advanced AI art models (like Midjourney, Gemini, Stable Diffusion). "
            "Focus on: Lighting, Texture, Composition, Style, and Atmosphere. "
            "Output ONLY the optimized prompt, no explanations."
        )
        
        data = {
            "model": self.model, # Use the same model for text
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Optimize this prompt: {raw_prompt}"}
            ],
            "temperature": 0.7
        }
        
        print(f"✨ 正在优化提示词: {raw_prompt}")
        response = self._make_request("/v1/chat/completions", data)
        
        if response and "choices" in response and len(response["choices"]) > 0:
            optimized = response["choices"][0]["message"]["content"].strip()
            print(f"✨ 优化完成: {optimized[:50]}...")
            return optimized
        
        return raw_prompt

    def generate_modified_image(self, prompt: str, base_image_paths: list[str]) -> Optional[str]:
        """
        基于原图(多图)进行修改 (Image-to-Image / Vision)
        """
        if not base_image_paths:
            return None

        try:
            content_list = [
                {
                    "type": "text",
                    "text": f"{prompt} (Return the modified image URL only)"
                }
            ]

            for img_path in base_image_paths:
                if not os.path.exists(img_path):
                    print(f"⚠️ 跳过不存在的图片: {img_path}")
                    continue
                    
                # 确定MIME类型
                mime_type = "image/png"
                if img_path.lower().endswith(".jpg") or img_path.lower().endswith(".jpeg"):
                    mime_type = "image/jpeg"
                
                # 读取并编码
                with open(img_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
                content_list.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded_string}"
                    }
                })

            print(f"🎨 正在修改图片 ({len(base_image_paths)} refs), 提示词: {prompt}")

            # 2. 构建多模态请求 (OpenAI Vision 格式)
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": content_list
                    }
                ],
                "n": 1
            }

            response = self._make_request("/v1/chat/completions", data)

            if response and "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]
                # 尝试提取 markdown 图片链接
                match = re.search(r'!\[.*?\]\((.*?)\)', content)
                if match:
                    return match.group(1)
                # 假如直接返回了URL文本
                if content.startswith("http"):
                    return content
                return content
            return None

        except Exception as e:
            print(f"❌ 图片修改失败: {e}")
            return None

    def generate_image(self, prompt: str, size: str = None, quality: str = None, style: str = None) -> Optional[str]:
        """
        生成图片
        Returns: 图片 URL 或 Base64 Data URI
        """
        # 使用默认参数
        if size is None: size = self.config["image"].get("size")
        if quality is None: quality = self.config["image"].get("quality")
        if style is None: style = self.config["image"].get("style")
        
        # 针对 Gemini-3-pro-image-preview 模型的特殊处理
        if "gemini-3-pro-image-preview" in self.model:
            print(f"🤖 检测到 Gemini 绘图模型，切换到 Chat 接口...")
            return self._generate_image_via_chat(prompt, size, quality)

        # 构建请求数据 (OpenAI 兼容格式)
        data = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": size
        }

        # 大多数中转商使用标准的 OpenAI 图片接口
        response = self._make_request("/v1/images/generations", data)

        if response and "data" in response and len(response["data"]) > 0:
            image_url = response["data"][0]["url"]
            print(f"✅ 图片生成成功URL: {image_url[:50]}...")
            return image_url
        else:
            print("❌ 未获取到图片数据")
            return None

    def download_image(self, image_url: str, save_path: str) -> bool:
        """下载图片到本地 (支持 URL 和 Base64 Data URI)"""
        try:
            print(f"📥 准备保存图片到: {save_path}")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 处理 Base64 Data URI
            if image_url.startswith("data:image"):
                try:
                    # 格式: data:image/png;base64,.....
                    header, encoded = image_url.split(",", 1)
                    data = base64.b64decode(encoded)
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    print(f"✅ Base64图片解码并保存成功")
                    return True
                except Exception as e:
                    print(f"❌ Base64解码失败: {e}")
                    return False

            # 处理普通 URL
            # 有些 URL 需要代理，有些不需要，这里直接请求
            response = requests.get(image_url, timeout=60)

            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ 下载成功")
                return True
            else:
                print(f"❌ 下载失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 下载异常: {e}")
            return False

    def generate_and_download(self, prompt: str, filename: str, folder: str = "generated_images") -> Optional[str]:
        """生成并下载"""
        image_url = self.generate_image(prompt)
        
        if image_url:
            save_path = os.path.join(folder, filename)
            if self.download_image(image_url, save_path):
                return save_path
        return None

# 单例辅助函数
def get_image_generator() -> ImageGenerator:
    return ImageGenerator()
