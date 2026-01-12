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
        
        # Load keys
        primary_key = auth_cfg.get("api_key", "")
        # Load backup keys (from config or env)
        # Env var BACKUP_KEYS takes precedence? Or config?
        # Let's support config 'backup_keys' which is a list or string
        backup_keys_conf = auth_cfg.get("backup_keys", [])
        if isinstance(backup_keys_conf, str):
            backup_keys_conf = [k.strip() for k in backup_keys_conf.split(",") if k.strip()]
        
        self.api_keys = [k for k in [primary_key] + backup_keys_conf if k]
        self.api_key = self.api_keys[0] if self.api_keys else ""
        
        # Load model-specific keys
        model_rules = auth_cfg.get("model_rules", {})
        self.special_models = model_rules.get("special_models", [])
        self.special_keys = model_rules.get("special_keys", [])
        if isinstance(self.special_keys, str):
             self.special_keys = [k.strip() for k in self.special_keys.split(",") if k.strip()]
        
        self.model = api_cfg.get("model")
        
        self.timeout = api_cfg.get("timeout", 120)
        self.max_retries = api_cfg.get("max_retries", 3)

    def _execute_raw_request(self, url: str, headers: Dict, data: Dict, retry_count: int = 0) -> Optional[requests.Response]:
        """执行单次请求，处理网络层面的重试"""
        try:
            print(f"🚀 发送请求到: {url}")
            print(f"   模型: {data.get('model')}")
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            return response
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return None

    def _make_request(self, endpoint: str, data: Dict, retry_count: int = 0, base_url: str = None, api_key: str = None, model: str = None) -> Optional[Dict]:
        """发送API请求 (支持多Key轮询)"""
        current_base_url = (base_url or self.base_url).rstrip("/")
        
        # Override model in data if provided
        if model:
            data["model"] = model
            
        url = f"{current_base_url}{endpoint}"
        
        # Determine keys to try
        # If explicit api_key provided (BYOK), use only that.
        # Otherwise, use system keys (primary + backups).
        keys_to_try = [api_key] if api_key else (self.api_keys if self.api_keys else [""])

        # Check for model-specific keys override (System keys only)
        if not api_key and model and model in self.special_models and self.special_keys:
             print(f"🔑 使用专用Key池 (针对模型: {model})")
             keys_to_try = self.special_keys
        
        last_error = None
        
        for key_idx, current_key in enumerate(keys_to_try):
            headers = {
                "Authorization": f"Bearer {current_key}",
                "Content-Type": "application/json"
            }
            
            # Internal Retry Loop for a specific key (for 502/Timeout etc, not 401/403)
            # Actually, _execute_raw_request handles the call. We handle logical retries here?
            # Let's keep simple: Try Key -> If 401/429/500 -> Try Next Key.
            # If 502/504 -> Retry same key a few times?
            
            # Let's combine: Loop over Keys. Inside, retry connection errors?
            # Simplified: Just try each key once. If network fails, maybe retry same key?
            
            # We will use a simple retry for network flakes on the *same* key
            for attempt in range(self.max_retries + 1):
                response = self._execute_raw_request(url, headers, data)
                
                if response is None:
                    # Network error, retry same key
                    time.sleep(1)
                    continue
                
                if response.status_code == 200:
                    return response.json()
                
                # If error is recoverable by switching keys (401 Auth, 429 Rate, 402 Payment, 500/503 Provider Error)
                if response.status_code in [401, 403, 429, 402, 500, 503]:
                    print(f"⚠️ Key #{key_idx} failed with {response.status_code}. Trying next key...")
                    # Break inner loop (retries) to go to next key
                    break 
                
                # If error is likely transient (502, 504), retry same key
                if response.status_code in [502, 504]:
                     print(f"🔄 正在重试 ({attempt + 1}/{self.max_retries})...")
                     time.sleep(2)
                     continue
                
                # Other errors (400 Bad Request) -> Don't switch keys, likely request issue
                print(f"❌ API请求失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return None
            
            # If we broke out of inner loop, it means this key failed. Continue to next key.
            
        print("❌ All keys failed.")
        return None

    def _generate_image_via_chat(self, prompt: str, size: str = None, quality: str = None, base_url: str = None, api_key: str = None, model: str = None) -> Optional[str]:
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
            "model": model or self.model,
            "messages": [
                {"role": "user", "content": final_prompt}
            ],
            "n": 1
        }
        
        response = self._make_request("/v1/chat/completions", data, base_url=base_url, api_key=api_key, model=model)
        
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            # 尝试提取 markdown 图片链接或直接返回内容
            # 格式通常是 ![image](url) 或 ![image](data:image/...)
            match = re.search(r'!\[.*?\]\((.*?)\)', content)
            if match:
                return match.group(1)
            return content # 如果没找到markdown格式，直接返回内容尝试
        return None

    def optimize_prompt(self, raw_prompt: str, subject: str = "general", model: str = None) -> str:
        """
        使用 LLM 优化提示词 (融入结构化思维)
        :param model: 目标绘图模型 (Target Image Model)，用于定制提示词风格。
                      实际推理仍然使用 self.model (System LLM)。
        """
        # 1. 确定 LLM 和 目标风格
        llm_model = self.model # 始终使用系统配置的 LLM (Brain) 进行思考
        target_model = model or self.model # 用户选择的绘图模型
        
        # 2. 定义学科特定的负面约束
        subject_constraints = {
            "math": "no distorted numbers, no curved rulers, no incorrect formulas",
            "science": "no pseudo-science, no incorrect anatomy, no impossible physics",
            "physics": "no impossible physics, correct diagrams",
            "chemistry": "no incorrect molecules, realistic equipment",
            "biology": "correct anatomy, realistic plants/animals",
            "english": "no gibberish text, no asian characters, spelling must be correct",
            "chinese": "calligraphy style, correct characters",
            "history": "no anachronisms, period-accurate clothing only",
            "it_ai": "no blurry screens, no nonsensical code, futuristic but logical",
            "arts_pe": "aesthetic, dynamic composition, correct musical instruments, realistic sports action",
            "humanities_psych": "accurate maps, historical accuracy, biological details, empathy, facial expressions, social scenes",
            "textbook": "no blurry details, no photographic noise, no dark background, no complex background"
        }
        
        neg_constraint = subject_constraints.get(subject, "no distorted text, no blurry details")

        # 3. 定制化风格指令 (根据目标模型)
        style_instruction = ""
        if target_model:
            t_lower = target_model.lower()
            if "jimeng" in t_lower:
                style_instruction = "Target Model: Jimeng/Dream. Style preference: High artistic quality, dreamy lighting, Chinese aesthetic friendly, precise tags."
            elif "gpt" in t_lower or "dall" in t_lower:
                style_instruction = "Target Model: DALL-E 3. Style preference: Natural language descriptions, very literal interpretation, detailed visual adjectives."
            elif "gemini" in t_lower:
                style_instruction = "Target Model: Gemini Image. Style preference: Structured, logical, high dynamic range, prompt adherence."

        # 4. 高级 System Prompt
        
        # 针对“教材绘图”的特殊处理
        if subject == "textbook":
            style_keywords = "modern 2.5D vector illustration, soft gradient shading, clean lines, high-quality educational textbook art, vibrant multi-color accents, white background"
            
            system_instruction = f"""
You are a Prompt Engineering Expert. Your task is to WRITE A TEXT DESCRIPTION.
DO NOT GENERATE AN IMAGE.

Goal: Rewrite the user's input into a detailed visual description suitable for an image generator.
Constraint: {neg_constraint}.
Background: Must be White.
{style_instruction}

Process:
1. Analyze the core concept.
2. Write a descriptive paragraph in English.
3. Integrate the style requirements naturally.

Output ONLY the text description.
"""
            user_content = f"Create a textbook illustration prompt for: {raw_prompt}. Style requirements: {style_keywords}. Subject context: {subject}"
        else:
            system_instruction = f"""
You are a Prompt Engineering Expert. Your task is to WRITE A TEXT DESCRIPTION.
DO NOT GENERATE AN IMAGE.

Goal: Rewrite the user's input into a structured prompt.
Constraint: {neg_constraint}.
{style_instruction}

Output ONLY the text description.
"""
            user_content = f"Create an educational infographic prompt for: {raw_prompt}. Subject context: {subject}"
        
        # 注意: 这里使用 llm_model (self.model) 发起请求，而不是传入的 model (可能只是 image model)
        data = {
            "model": llm_model, 
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.7
        }
        
        print(f"✨ 正在优化提示词 (Target: {target_model}): {raw_prompt}")
        response = self._make_request("/v1/chat/completions", data, model=llm_model)
        
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"].strip()
            
            # 移除 markdown 图片链接
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\[Image\]', '', content, flags=re.IGNORECASE)
            content = content.strip()
            
            if not content or len(content) < 5:
                print("⚠️ 优化结果无效，回退")
                return raw_prompt

            print(f"✨ 优化完成: {content[:50]}...")
            return content
        
        return raw_prompt

    def generate_modified_image(self, prompt: str, base_image_paths: list[str], base_url: str = None, api_key: str = None, model: str = None) -> Optional[str]:
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
                "model": model or self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": content_list
                    }
                ],
                "n": 1
            }

            response = self._make_request("/v1/chat/completions", data, base_url=base_url, api_key=api_key, model=model)

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

    def generate_image(self, prompt: str, size: str = None, quality: str = None, style: str = None, base_url: str = None, api_key: str = None, model: str = None) -> Optional[str]:
        """
        生成图片
        Returns: 图片 URL 或 Base64 Data URI
        """
        # 使用默认参数
        if size is None: size = self.config["image"].get("size")
        if quality is None: quality = self.config["image"].get("quality")
        if style is None: style = self.config["image"].get("style")
        
        target_model = model or self.model

        # 针对 Gemini-3-pro-image-preview 模型的特殊处理
        if "gemini-3-pro-image-preview" in target_model:
            print(f"🤖 检测到 Gemini 绘图模型，切换到 Chat 接口...")
            return self._generate_image_via_chat(prompt, size, quality, base_url=base_url, api_key=api_key, model=target_model)

        # 构建请求数据 (OpenAI 兼容格式)
        data = {
            "model": target_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "url"
        }

        # 针对 z-image-turbo 的特殊参数
        if target_model == "z-image-turbo":
            data.update({
                "watermark": False,
                "prompt_extend": True
            })

        # 大多数中转商使用标准的 OpenAI 图片接口
        response = self._make_request("/v1/images/generations", data, base_url=base_url, api_key=api_key, model=target_model)

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

    def generate_and_download(self, prompt: str, filename: str, folder: str = "generated_images", base_url: str = None, api_key: str = None, model: str = None) -> Optional[str]:
        """生成并下载"""
        image_url = self.generate_image(prompt, base_url=base_url, api_key=api_key, model=model)
        
        if image_url:
            save_path = os.path.join(folder, filename)
            if self.download_image(image_url, save_path):
                return save_path
        return None

# 单例辅助函数
def get_image_generator() -> ImageGenerator:
    return ImageGenerator()
