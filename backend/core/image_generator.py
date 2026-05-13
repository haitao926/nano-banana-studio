#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nano Banana (Gemini) 图片生成器
基于 OpenAI 兼容协议 (Requests)
"""

import json
import builtins
import hashlib
import requests
import time
from typing import Any, Dict, List, Optional, Union
import os
import base64
import re
import io
from PIL import Image, ImageDraw, ImageFont

from .env_utils import get_env_str, get_env_list


def _safe_print(*args: Any, **kwargs: Any) -> None:
    """Best-effort logging that never fails request handling."""
    try:
        builtins.print(*args, **kwargs)
    except BrokenPipeError:
        return
    except ValueError:
        return
    except OSError as exc:
        if getattr(exc, "errno", None) in {5, 32}:
            return
        raise


# Route all module-local prints through a safe logger so detached/invalid
# stdout streams cannot turn normal request logging into a 500 response.
print = _safe_print
PROVIDER_CONNECT_TIMEOUT_SECONDS = float(os.getenv("NBS_PROVIDER_CONNECT_TIMEOUT_SECONDS", "8"))


def _font_candidates() -> List[str]:
    return [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]

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
        self.last_request_diagnostics: Optional[Dict[str, Any]] = None

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

    def _remember_error(self, message: str, status_code: Optional[int] = None) -> None:
        text = str(message or "").strip()
        if not text:
            return
        payload: Dict[str, Any] = {"message": text}
        if status_code is not None:
            payload["status_code"] = status_code
        self.last_error = payload

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

    @staticmethod
    def _request_timeout_value(request_timeout: Optional[int]) -> Union[int, float, tuple[float, float]]:
        read_timeout = float(request_timeout) if request_timeout is not None else float(120)
        read_timeout = max(1.0, read_timeout)
        connect_timeout = max(1.0, min(PROVIDER_CONNECT_TIMEOUT_SECONDS, read_timeout))
        return (connect_timeout, read_timeout)

    def _execute_raw_request(
        self,
        url: str,
        headers: Dict,
        data: Dict,
        retry_count: int = 0,
        request_timeout: Optional[int] = None,
    ) -> Optional[requests.Response]:
        """执行单次请求，处理网络层面的重试"""
        try:
            print(f"🚀 发送请求到: {url}")
            print(f"   模型: {data.get('model')}")
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=self._request_timeout_value(request_timeout or self.timeout),
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
        if base.endswith("/compatible-mode/v1") and endpoint.startswith("/v1/"):
            endpoint = endpoint[len("/v1") :]
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
        request_timeout: Optional[int] = None,
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
                timeout=self._request_timeout_value(request_timeout or self.timeout),
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
        request_timeout: Optional[int] = None,
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

        max_attempts = 1 if request_timeout is not None else (self.max_retries + 1)

        for key_idx, current_key in enumerate(keys_to_try):
            headers = {}
            if current_key:
                headers["Authorization"] = f"Bearer {current_key}"

            for attempt in range(max_attempts):
                response = self._execute_multipart_request(url, headers, data, file_paths, request_timeout=request_timeout)

                if response is None:
                    if attempt + 1 < max_attempts:
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
                    if attempt + 1 < max_attempts:
                        print(f"🔄 正在重试 ({attempt + 1}/{max_attempts - 1})...")
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
    def _supports_url_response_format(model: Optional[str]) -> bool:
        if not model:
            return True
        text = str(model).lower()
        if "seedream" in text or text == "z-image-turbo":
            return False
        return "gpt-image-2" not in text

    @staticmethod
    def _is_seedream_model(model: Optional[str]) -> bool:
        if not model:
            return False
        return "seedream" in str(model).lower()

    @staticmethod
    def _supports_seedream_group(model: Optional[str]) -> bool:
        if not model:
            return False
        text = str(model).lower()
        return "seedream-4" in text or "seedream-5" in text

    @staticmethod
    def _supports_seedream_multi_image(model: Optional[str]) -> bool:
        return ImageGenerator._supports_seedream_group(model)

    @staticmethod
    def _is_grok_image_model(model: Optional[str]) -> bool:
        if not model:
            return False
        text = str(model).lower()
        return "grok" in text and "image" in text

    @staticmethod
    def _is_gemini_image_preview_model(model: Optional[str]) -> bool:
        if not model:
            return False
        text = str(model).lower()
        return "gemini" in text and "image-preview" in text

    @staticmethod
    def _is_z_image_model(model: Optional[str]) -> bool:
        if not model:
            return False
        return str(model).lower().strip() == "z-image-turbo"

    @staticmethod
    def _is_gpt_image_2_all_model(model: Optional[str]) -> bool:
        if not model:
            return False
        return str(model).lower().strip() == "gpt-image-2-all"

    @staticmethod
    def _request_model_for_images_endpoint(model: Optional[str]) -> Optional[str]:
        if not model:
            return model
        text = str(model).strip()
        lowered = text.lower()
        if lowered == "grok-imagine-image":
            return "grok-3-image"
        return text

    @staticmethod
    def _summarize_payload_fields(data: Dict[str, Any]) -> List[str]:
        if not isinstance(data, dict):
            return []
        return sorted(str(key) for key in data.keys())

    def _make_request(
        self,
        endpoint: str,
        data: Dict,
        retry_count: int = 0,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[Dict]:
        """发送API请求 (支持多Key轮询)"""
        current_base_url = (base_url or self.base_url).rstrip("/")
        
        # Override model in data if provided, except Gemini native endpoints where
        # the model belongs in the URL and some gateways reject it in the body.
        if model and not endpoint.startswith("/v1beta/models/") and not data.get("model"):
            data["model"] = model
            
        url = self._build_url(current_base_url, endpoint)
        self.last_request_diagnostics = {
            "endpoint": endpoint,
            "url": url,
            "payload_fields": self._summarize_payload_fields(data),
            "model": data.get("model") or model,
        }
        
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
        max_attempts = 1 if request_timeout is not None else (self.max_retries + 1)
        
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
            for attempt in range(max_attempts):
                response = self._execute_raw_request(url, headers, data, request_timeout=request_timeout)
                
                if response is None:
                    last_error = {
                        "status_code": 504 if request_timeout is not None else 502,
                        "message": "Request timed out or failed to reach provider",
                        "endpoint": endpoint,
                        "payload_fields": self._summarize_payload_fields(data),
                    }
                    # Network error, retry same key
                    if attempt + 1 < max_attempts:
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
                        "endpoint": endpoint,
                        "payload_fields": self._summarize_payload_fields(data),
                    }
                    print(f"⚠️ Key #{key_idx} failed with {response.status_code}. Trying next key...")
                    # Break inner loop (retries) to go to next key
                    break 
                
                # If error is likely transient (502, 504), retry same key
                if response.status_code in [502, 504]:
                     message = response.text.strip() if response.text else f"HTTP {response.status_code}"
                     last_error = {
                         "status_code": response.status_code,
                         "message": message,
                         "endpoint": endpoint,
                         "payload_fields": self._summarize_payload_fields(data),
                     }
                     if attempt + 1 < max_attempts:
                         print(f"🔄 正在重试 ({attempt + 1}/{max_attempts - 1})...")
                         time.sleep(2)
                     continue
                
                # Other errors (400 Bad Request) -> Don't switch keys, likely request issue
                print(f"❌ API请求失败: {response.status_code}")
                print(f"   响应: {response.text}")
                self.last_error = {
                    "status_code": response.status_code,
                    "message": response.text.strip() if response.text else f"HTTP {response.status_code}",
                    "endpoint": endpoint,
                    "payload_fields": self._summarize_payload_fields(data),
                }
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
            if payload.get("type") == "image_generation_call":
                result_val = payload.get("result")
                if isinstance(result_val, str) and result_val.strip():
                    normalized = cls._normalize_data_uri(result_val.strip())
                    if normalized.startswith(("http://", "https://", "data:image")):
                        return normalized
                    return f"data:image/png;base64,{result_val.strip()}"

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

    @staticmethod
    def _build_chat_image_prompt(prompt: str, size: str = None, quality: str = None) -> str:
        final_prompt = prompt
        if size:
            if size == "1792x1024":
                final_prompt += " --ar 16:9"
            elif size == "1024x1792":
                final_prompt += " --ar 9:16"
            elif size == "1024x1024":
                final_prompt += " --ar 1:1"
        if quality:
            if quality.lower() in ["2k", "high"]:
                final_prompt += ", (highly detailed, 2k resolution, sharp focus)"
            elif quality.lower() in ["4k", "ultra"]:
                final_prompt += ", (ultra detailed, 4k resolution, 8k, masterpiece, best quality, extreme detail, hyperrealistic)"
        return final_prompt

    def _generate_image_via_chat(
        self,
        prompt: str,
        size: str = None,
        quality: str = None,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
        """通过 Chat API 生成图片 (针对 Gemini 等模型)"""
        final_prompt = self._build_chat_image_prompt(prompt, size=size, quality=quality)

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
            
            response = self._make_request(
                "/v1/chat/completions",
                data,
                base_url=base_url,
                api_key=api_key,
                model=model,
                request_timeout=request_timeout,
            )
            
            if response:
                candidate = self._extract_image_candidate(response)
                if candidate:
                    return candidate
                print("⚠️ Chat 接口返回内容非图片，准备重试更严格指令...")
        
        return None

    def _generate_image_via_responses(
        self,
        prompt: str,
        size: str = None,
        quality: str = None,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
        """通过 Responses API 生成图片 (针对 Grok / OpenAI Responses 兼容链路)"""
        final_prompt = self._build_chat_image_prompt(prompt, size=size, quality=quality)
        print(f"🎨 Responses生成提示词: {final_prompt}")
        data: Dict[str, Any] = {
            "model": model or self.model,
            "input": final_prompt,
            "tools": [{"type": "image_generation"}],
        }
        response = self._make_request(
            "/v1/responses",
            data,
            base_url=base_url,
            api_key=api_key,
            model=model,
            request_timeout=request_timeout,
        )
        if not response:
            return None
        candidate = self._extract_image_candidate(response)
        if candidate:
            return candidate
        output = response.get("output")
        if isinstance(output, list):
            for item in output:
                candidate = self._extract_image_candidate(item)
                if candidate:
                    return candidate
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

    def _generate_image_via_gemini(
        self,
        prompt: str,
        size: str = None,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
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
            response = self._make_request(
                endpoint,
                payload,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )
            if response:
                return self._extract_image_candidate(response)
            return None
        except Exception as e:
            print(f"❌ Gemini 图片生成失败: {e}")
            return None

    @staticmethod
    def _image_path_to_data_uri(path: str) -> Optional[str]:
        if not path or not os.path.exists(path):
            return None
        mime_type = "image/png"
        lowered = path.lower()
        if lowered.endswith((".jpg", ".jpeg")):
            mime_type = "image/jpeg"
        elif lowered.endswith(".webp"):
            mime_type = "image/webp"
        with open(path, "rb") as image_file:
            b64_data = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"

    def _build_images_generation_payload(
        self,
        *,
        prompt: str,
        model: str,
        size: Optional[str] = None,
        image: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        request_model = self._request_model_for_images_endpoint(model)
        payload: Dict[str, Any] = {
            "model": request_model,
            "prompt": prompt,
            "n": 1,
        }
        if size:
            payload["size"] = size
        if image:
            payload["image"] = image
        if self._supports_url_response_format(request_model):
            payload["response_format"] = "url"
        if self._is_z_image_model(request_model):
            payload.update({
                "watermark": False,
                "prompt_extend": True,
            })
        return payload

    def _generate_image_via_images_generation(
        self,
        prompt: str,
        size: str = None,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        image: Optional[Union[str, List[str]]] = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
        target_model = model or self.model
        data = self._build_images_generation_payload(
            prompt=prompt,
            model=target_model,
            size=size,
            image=image,
        )
        response = self._make_request(
            "/v1/images/generations",
            data,
            base_url=base_url,
            api_key=api_key,
            model=target_model,
            request_timeout=request_timeout,
        )

        candidate = self._extract_image_candidate(response)
        if candidate:
            print(f"✅ 图片生成成功: {candidate[:50]}...")
            return candidate
        print("❌ 未获取到图片数据")
        return None

    @staticmethod
    def _normalize_aspect_ratio(aspect_ratio: Optional[str]) -> str:
        text = str(aspect_ratio or "").strip()
        return text or "1:1"

    @staticmethod
    def _describe_aspect_ratio(aspect_ratio: Optional[str]) -> str:
        ratio = ImageGenerator._normalize_aspect_ratio(aspect_ratio)
        if ratio in {"9:16", "3:4", "4:5", "2:3", "1:4", "1:8"}:
            return f"竖向画布（{ratio}）"
        if ratio in {"16:9", "4:3", "5:4", "3:2", "4:1", "8:1", "21:9"}:
            return f"横向画布（{ratio}）"
        return f"方形或居中构图画布（{ratio}）"

    def optimize_prompt(
        self,
        raw_prompt: str,
        subject: str = "general",
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        aspect_ratio: Optional[str] = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
        """
        使用 LLM 优化提示词 (融入结构化思维)
        :param model: 目标绘图模型 (Target Image Model)，用于定制提示词风格。
                      实际推理仍然使用 self.model (System LLM)。
        """
        raw_prompt = (raw_prompt or "").strip()
        if not raw_prompt:
            return None

        # 1. 确定 LLM 和 目标风格
        llm_model = model or self.llm_model or self.model
        if llm_model == "MiniMax-M2.7":
            llm_model = "MiniMax/MiniMax-M2.7"
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
        system_instruction = ""
        user_content = f"Create an educational infographic prompt for: {raw_prompt}. Subject context: {subject}"
        normalized_aspect_ratio = self._normalize_aspect_ratio(aspect_ratio)
        layout_hint = self._describe_aspect_ratio(aspect_ratio)

        # 针对“教材绘图”的特殊处理
        if subject == "textbook":
            style_keywords = p_conf.get("textbook_style_keywords", "modern 2.5D vector illustration, white background")
            template = templates.get("textbook", "")
            if template:
                system_instruction = template.format(
                    neg_constraint=neg_constraint,
                    style_instruction=style_instruction,
                    lang_instruction=lang_instruction,
                    aspect_ratio=normalized_aspect_ratio,
                    layout_hint=layout_hint
                )
            user_content = f"Create a textbook illustration prompt for: {raw_prompt}. Style requirements: {style_keywords}. Subject context: {subject}"
        elif subject == "sketchnote":
            template = templates.get("sketchnote", "")
            if template:
                system_instruction = template.format(
                    neg_constraint=neg_constraint,
                    style_instruction=style_instruction,
                    lang_instruction=lang_instruction,
                    aspect_ratio=normalized_aspect_ratio,
                    layout_hint=layout_hint
                )
            user_content = (
                f"用户提供的内容：\n{raw_prompt}\n\n"
                f"用户当前选择的画幅：{normalized_aspect_ratio}。\n"
                f"请严格按照System Prompt的规则，生成对应的绘画指令。不要解释，直接输出最终的 Prompt。"
            )
        else:
            template = templates.get("general", "")
            if template:
                system_instruction = template.format(
                    neg_constraint=neg_constraint,
                    style_instruction=style_instruction,
                    lang_instruction=lang_instruction,
                    aspect_ratio=normalized_aspect_ratio,
                    layout_hint=layout_hint
                )
        
        # Fallback if template is missing
        if not system_instruction:
            system_instruction = "You are a prompt expert. Rewrite the user prompt."

        guardrail_instruction = (
            "Faithfulness rules (highest priority):\n"
            "1) Preserve the user's core intent and scene.\n"
            "2) Do NOT change key entities, counts, formulas, time/place, or relationships.\n"
            "3) Keep explicitly quoted/backticked text exactly unchanged.\n"
            "4) If uncertain, keep the original wording instead of inventing details.\n"
            "5) Output only one final prompt line, no markdown, no explanation."
        )
        system_instruction = f"{system_instruction}\n\n{guardrail_instruction}"
        must_keep_fragments = self._extract_must_keep_fragments(raw_prompt)
        must_keep_text = "; ".join(must_keep_fragments[:12])
        user_content = (
            f"{user_content}\n\n"
            f"Original prompt (must stay faithful):\n{raw_prompt}\n\n"
            f"Critical terms to preserve when present: {must_keep_text or 'None'}"
        )

        # 注意: 这里使用 llm_model (self.model) 发起请求，而不是传入的 model (可能只是 image model)
        temperature = 0.2
        if (base_url or "").lower().find("moonshot.cn") >= 0 and llm_model.lower().startswith("kimi-"):
            # Moonshot Kimi chat models currently require temperature=1.
            temperature = 1

        data = {
            "model": llm_model, 
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content}
            ],
            "temperature": temperature
        }
        
        print(f"✨ 正在优化提示词 (Target: {target_model}): {raw_prompt}")
        response = self._make_request(
            "/v1/chat/completions",
            data,
            base_url=base_url,
            api_key=api_key,
            model=llm_model,
            request_timeout=request_timeout,
        )
        
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
            content = re.sub(r"^(optimized\s*prompt|prompt)\s*[:：]\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s+", " ", content).strip()

            drifted, missing = self._is_prompt_drifted(raw_prompt, content, must_keep_fragments)
            if drifted:
                print(f"⚠️ 优化结果偏离原意，回退原提示词。missing={missing[:3]}")
                return raw_prompt
            if missing:
                keep_terms = ", ".join(f"`{x}`" for x in missing[:3])
                content = f"{content}. Keep exact terms: {keep_terms}."
            content = content.strip()
            
            if not content or len(content) < 5:
                print("⚠️ 优化结果无效")
                return None

            print(f"✨ 优化完成: {content[:50]}...")
            return content
        
        return None

    def _extract_must_keep_fragments(self, text: str) -> List[str]:
        if not text:
            return []

        fragments: List[str] = []
        seen = set()

        def _add(value: str):
            v = (value or "").strip()
            if len(v) < 2:
                return
            key = v.lower()
            if key in seen:
                return
            seen.add(key)
            fragments.append(v)

        # Keep exact user-specified literal strings first.
        for m in re.findall(r"`([^`]{1,80})`", text):
            _add(m)
        for m in re.findall(r"[\"“”'‘’]([^\"“”'‘’]{2,80})[\"“”'‘’]", text):
            _add(m)

        # Keep common technical tokens and constraints.
        for m in re.findall(r"\b\d{1,4}[:xX]\d{1,4}\b", text):
            _add(m)
        for m in re.findall(r"\b[A-Za-z][A-Za-z0-9_.:/-]{2,}\b", text):
            if any(ch.isdigit() for ch in m) or "-" in m or "_" in m:
                _add(m)
        for m in re.findall(r"\b\d+(?:\.\d+)?(?:%|°|cm|mm|m|km|fps|k|K)?\b", text):
            _add(m)

        return fragments[:20]

    def _is_prompt_drifted(self, raw_prompt: str, optimized_prompt: str, must_keep_fragments: List[str]) -> tuple[bool, List[str]]:
        if not optimized_prompt:
            return True, must_keep_fragments[:]

        raw = raw_prompt.strip()
        opt = optimized_prompt.strip()
        if not raw:
            return False, []

        missing: List[str] = []
        low_opt = opt.lower()
        for frag in must_keep_fragments or []:
            low_frag = frag.lower()
            if low_frag not in low_opt and frag not in opt:
                missing.append(frag)

        # Overly long rewrite usually means it is adding too much invented detail.
        if len(opt) > max(1200, len(raw) * 8):
            return True, missing

        # If many hard constraints are lost, fallback to original prompt.
        if must_keep_fragments and len(missing) >= max(2, int(len(must_keep_fragments) * 0.6)):
            return True, missing

        return False, missing

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
        request_timeout: Optional[int] = None,
    ) -> List[str]:
        target_model = model or self.model
        data: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "watermark": False,
            "output_format": "png",
        }
        target_lower = str(target_model or "").lower()
        if "seedream-5" in target_lower:
            data["size"] = "2K"
        elif size:
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
            request_timeout=request_timeout,
        )
        return self._extract_image_candidates(response)

    def generate_modified_image(
        self,
        prompt: str,
        base_image_paths: list[str],
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        size: str = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
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
                    request_timeout=request_timeout,
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
                response = self._make_request(
                    endpoint,
                    payload,
                    base_url=base_url,
                    api_key=api_key,
                    model=target_model,
                    request_timeout=request_timeout,
                )
                
                if response:
                    return self._extract_image_candidate(response)
                return None

            # -------------------------------------------------
            # 2. OPENAI IMAGE EDITS (gpt-image / dall-e)
            # -------------------------------------------------
            if is_openai_image:
                if self._is_gpt_image_2_all_model(target_model):
                    reference_images = []
                    for img_path in base_image_paths:
                        data_uri = self._image_path_to_data_uri(img_path)
                        if data_uri:
                            reference_images.append(data_uri)
                    if not reference_images:
                        return None
                    print(f"🎨 GPT Image 2 JSON 参考图生成 ({len(reference_images)} refs): {prompt}")
                    return self._generate_image_via_images_generation(
                        edit_instruction,
                        size=size or self.config.get("image", {}).get("size"),
                        base_url=base_url,
                        api_key=api_key,
                        model=target_model,
                        image=reference_images,
                        request_timeout=request_timeout,
                    )

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
                    request_timeout=request_timeout,
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

            response = self._make_request(
                "/v1/chat/completions",
                data,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )

            if response:
                candidate = self._extract_image_candidate(response)
                if candidate:
                    return candidate
            return None

        except Exception as e:
            print(f"❌ 图片修改失败: {e}")
            return None

    def generate_image(
        self,
        prompt: str,
        size: str = None,
        quality: str = None,
        style: str = None,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
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
                request_timeout=request_timeout,
            )
            return seedream_images[0] if seedream_images else None

        target_model_lower = (target_model or "").lower()

        # Gemini / Nano Banana image-preview 系列优先走 Gemini 原生 generateContent。
        if self._is_gemini_image_preview_model(target_model):
            print(f"🤖 检测到 Gemini Image Preview，优先尝试 generateContent 接口...")
            gemini_result = self._generate_image_via_gemini(
                prompt,
                size=size,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )
            if gemini_result:
                return gemini_result
            print("⚠️ Gemini generateContent 未返回图片，回退到 Chat Completions...")
            return self._generate_image_via_chat(
                prompt,
                size,
                quality,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )
        if self._is_grok_image_model(target_model):
            print("🤖 检测到 Grok Image，优先尝试 images/generations 接口...")
            images_result = self._generate_image_via_images_generation(
                prompt,
                size=size,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )
            if images_result:
                return images_result
            print("⚠️ Grok images/generations 未返回图片，回退到 Chat / Responses...")
            chat_result = self._generate_image_via_chat(
                prompt,
                size,
                quality,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )
            if chat_result:
                return chat_result
            responses_result = self._generate_image_via_responses(
                prompt,
                size,
                quality,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )
            if responses_result:
                return responses_result
            return None
        # Gemini 2.5 Flash Image: 使用 generateContent
        if "gemini-2.5-flash-image" in target_model_lower:
            print(f"🤖 检测到 Gemini 2.5 Flash Image，切换到 generateContent 接口...")
            return self._generate_image_via_gemini(
                prompt,
                size=size,
                base_url=base_url,
                api_key=api_key,
                model=target_model,
                request_timeout=request_timeout,
            )

        # 大多数中转商使用标准的 OpenAI 图片接口
        return self._generate_image_via_images_generation(
            prompt,
            size=size,
            base_url=base_url,
            api_key=api_key,
            model=target_model,
            request_timeout=request_timeout,
        )

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
            self.last_error = None
            print(f"📥 准备保存图片到: {save_path}")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 处理 Base64 Data URI
            if image_url.startswith("data:image"):
                image_url = self._normalize_data_uri(image_url)
                if "," not in image_url:
                    print("❌ Base64数据缺少逗号分隔，无法解析")
                    self._remember_error("Base64 image payload missing comma separator")
                    return False
                try:
                    # 格式: data:image/png;base64,.....
                    header, encoded = image_url.split(",", 1)
                    data = base64.b64decode(encoded)
                    if not self._is_valid_image_bytes(data):
                        print("❌ Base64内容不是有效图片，已终止保存")
                        self._remember_error("Base64 payload is not a valid image")
                        return False
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    print(f"✅ Base64图片解码并保存成功")
                    return True
                except Exception as e:
                    print(f"❌ Base64解码失败: {e}")
                    self._remember_error(f"Base64 image decode failed: {e}")
                    return False

            # 处理普通 URL
            # 有些 URL 需要代理，有些不需要，这里直接请求
            response = requests.get(image_url, timeout=60)

            if response.status_code == 200:
                content_type = (response.headers.get("Content-Type") or "").lower()
                if content_type and not content_type.startswith("image/"):
                    print(f"❌ 响应类型不是图片: {content_type}")
                    self._remember_error(f"Downloaded content-type is not an image: {content_type}", status_code=200)
                    return False
                if not self._is_valid_image_bytes(response.content):
                    print("❌ 下载内容不是有效图片，已终止保存")
                    self._remember_error("Downloaded content is not a valid image", status_code=200)
                    return False
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ 下载成功")
                return True
            else:
                print(f"❌ 下载失败: {response.status_code}")
                self._remember_error(f"Image download failed with HTTP {response.status_code}", status_code=response.status_code)
                return False
        except Exception as e:
            print(f"❌ 下载异常: {e}")
            self._remember_error(f"Image download raised exception: {e}")
            return False

    @staticmethod
    def _parse_size(size: Optional[str]) -> tuple[int, int]:
        text = str(size or "").strip().lower()
        if "x" not in text:
            return (1024, 1024)
        left, _, right = text.partition("x")
        try:
            width = max(256, min(2048, int(left)))
            height = max(256, min(2048, int(right)))
            return (width, height)
        except Exception:
            return (1024, 1024)

    @staticmethod
    def _load_fallback_font(size: int) -> ImageFont.ImageFont:
        for candidate in _font_candidates():
            if not os.path.exists(candidate):
                continue
            try:
                return ImageFont.truetype(candidate, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    def create_local_fallback_image(self, prompt: str, save_path: str, size: Optional[str] = None) -> bool:
        """Create a deterministic local image when all remote providers fail."""
        try:
            width, height = self._parse_size(size)
            digest = hashlib.sha256((prompt or "fallback-image").encode("utf-8")).digest()
            bg = tuple(40 + digest[i] % 120 for i in range(3))
            accent = tuple(120 + digest[i + 3] % 100 for i in range(3))
            accent2 = tuple(100 + digest[i + 6] % 120 for i in range(3))

            image = Image.new("RGB", (width, height), bg)
            draw = ImageDraw.Draw(image, "RGBA")

            for idx in range(5):
                x0 = int((digest[idx] / 255) * width * 0.7)
                y0 = int((digest[idx + 5] / 255) * height * 0.7)
                x1 = x0 + int(width * (0.18 + (digest[idx + 10] / 255) * 0.32))
                y1 = y0 + int(height * (0.12 + (digest[idx + 15] / 255) * 0.28))
                color = accent if idx % 2 == 0 else accent2
                alpha = 70 + (digest[idx + 20] % 80)
                draw.rounded_rectangle((x0, y0, x1, y1), radius=32, fill=(*color, alpha))

            panel_margin = int(min(width, height) * 0.08)
            draw.rounded_rectangle(
                (panel_margin, panel_margin, width - panel_margin, height - panel_margin),
                radius=36,
                fill=(255, 255, 255, 210),
                outline=(*accent2, 220),
                width=4,
            )

            title_font = self._load_fallback_font(max(24, width // 18))
            body_font = self._load_fallback_font(max(16, width // 32))
            title = "Nano Banana Fallback"
            body = (prompt or "Image generation fallback").strip()
            body = re.sub(r"\s+", " ", body)[:120]

            title_box = draw.textbbox((0, 0), title, font=title_font)
            title_w = title_box[2] - title_box[0]
            draw.text(
                ((width - title_w) // 2, int(height * 0.18)),
                title,
                font=title_font,
                fill=(20, 20, 20, 255),
            )

            body_x = panel_margin + 36
            body_y = int(height * 0.36)
            draw.multiline_text(
                (body_x, body_y),
                body,
                font=body_font,
                fill=(35, 35, 35, 255),
                spacing=8,
            )

            footer = "All configured providers failed. Returned local fallback image."
            draw.multiline_text(
                (body_x, height - panel_margin - 90),
                footer,
                font=body_font,
                fill=(70, 70, 70, 255),
                spacing=6,
            )

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            image.save(save_path, format="PNG")
            return True
        except Exception as e:
            print(f"❌ 本地兜底图片生成失败: {e}")
            return False

    def generate_and_download(
        self,
        prompt: str,
        filename: str,
        folder: str = "generated_images",
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        request_timeout: Optional[int] = None,
    ) -> Optional[str]:
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
                image_url = self.generate_image(
                    prompt,
                    base_url=base_url,
                    api_key=api_key,
                    model=model_name,
                    request_timeout=request_timeout,
                )
                if not image_url:
                    continue
                if self.download_image(image_url, save_path):
                    return save_path
                print(f"⚠️ 图片内容无效，重试生成 ({attempt + 1}/{self.max_retries})...")

        self._remember_error(
            (self.last_error or {}).get("message") or "All generation/download attempts returned invalid image content"
        )
        return None

# 单例辅助函数
def get_image_generator() -> ImageGenerator:
    return ImageGenerator()
