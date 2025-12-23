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

class ImageGenerator:
    """基于 HTTP 请求的通用图片生成器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "..", "data", "config.json")
            
        self.config_path = config_path
        self.config = self._load_config(config_path)
        
        # 加载配置
        self.base_url = self.config["api"]["base_url"].rstrip('/')
        self.api_key = self.config["auth"]["api_key"]
        self.model = self.config["api"]["model"]
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = self.config["api"]["timeout"]
        self.max_retries = self.config["api"]["max_retries"]

    def _load_config(self, config_path: str) -> Dict:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            return {}

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

    def generate_image(self, prompt: str, size: str = None, quality: str = None, style: str = None) -> Optional[str]:
        """
        生成图片
        Returns: 图片 URL
        """
        # 使用默认参数
        if size is None: size = self.config["image"]["size"]
        
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
        """下载图片到本地"""
        try:
            print(f"📥 下载图片到: {save_path}")
            # 有些 URL 需要代理，有些不需要，这里直接请求
            response = requests.get(image_url, timeout=60)

            if response.status_code == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
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