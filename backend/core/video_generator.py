import base64
import os
from typing import Any, Dict, Optional, Iterable

import requests


DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_VEO_BASE_URL = "https://api.vectorengine.ai"

try:
    from volcenginesdkarkruntime import Ark
except Exception:
    Ark = None


class VideoGenerator:
    def __init__(self, default_base_url: Optional[str] = None):
        self.default_base_url = default_base_url or DEFAULT_BASE_URL

    @staticmethod
    def _extract_value(payload: Any, keys: Iterable[str]) -> Optional[Any]:
        if isinstance(payload, dict):
            for key in keys:
                if key in payload:
                    return payload[key]
            for value in payload.values():
                found = VideoGenerator._extract_value(value, keys)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = VideoGenerator._extract_value(item, keys)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _normalize_base_url(base_url: Optional[str], default_base_url: str) -> str:
        value = (base_url or "").strip().rstrip("/")
        if not value:
            return default_base_url
        api_index = value.find("/v1beta")
        if api_index != -1:
            return value[: api_index + len("/v1beta")]
        return f"{value}/v1beta"

    @staticmethod
    def _resolve_api_key(api_key: Optional[str]) -> Optional[str]:
        return api_key or os.getenv("GEMINI_API_KEY") or os.getenv("VIDEO_API_KEY")

    @staticmethod
    def _resolve_ark_key(api_key: Optional[str]) -> Optional[str]:
        return api_key or os.getenv("ARK_API_KEY")

    @staticmethod
    def _normalize_ark_base_url(base_url: Optional[str]) -> str:
        value = (base_url or "").strip().rstrip("/")
        if not value:
            return DEFAULT_ARK_BASE_URL
        if value.endswith("/api/v3"):
            return value
        return f"{value}/api/v3"

    @staticmethod
    def _is_ark_model(model: Optional[str]) -> bool:
        if not model:
            return False
        text = str(model).strip().lower()
        return "wan2-" in text or "doubao" in text or "seedance" in text or "ark" in text or "volc" in text

    @staticmethod
    def _is_veo_model(model: Optional[str]) -> bool:
        if not model:
            return False
        return "veo" in str(model).strip().lower()

    @staticmethod
    def _is_sora_model(model: Optional[str]) -> bool:
        if not model:
            return False
        return "sora" in str(model).strip().lower()

    @staticmethod
    def _normalize_veo_base_url(base_url: Optional[str]) -> str:
        value = (base_url or "").strip().rstrip("/")
        return value or DEFAULT_VEO_BASE_URL

    @staticmethod
    def _map_veo_model(model: str) -> str:
        text = (model or "").strip()
        mapping = {
            "veo-3.1-generate-preview": "veo3.1",
            "veo-3.1-fast-generate-preview": "veo3.1-fast",
            "veo-3.1": "veo3.1",
            "veo-3.1-fast": "veo3.1-fast",
            "veo-3.1-pro": "veo3.1-pro",
            "veo-3.1-4k": "veo3.1-4k",
            "veo-3.1-pro-4k": "veo3.1-pro-4k",
        }
        if text in mapping:
            return mapping[text]
        if text.startswith("veo-"):
            return f"veo{text[4:]}"
        return text

    @staticmethod
    def _should_enhance_prompt(prompt: str) -> bool:
        if not prompt:
            return False
        return any(ord(ch) > 127 for ch in prompt)

    def _request_veo(
        self,
        method: str,
        url: str,
        api_key: Optional[str],
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=timeout)
            else:
                resp = requests.post(url, headers=headers, json=payload or {}, timeout=timeout)
        except Exception as exc:
            return {"error": f"Request error: {exc}"}
        return self._coerce_response(resp)

    @staticmethod
    def _coerce_response(resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        if isinstance(data, dict):
            data.setdefault("status_code", resp.status_code)
            return data
        return {"status_code": resp.status_code, "raw": data}

    @staticmethod
    def _coerce_ark_payload(payload: Any) -> Dict[str, Any]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        for attr in ("model_dump", "dict", "to_dict"):
            try:
                fn = getattr(payload, attr)
            except Exception:
                fn = None
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    pass
        try:
            return dict(payload)
        except Exception:
            pass
        try:
            return payload.__dict__
        except Exception:
            return {"raw": str(payload)}

    @staticmethod
    def _append_ark_flags(prompt: str, resolution: Optional[str], duration_seconds: Optional[int]) -> str:
        text = prompt or ""
        lower = text.lower()
        if resolution and "--resolution" not in lower:
            res = str(resolution).lower()
            if res in ("720", "720p"):
                text += " --resolution 720p"
            elif res in ("1080", "1080p"):
                text += " --resolution 1080p"
        if duration_seconds and "--duration" not in lower:
            text += f" --duration {int(duration_seconds)}"
        return text.strip()

    def _request(
        self,
        method: str,
        url: str,
        api_key: Optional[str],
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["x-goog-api-key"] = api_key
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=timeout)
            else:
                resp = requests.post(url, headers=headers, json=payload or {}, timeout=timeout)
        except Exception as exc:
            return {"error": f"Request error: {exc}"}
        return self._coerce_response(resp)

    def submit_task(
        self,
        prompt: str,
        model: str,
        image_url: Optional[str] = None,
        image_urls: Optional[Iterable[str]] = None,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._is_sora_model(model):
            return self.submit_task_sora(
                prompt=prompt,
                model=model,
                image_url=image_url,
                image_urls=image_urls,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                duration_seconds=duration_seconds,
                api_key=api_key,
                base_url=base_url,
            )
        if self._is_veo_model(model):
            return self.submit_task_veo(
                prompt=prompt,
                model=model,
                image_url=image_url,
                aspect_ratio=aspect_ratio,
                api_key=api_key,
                base_url=base_url,
            )
        if self._is_ark_model(model):
            return self.submit_task_ark(
                prompt=prompt,
                model=model,
                image_url=image_url,
                resolution=resolution,
                duration_seconds=duration_seconds,
                api_key=api_key,
                base_url=base_url,
            )

        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing Gemini API Key (provide x-video-key or GEMINI_API_KEY)."}

        resolved_base = self._normalize_base_url(base_url, self.default_base_url)
        url = f"{resolved_base}/models/{model}:predictLongRunning"

        instance: Dict[str, Any] = {"prompt": prompt}
        if image_bytes:
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            instance["image"] = {
                "inlineData": {
                    "mimeType": image_mime or "image/png",
                    "data": encoded,
                }
            }

        parameters: Dict[str, Any] = {}
        if aspect_ratio:
            parameters["aspectRatio"] = aspect_ratio
        if resolution:
            parameters["resolution"] = resolution
        if duration_seconds is not None:
            parameters["durationSeconds"] = str(duration_seconds)

        payload: Dict[str, Any] = {"instances": [instance]}
        if parameters:
            payload["parameters"] = parameters

        return self._request("POST", url, resolved_key, payload=payload, timeout=120)

    def submit_task_sora(
        self,
        prompt: str,
        model: str,
        image_url: Optional[str] = None,
        image_urls: Optional[Iterable[str]] = None,
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not api_key:
            return {"error": "Missing Sora API Key (provide x-video-key)."}
        urls = [u for u in (image_urls or []) if u]
        if not urls and image_url:
            urls = [image_url]
        if not urls:
            return {"error": "Sora requires at least one image URL (images or image_url)."}
        resolved_base = self._normalize_veo_base_url(base_url)
        url = f"{resolved_base}/v1/video/create"
        orientation = "portrait" if aspect_ratio == "9:16" else "landscape"
        size = "large" if str(resolution).lower() in ("1080", "1080p", "4k") else "small"
        duration = int(duration_seconds) if duration_seconds else 10
        payload: Dict[str, Any] = {
            "images": urls,
            "model": model,
            "orientation": orientation,
            "prompt": prompt,
            "size": size,
            "duration": duration,
            "watermark": False,
        }
        return self._request_veo("POST", url, api_key, payload=payload, timeout=120)

    def submit_task_veo(
        self,
        prompt: str,
        model: str,
        image_url: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not api_key:
            return {"error": "Missing Veo API Key (provide x-video-key)."}
        resolved_base = self._normalize_veo_base_url(base_url)
        url = f"{resolved_base}/v1/video/create"
        payload: Dict[str, Any] = {
            "model": self._map_veo_model(model),
            "prompt": prompt,
            "enhance_prompt": self._should_enhance_prompt(prompt),
            "enable_upsample": False,
            "aspect_ratio": aspect_ratio or "16:9",
        }
        if image_url:
            payload["images"] = [image_url]
        return self._request_veo("POST", url, api_key, payload=payload, timeout=120)

    def submit_task_ark(
        self,
        prompt: str,
        model: str,
        image_url: Optional[str] = None,
        resolution: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_key = self._resolve_ark_key(api_key)
        if not resolved_key:
            return {"error": "Missing Ark API Key (provide x-video-key or ARK_API_KEY)."}
        if Ark is None:
            return {"error": "volcengine-python-sdk[ark] is not installed."}

        resolved_base = self._normalize_ark_base_url(base_url)
        final_prompt = self._append_ark_flags(prompt, resolution, duration_seconds)
        content = [{"type": "text", "text": final_prompt}]
        if image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        client = Ark(base_url=resolved_base, api_key=resolved_key)
        try:
            result = client.content_generation.tasks.create(model=model, content=content)
        except Exception as exc:
            return {"error": f"Ark request error: {exc}"}
        return self._coerce_ark_payload(result)

    def get_task_result(
        self,
        operation_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._is_sora_model(model):
            return self.get_task_result_veo(operation_name, api_key=api_key, base_url=base_url)
        if self._is_veo_model(model):
            return self.get_task_result_veo(operation_name, api_key=api_key, base_url=base_url)
        if self._is_ark_model(model):
            return self.get_task_result_ark(operation_name, api_key=api_key, base_url=base_url)

        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing Gemini API Key (provide x-video-key or GEMINI_API_KEY)."}

        resolved_base = self._normalize_base_url(base_url, self.default_base_url)
        op = (operation_name or "").strip()
        if op.startswith("http://") or op.startswith("https://"):
            url = op
        else:
            url = f"{resolved_base}/{op.lstrip('/')}"
        return self._request("GET", url, resolved_key, timeout=60)

    def get_task_result_veo(
        self,
        task_id: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not api_key:
            return {"error": "Missing Veo API Key (provide x-video-key)."}
        resolved_base = self._normalize_veo_base_url(base_url)
        # Try common status endpoints with multiple id field variants
        payload = {"id": task_id, "task_id": task_id, "taskId": task_id}
        for method, path, body in (
            ("GET", f"{resolved_base}/v1/video/status?id={task_id}", None),
            ("GET", f"{resolved_base}/v1/video/status?task_id={task_id}", None),
            ("GET", f"{resolved_base}/v1/video/get?id={task_id}", None),
            ("GET", f"{resolved_base}/v1/video/get?task_id={task_id}", None),
            ("POST", f"{resolved_base}/v1/video/status", payload),
            ("POST", f"{resolved_base}/v1/video/get", payload),
        ):
            result = self._request_veo(method, path, api_key, payload=body, timeout=60)
            error = self.extract_error(result)
            if not error:
                return result
        return result

    def get_task_result_ark(
        self,
        task_id: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_key = self._resolve_ark_key(api_key)
        if not resolved_key:
            return {"error": "Missing Ark API Key (provide x-video-key or ARK_API_KEY)."}
        if Ark is None:
            return {"error": "volcengine-python-sdk[ark] is not installed."}

        resolved_base = self._normalize_ark_base_url(base_url)
        client = Ark(base_url=resolved_base, api_key=resolved_key)
        try:
            result = client.content_generation.tasks.get(task_id=task_id)
        except Exception as exc:
            return {"error": f"Ark request error: {exc}"}
        return self._coerce_ark_payload(result)

    @staticmethod
    def extract_error(payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        if payload.get("error"):
            return str(payload["error"])
        status = payload.get("status")
        if status and str(status).lower() == "failed":
            return str(payload.get("error") or payload.get("message") or "Video generation failed.")
        status_code = payload.get("status_code")
        if isinstance(status_code, int) and status_code >= 400:
            message = payload.get("message") or payload.get("error") or payload.get("raw")
            return str(message) if message else f"HTTP {status_code}"
        if payload.get("done") is True and payload.get("response") is None:
            return "Video generation failed without response."
        return None

    @classmethod
    def extract_video_url(cls, payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        # 1) Explicit video URL fields anywhere in payload
        explicit = cls._extract_value(payload, ["video_url", "videoUrl", "video_uri", "videoUri"])
        if explicit:
            return explicit

        # 2) Known Gemini response structure
        response = payload.get("response")
        for container in (response, response.get("generateVideoResponse") if isinstance(response, dict) else None):
            if not isinstance(container, dict):
                continue
            for key in ("generatedSamples", "generated_samples", "generatedVideos", "generated_videos"):
                items = container.get(key)
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        video = item.get("video") or {}
                        if isinstance(video, dict):
                            uri = video.get("uri") or video.get("url") or video.get("videoUri")
                            if uri:
                                return uri

        # 3) Ark-style content/output arrays: pick url only if the item is video-typed
        def _find_video_url(node: Any) -> Optional[str]:
            if isinstance(node, dict):
                node_type = str(node.get("type") or "").lower()
                if "video" in node_type:
                    return node.get("url") or node.get("video_url") or node.get("videoUrl")
                if "video" in node:
                    video = node.get("video")
                    if isinstance(video, dict):
                        return video.get("url") or video.get("uri") or video.get("videoUrl") or video.get("video_url")
                for value in node.values():
                    found = _find_video_url(value)
                    if found:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = _find_video_url(item)
                    if found:
                        return found
            return None

        for key in ("output", "outputs", "content", "contents", "result", "results", "data"):
            found = _find_video_url(payload.get(key))
            if found:
                return found

        # 4) Last resort: avoid grabbing image_url by only accepting url values in video-typed nodes
        return None
