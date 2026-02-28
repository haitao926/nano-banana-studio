#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nano Banana (Gemini) 图片生成器
基于 OpenAI 兼容协议 (Requests)
"""

import json
import requests
import time
from typing import Any, Dict, List, Optional, Union
import os
import base64
import re
import io
from PIL import Image

from .env_utils import get_env_str, get_env_list

def _parse_model_key_map(raw: str) -> Dict[str, str]:
    if not raw:
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k).strip(): str(v).strip() for k, v in data.items() if str(k).strip() and str(v).strip()}
        except Exception:
            pass
    pairs = re.split(r"[,\n;]+", raw)
    mapping: Dict[str, str] = {}
    for pair in pairs:
        if not pair.strip() or "=" not in pair:
            continue
        model, key = pair.split("=", 1)
        model = model.strip()
        key = key.strip()
        if model and key:
            mapping[model] = key
    return mapping

class ImageGenerator:
    """基于 HTTP 请求的通用图片生成器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "..", "data", "config.json")
            
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self._apply_config(self.config)
        self.prompt_config = self._load_prompt_config()
        self.last_error: Optional[Dict[str, Any]] = None

    def _load_config(self, config_path: str) -> Dict:
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            return {}

    def _load_prompt_config(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prompt_templates.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load prompt templates: {e}")
        return {}

    def _apply_config(self, config: Dict):
        """将配置字典应用到实例属性"""
        if not isinstance(config, dict):
            config = {}
        self.config = config
        self.config.setdefault("api", {})
        self.config.setdefault("auth", {})
        api_cfg = self.config.get("api", {}) or {}
        auth_cfg = self.config.get("auth", {}) or {}
        # 确保 image 节点存在，避免下游 KeyError
        self.config.setdefault("image", {})

        env_base_url = get_env_str("IMAGE_BASE_URL")
        if env_base_url:
            api_cfg["base_url"] = env_base_url
            self.config["api"]["base_url"] = env_base_url

        env_api_key = get_env_str("IMAGE_API_KEY")
        if env_api_key:
            auth_cfg["api_key"] = env_api_key
            self.config["auth"]["api_key"] = env_api_key
        env_backup_keys = get_env_list("IMAGE_BACKUP_KEYS")
        if env_backup_keys is not None:
            auth_cfg["backup_keys"] = env_backup_keys
            self.config["auth"]["backup_keys"] = env_backup_keys

        # 加载配置（以 config 文件为主）
        env_image_model = get_env_str("IMAGE_MODEL")
        if env_image_model:
            api_cfg["model"] = env_image_model
            self.config["api"]["model"] = env_image_model
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

        model_key_map = model_rules.get("model_key_map", {}) if isinstance(model_rules, dict) else {}
        if not isinstance(model_key_map, dict):
            model_key_map = {}
        env_model_map = os.getenv("IMAGE_MODEL_KEY_MAP", "").strip()
        if env_model_map:
            model_key_map = _parse_model_key_map(env_model_map)
        self.model_key_map = {str(k).strip(): str(v).strip() for k, v in model_key_map.items() if str(k).strip() and str(v).strip()}
        
        self.model = api_cfg.get("model")
        self.llm_model = get_env_str("IMAGE_LLM_MODEL") or None
        
        self.timeout = api_cfg.get("timeout", 120)
        self.max_retries = api_cfg.get("max_retries", 3)
        image_cfg = self.config.get("image", {}) or {}
        fallback_models = image_cfg.get("fallback_models", [])
        if isinstance(fallback_models, str):
            fallback_models = [m.strip() for m in fallback_models.split(",") if m.strip()]
        self.fallback_models = [m for m in fallback_models if m]

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

    @staticmethod
    def _build_url(base_url: str, endpoint: str) -> str:
        base = (base_url or "").rstrip("/")
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        if endpoint.startswith("/v1/"):
            if base.endswith("/v1") or base.endswith("/api/v3"):
                endpoint = endpoint[len("/v1") :]
        return f"{base}{endpoint}"

    def _execute_multipart_request(
        self,
        url: str,
        headers: Dict,
        data: Dict,
        file_paths: list[str],
    ) -> Optional[requests.Response]:
        files = []
        handles = []
        try:
            for img_path in file_paths:
                if not os.path.exists(img_path):
                    continue
                mime_type = "image/png"
                if img_path.lower().endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                fh = open(img_path, "rb")
                handles.append(fh)
                files.append(("image[]", (os.path.basename(img_path), fh, mime_type)))

            response = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=self.timeout,
            )
            return response
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return None
        finally:
            for fh in handles:
                try:
                    fh.close()
                except Exception:
                    pass

    def _make_multipart_request(
        self,
        endpoint: str,
        data: Dict,
        file_paths: list[str],
        retry_count: int = 0,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
    ) -> Optional[Dict]:
        current_base_url = (base_url or self.base_url).rstrip("/")

        if model:
            data["model"] = model

        url = self._build_url(current_base_url, endpoint)

        keys_to_try = [api_key] if api_key else (self.api_keys if self.api_keys else [""])

        if not api_key and model and self.model_key_map:
            mapped_key = self.model_key_map.get(model)
            if mapped_key:
                print(f"🔑 使用模型专用Key: {model}")
                keys_to_try = [mapped_key]

        if not api_key and model and model in self.special_models and self.special_keys:
            print(f"🔑 使用专用Key池 (针对模型: {model})")
            keys_to_try = self.special_keys

        for key_idx, current_key in enumerate(keys_to_try):
            headers = {}
            if current_key:
                headers["Authorization"] = f"Bearer {current_key}"

            for attempt in range(self.max_retries + 1):
                response = self._execute_multipart_request(url, headers, data, file_paths)

                if response is None:
                    time.sleep(1)
                    continue

                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception:
                        return {"raw": response.text, "status_code": response.status_code}

                if response.status_code in [401, 403, 429, 402, 500, 503]:
                    print(f"⚠️ Key #{key_idx} failed with {response.status_code}. Trying next key...")
                    break

                if response.status_code in [502, 504]:
                    print(f"🔄 正在重试 ({attempt + 1}/{self.max_retries})...")
                    time.sleep(2)
                    continue

                print(f"❌ API请求失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return None

        print("❌ All keys failed.")
        return None

    @staticmethod
    def _is_openai_image_model(model: Optional[str]) -> bool:
        if not model:
            return False
        text = str(model).lower()
        return any(token in text for token in ("gpt-image", "dall-e", "dalle", "chatgpt-image"))

    @staticmethod
    def _is_seedream_model(model: Optional[str]) -> bool:
        if not model:
            return False
        return "seedream" in str(model).lower()

    @staticmethod
    def _supports_seedream_group(model: Optional[str]) -> bool:
        if not model:
            return False
        return "seedream-4" in str(model).lower()

    @staticmethod
    def _supports_seedream_multi_image(model: Optional[str]) -> bool:
        return ImageGenerator._supports_seedream_group(model)

    def _make_request(self, endpoint: str, data: Dict, retry_count: int = 0, base_url: str = None, api_key: str = None, model: str = None) -> Optional[Dict]:
        """发送API请求 (支持多Key轮询)"""
        current_base_url = (base_url or self.base_url).rstrip("/")
        
        # Override model in data if provided
        if model:
            data["model"] = model
            
        url = self._build_url(current_base_url, endpoint)
        
        # Determine keys to try
        # If explicit api_key provided (BYOK), use only that.
        # Otherwise, use system keys (primary + backups).
        keys_to_try = [api_key] if api_key else (self.api_keys if self.api_keys else [""])

        # Per-model key map override (System keys only)
        if not api_key and model and self.model_key_map:
            mapped_key = self.model_key_map.get(model)
            if mapped_key:
                print(f"🔑 使用模型专用Key: {model}")
                keys_to_try = [mapped_key]

        # Check for model-specific keys override (System keys only)
        if not api_key and model and model in self.special_models and self.special_keys:
             print(f"🔑 使用专用Key池 (针对模型: {model})")
             keys_to_try = self.special_keys
        
        last_error: Optional[Dict[str, Any]] = None
        self.last_error = None
        
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
                    message = None
                    try:
                        payload = response.json()
                        if isinstance(payload, dict):
                            if isinstance(payload.get("error"), dict):
                                message = payload["error"].get("message") or payload["error"].get("message_zh")
                            message = message or payload.get("message") or payload.get("msg")
                    except Exception:
                        payload = None
                    if not message:
                        message = response.text.strip() if response.text else None
                    last_error = {
                        "status_code": response.status_code,
                        "message": message or f"HTTP {response.status_code}",
                    }
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
            
        if last_error:
            self.last_error = last_error
        print("❌ All keys failed.")
        return {"error": last_error or {"message": "All keys failed"}, "status_code": (last_error or {}).get("status_code")}

    @staticmethod
    def _normalize_data_uri(value: str) -> str:
        if not value or not value.startswith("data:image"):
            return value
        if "," in value:
            header, encoded = value.split(",", 1)
            encoded = re.sub(r"\s+", "", encoded)
            return f"{header},{encoded}" if encoded else value
        match = re.match(r"^(data:image/[^;]+;base64)\s+(.+)$", value, re.DOTALL)
        if match:
            encoded = re.sub(r"\s+", "", match.group(2))
            return f"{match.group(1)},{encoded}" if encoded else value
        return value

    @classmethod
    def _extract_image_candidate(cls, payload: Any) -> Optional[str]:
        if payload is None:
            return None

        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                return None
            text = re.sub(r"^```[a-zA-Z0-9]*\n", "", text)
            text = re.sub(r"\n```$", "", text)

            if text.startswith("{") or text.startswith("["):
                try:
                    parsed = json.loads(text)
                    candidate = cls._extract_image_candidate(parsed)
                    if candidate:
                        return candidate
                except Exception:
                    pass

            data_match = re.search(
                r"(data:image/[a-zA-Z0-9.+-]+;base64)(?:,|\s+)([A-Za-z0-9+/=\s]+)",
                text,
                re.DOTALL,
            )
            if data_match:
                encoded = re.sub(r"\s+", "", data_match.group(2))
                if encoded:
                    return f"{data_match.group(1)},{encoded}"

            md_match = re.search(r'!\[.*?\]\((.*?)\)', text)
            if md_match:
                return cls._normalize_data_uri(md_match.group(1).rstrip(").,]"))

            url_match = re.search(r"(https?://[^\s)]+)", text)
            if url_match:
                return url_match.group(1).rstrip(").,]")

            if text.startswith(("http://", "https://", "data:image")):
                return cls._normalize_data_uri(text)
            return None

        if isinstance(payload, list):
            for item in payload:
                candidate = cls._extract_image_candidate(item)
                if candidate:
                    return candidate
            return None

        if isinstance(payload, dict):
            # Gemini style: candidates -> content -> parts -> inlineData/inline_data
            candidates = payload.get("candidates")
            if isinstance(candidates, list):
                for candidate in candidates:
                    found = cls._extract_image_candidate(candidate)
                    if found:
                        return found

            parts = payload.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    found = cls._extract_image_candidate(part)
                    if found:
                        return found

            inline_data = payload.get("inline_data") or payload.get("inlineData")
            if isinstance(inline_data, dict):
                data_val = inline_data.get("data")
                mime_type = inline_data.get("mime_type") or inline_data.get("mimeType") or "image/png"
                if isinstance(data_val, str) and data_val.strip():
                    return f"data:{mime_type};base64,{data_val.strip()}"

            if "data" in payload and ("mime_type" in payload or "mimeType" in payload):
                data_val = payload.get("data")
                mime_type = payload.get("mime_type") or payload.get("mimeType") or "image/png"
                if isinstance(data_val, str) and data_val.strip():
                    return f"data:{mime_type};base64,{data_val.strip()}"

            url_val = payload.get("url")
            if isinstance(url_val, str):
                return cls._normalize_data_uri(url_val)

            image_url_val = payload.get("image_url")
            if isinstance(image_url_val, str):
                return cls._normalize_data_uri(image_url_val)
            if isinstance(image_url_val, dict):
                candidate = cls._extract_image_candidate(image_url_val)
                if candidate:
                    return candidate

            b64_val = payload.get("b64_json")
            if isinstance(b64_val, str) and b64_val.strip():
                return f"data:image/png;base64,{b64_val.strip()}"

            for key in ("content", "message", "data", "choices", "images", "output"):
                if key in payload:
                    candidate = cls._extract_image_candidate(payload[key])
                    if candidate:
                        return candidate
            return None

        return None

    @classmethod
    def _extract_image_candidates(cls, payload: Any) -> List[str]:
        if payload is None:
            return []
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                candidates: List[str] = []
                for item in data:
                    candidate = cls._extract_image_candidate(item)
                    if candidate:
                        candidates.append(candidate)
                if candidates:
                    return candidates
        candidate = cls._extract_image_candidate(payload)
        return [candidate] if candidate else []

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

        system_instruction = (
            "You are an image generation model. "
            "You MUST return a single image only, either as a direct https URL or a data:image/*;base64 string. "
            "Do not include any extra text, markdown, or explanations."
        )

        def _build_user_prompt(strict: bool = False) -> str:
            suffix = (
                "Return only the image (URL or data:image/*;base64). No other text."
                if not strict else
                "IMPORTANT: Return ONLY a direct image URL or data:image/*;base64. No other text."
            )
            return f"Generate a single image based on the description below.\n{suffix}\n\nDescription: {final_prompt}"

        for attempt in range(2):
            data = {
                "model": model or self.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": _build_user_prompt(strict=attempt > 0)}
                ],
                "n": 1
            }
            
            response = self._make_request("/v1/chat/completions", data, base_url=base_url, api_key=api_key, model=model)
            
            if response:
                candidate = self._extract_image_candidate(response)
                if candidate:
                    return candidate
                print("⚠️ Gemini 返回内容非图片，准备重试更严格指令...")
        
        return None

    @staticmethod
    def _size_to_aspect_ratio(size: Optional[str]) -> Optional[str]:
        if not size or "x" not in size:
            return None
        size = size.lower().strip()
        mapping = {
            "1024x1024": "1:1",
            "1792x1024": "16:9",
            "1024x1792": "9:16",
            "1536x1024": "3:2",
            "1024x1536": "2:3",
            "1152x896": "5:4",
            "896x1152": "4:5",
        }
        return mapping.get(size)

    def _generate_image_via_gemini(self, prompt: str, size: str = None, base_url: str = None, api_key: str = None, model: str = None) -> Optional[str]:
        """通过 Gemini generateContent 生成图片 (适配 gemini-2.5-flash-image)"""
        try:
            target_model = model or self.model
            parts = [{"text": prompt}]
            generation_config: Dict[str, Any] = {"responseModalities": ["IMAGE"]}
            aspect_ratio = self._size_to_aspect_ratio(size)
            if aspect_ratio:
                generation_config["imageConfig"] = {"aspect_ratio": aspect_ratio}

            payload = {
                "contents": [{"parts": parts}],
                "generationConfig": generation_config
            }

            endpoint = f"/v1beta/models/{target_model}:generateContent"
            response = self._make_request(endpoint, payload, base_url=base_url, api_key=api_key, model=target_model)
            if response:
                return self._extract_image_candidate(response)
            return None
        except Exception as e:
            print(f"❌ Gemini 图片生成失败: {e}")
            return None

    def optimize_prompt(self, raw_prompt: str, subject: str = "general", model: str = None, api_key: str = None, base_url: str = None) -> Optional[str]:
        """
        使用 LLM 优化提示词 (融入结构化思维)
        :param model: 目标绘图模型 (Target Image Model)，用于定制提示词风格。
                      实际推理仍然使用 self.model (System LLM)。
        """
        # 1. 确定 LLM 和 目标风格
        llm_model = model or self.llm_model or self.model
        target_model = model or self.model
        if not llm_model:
            print("⚠️ 缺少 LLM 模型配置，无法优化提示词")
            return None
        
        # Load config or use defaults
        p_conf = self.prompt_config or {}
        subject_constraints = p_conf.get("subject_constraints", {})
        
        # 2. 定义学科特定的负面约束
        neg_constraint = subject_constraints.get(subject, p_conf.get("default_neg_constraint", "no distorted text"))

        # 3. 定制化风格指令 (根据目标模型)
        style_instruction = ""
        lang_instruction = p_conf.get("default_language_instruction", "Write a descriptive paragraph in English.")
        
        model_styles = p_conf.get("model_styles", {})
        if target_model:
            t_lower = target_model.lower()
            # Find matching model style
            for key, conf in model_styles.items():
                if key in t_lower:
                    style_instruction = conf.get("style", "")
                    if "language_instruction" in conf:
                        lang_instruction = conf["language_instruction"]
                    break

        # Subject Language Override
        overrides = p_conf.get("subject_language_overrides", {})
        if subject in overrides:
            lang_instruction = overrides[subject]

        # 4. 高级 System Prompt
        templates = p_conf.get("templates", {})
        
                # 针对“教材绘图”的特殊处理
                if subject == "textbook":
                    style_keywords = p_conf.get("textbook_style_keywords", "modern 2.5D vector illustration, white background")
                    template = templates.get("textbook", "")
        
                    system_instruction = template.format(
                        neg_constraint=neg_constraint,
                        style_instruction=style_instruction,
                        lang_instruction=lang_instruction
                    )
                    user_content = f"Create a textbook illustration prompt for: {raw_prompt}. Style requirements: {style_keywords}. Subject context: {subject}"
                elif subject == "sketchnote":
                    system_instruction = templates.get("sketchnote", "")
                    user_content = f"用户提供的内容：\n{raw_prompt}\n\n请严格按照System Prompt的规则，生成对应的绘画指令。不要解释，直接输出最终的 Prompt。"
                else:
                    template = templates.get("general", "")            
            system_instruction = template.format(
                neg_constraint=neg_constraint,
                style_instruction=style_instruction,
                lang_instruction=lang_instruction
            )
            user_content = f"Create an educational infographic prompt for: {raw_prompt}. Subject context: {subject}"
        
        # Fallback if template is missing
        if not system_instruction:
            system_instruction = "You are a prompt expert. Rewrite the user prompt."

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
        response = self._make_request("/v1/chat/completions", data, base_url=base_url, api_key=api_key, model=llm_model)
        
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"].strip()

            # Strip fenced code blocks
            content = re.sub(r"^```[a-zA-Z0-9]*\n", "", content).strip()
            content = re.sub(r"\n```$", "", content).strip()

            # If JSON with a prompt field, extract it
            if content.startswith("{") and content.endswith("}"):
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and isinstance(data.get("prompt"), str):
                        content = data["prompt"].strip()
                except Exception:
                    pass
            
            # 移除 markdown 图片链接
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\[Image\]', '', content, flags=re.IGNORECASE)
            content = content.strip()
            
            if not content or len(content) < 5:
                print("⚠️ 优化结果无效")
                return None

            print(f"✨ 优化完成: {content[:50]}...")
            return content
        
        return None

    def generate_seedream_images(
        self,
        prompt: str,
        size: str = None,
        image_url: Optional[Union[str, List[str]]] = None,
        max_images: int = 4,
        group_mode: bool = False,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
    ) -> List[str]:
        target_model = model or self.model
        data: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "response_format": "url",
            "stream": False,
            "watermark": False,
        }
        if size:
            data["size"] = size
        if image_url:
            if isinstance(image_url, (list, tuple)):
                images = [u for u in image_url if u]
                if images:
                    if not self._supports_seedream_multi_image(target_model):
                        data["image"] = images[0]
                    else:
                        data["image"] = images
            else:
                data["image"] = image_url
        if group_mode and self._supports_seedream_group(target_model):
            data["sequential_image_generation"] = "auto"
            data["sequential_image_generation_options"] = {"max_images": max_images}
        response = self._make_request(
            "/v1/images/generations",
            data,
            base_url=base_url,
            api_key=api_key,
            model=target_model,
        )
        return self._extract_image_candidates(response)

    def generate_modified_image(self, prompt: str, base_image_paths: list[str], base_url: str = None, api_key: str = None, model: str = None) -> Optional[str]:
        """
        基于原图(多图)进行修改 (Image-to-Image / Vision)
        """
        if not base_image_paths:
            return None

        target_model = model or self.model
        if self._is_seedream_model(target_model):
            first_path = base_image_paths[0]
            try:
                mime_type = "image/png"
                if first_path.lower().endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                with open(first_path, "rb") as image_file:
                    b64_data = base64.b64encode(image_file.read()).decode("utf-8")
                image_url = f"data:{mime_type};base64,{b64_data}"
                seedream_images = self.generate_seedream_images(
                    prompt,
                    image_url=image_url,
                    base_url=base_url,
                    api_key=api_key,
                    model=target_model,
                )
                return seedream_images[0] if seedream_images else None
            except Exception:
                return None
        is_gemini = "gemini" in target_model.lower()
        is_openai_image = self._is_openai_image_model(target_model)

        # Construct a strong instruction for Image Editing (Shared by both strategies)
        edit_instruction = (
            f"Using the provided image as a STRICT reference, apply this modification: {prompt}. "
            "You MUST maintain the original composition, subject, layout, and style. "
            "Do NOT generate a new random image. Modify the existing image."
        )

        try:
            # -------------------------------------------------
            # 1. GEMINI NATIVE STRATEGY (:generateContent)
            # -------------------------------------------------
            if is_gemini:
                # User Example suggests Text FIRST, then Image
                parts = [{"text": edit_instruction}]
                
                for img_path in base_image_paths:
                    if not os.path.exists(img_path): continue
                    
                    mime_type = "image/png"
                    if img_path.lower().endswith((".jpg", ".jpeg")):
                        mime_type = "image/jpeg"
                    
                    with open(img_path, "rb") as image_file:
                        b64_data = base64.b64encode(image_file.read()).decode('utf-8')
                    
                    parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    })
                
                payload = {
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "responseModalities": ["IMAGE"]
                    }
                }
                
                endpoint = f"/v1beta/models/{target_model}:generateContent"
                
                print(f"🎨 Gemini 原生重绘: {prompt}")
                response = self._make_request(endpoint, payload, base_url=base_url, api_key=api_key, model=target_model)
                
                if response:
                    return self._extract_image_candidate(response)
                return None

            # -------------------------------------------------
            # 2. OPENAI IMAGE EDITS (gpt-image / dall-e)
            # -------------------------------------------------
            if is_openai_image:
                print(f"🎨 OpenAI Images/Edits ({len(base_image_paths)} refs): {prompt}")
                data = {
                    "prompt": edit_instruction,
                    "n": 1
                }
                response = self._make_multipart_request(
                    "/v1/images/edits",
                    data,
                    base_image_paths,
                    base_url=base_url,
                    api_key=api_key,
                    model=target_model,
                )
                if response:
                    candidate = self._extract_image_candidate(response)
                    if candidate:
                        return candidate
                return None

            # -------------------------------------------------
            # 3. OPENAI COMPATIBLE STRATEGY (Chat Vision)
            # -------------------------------------------------
            content_list = [
                {
                    "type": "text",
                    "text": edit_instruction
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

            print(f"🎨 OpenAI 兼容重绘 ({len(base_image_paths)} refs): {prompt}")

            data = {
                "model": target_model,
                "messages": [
                    {
                        "role": "user",
                        "content": content_list
                    }
                ],
                "n": 1
            }

            response = self._make_request("/v1/chat/completions", data, base_url=base_url, api_key=api_key, model=target_model)

            if response:
                candidate = self._extract_image_candidate(response)
                if candidate:
                    return candidate
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

        if self._is_seedream_model(target_model):
            seedream_images = self.generate_seedream_images(
                prompt,
                size=size,
                image_url=None,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
            )
            return seedream_images[0] if seedream_images else None

        # 针对 Gemini-3-pro-image-preview 模型的特殊处理
        if "gemini-3-pro-image-preview" in target_model:
            print(f"🤖 检测到 Gemini 绘图模型，切换到 Chat 接口...")
            return self._generate_image_via_chat(prompt, size, quality, base_url=base_url, api_key=api_key, model=target_model)
        # Gemini 2.5 Flash Image: 使用 generateContent
        if "gemini-2.5-flash-image" in target_model:
            print(f"🤖 检测到 Gemini 2.5 Flash Image，切换到 generateContent 接口...")
            return self._generate_image_via_gemini(prompt, size=size, base_url=base_url, api_key=api_key, model=target_model)

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

    @staticmethod
    def _is_valid_image_bytes(data: bytes) -> bool:
        if not data:
            return False
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
            return True
        except Exception:
            return False

    def download_image(self, image_url: str, save_path: str) -> bool:
        """下载图片到本地 (支持 URL 和 Base64 Data URI)"""
        try:
            print(f"📥 准备保存图片到: {save_path}")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 处理 Base64 Data URI
            if image_url.startswith("data:image"):
                image_url = self._normalize_data_uri(image_url)
                if "," not in image_url:
                    print("❌ Base64数据缺少逗号分隔，无法解析")
                    return False
                try:
                    # 格式: data:image/png;base64,.....
                    header, encoded = image_url.split(",", 1)
                    data = base64.b64decode(encoded)
                    if not self._is_valid_image_bytes(data):
                        print("❌ Base64内容不是有效图片，已终止保存")
                        return False
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
                content_type = (response.headers.get("Content-Type") or "").lower()
                if content_type and not content_type.startswith("image/"):
                    print(f"❌ 响应类型不是图片: {content_type}")
                    return False
                if not self._is_valid_image_bytes(response.content):
                    print("❌ 下载内容不是有效图片，已终止保存")
                    return False
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
        target_model = model or self.model
        models_to_try = [target_model]
        if target_model and "gemini" in target_model.lower() and self.fallback_models:
            models_to_try.extend([m for m in self.fallback_models if m != target_model])

        save_path = os.path.join(folder, filename)

        for idx, model_name in enumerate(models_to_try):
            if idx > 0:
                print(f"🔁 切换备用模型: {model_name}")

            for attempt in range(self.max_retries + 1):
                image_url = self.generate_image(prompt, base_url=base_url, api_key=api_key, model=model_name)
                if not image_url:
                    continue
                if self.download_image(image_url, save_path):
                    return save_path
                print(f"⚠️ 图片内容无效，重试生成 ({attempt + 1}/{self.max_retries})...")
        
        return None

# 单例辅助函数
def get_image_generator() -> ImageGenerator:
    return ImageGenerator()
