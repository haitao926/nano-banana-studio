import json
import os
from typing import Optional, Dict, Any, Iterable

import requests

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DETECT_PATH = "/services/aigc/image2video/face-detect"
SYNTH_PATH = "/services/aigc/image2video/video-synthesis/"
TASK_PATH = "/tasks/{task_id}"


class DigitalHumanGenerator:
    def __init__(self, default_base_url: Optional[str] = None):
        self.default_base_url = default_base_url or DEFAULT_BASE_URL

    @staticmethod
    def _extract_value(payload: Any, keys: Iterable[str]) -> Optional[Any]:
        if isinstance(payload, dict):
            for key in keys:
                if key in payload:
                    return payload[key]
            for value in payload.values():
                found = DigitalHumanGenerator._extract_value(value, keys)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = DigitalHumanGenerator._extract_value(item, keys)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _normalize_status(status: Optional[str]) -> Optional[str]:
        if status is None:
            return None
        value = str(status).strip()
        if not value:
            return None
        upper = value.upper()
        if upper in ("PROCESSING", "GENERATING"):
            return "processing"
        if upper in ("IN_QUEUE", "QUEUED"):
            return "in_queue"
        if upper in ("DONE", "COMPLETED"):
            return "done"
        if upper in ("NOT_FOUND", "EXPIRED"):
            return "expired"
        if upper == "PENDING":
            return "processing"
        if upper == "RUNNING":
            return "running"
        if upper == "SUCCEEDED":
            return "done"
        if upper in ("FAILED", "CANCELED", "CANCELLED"):
            return "failed"
        if upper == "UNKNOWN":
            return "expired"
        return value.lower()

    @staticmethod
    def _resolve_api_key(api_key: Optional[str]) -> Optional[str]:
        return api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("DASHSCOPE_VIDEO_API_KEY")

    def _normalize_base_url(self, base_url: Optional[str]) -> str:
        value = (base_url or "").strip().rstrip("/")
        if not value:
            return self.default_base_url
        if "compatible-mode" in value:
            raise RuntimeError(
                "DashScope compatible-mode base_url is not supported for wan2.2-s2v. "
                "Use https://dashscope.aliyuncs.com/api/v1"
            )
        api_index = value.find("/api/v1")
        if api_index != -1:
            return value[: api_index + len("/api/v1")]
        return f"{value}/api/v1"

    @staticmethod
    def _normalize_resolution(resolution: Any) -> str:
        if resolution is None:
            return "480P"
        value = str(resolution).strip().upper()
        if value in ("480", "480P"):
            return "480P"
        if value in ("720", "720P", "1080", "1080P"):
            return "720P"
        return "480P"

    @staticmethod
    def _normalize_style(style: Optional[str]) -> Optional[str]:
        if not style:
            return None
        value = str(style).strip().lower()
        if not value:
            return None
        if value in ("speech", "speaking", "talk", "talking"):
            return "speech"
        if value in ("sing", "singing"):
            return "sing"
        if value in ("perform", "performance", "performing", "act", "acting"):
            return "performance"
        return None

    @staticmethod
    def _coerce_response(resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        if isinstance(data, dict):
            data.setdefault("status_code", resp.status_code)
            data.setdefault("request_id", resp.headers.get("X-Request-Id"))
            return data
        return {"status_code": resp.status_code, "raw": data}


    def _request(
        self,
        method: str,
        url: str,
        api_key: str,
        payload: Optional[Dict[str, Any]] = None,
        async_call: bool = False,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if async_call:
            headers["X-DashScope-Async"] = "enable"
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=timeout)
            else:
                resp = requests.post(url, headers=headers, json=payload or {}, timeout=timeout)
        except Exception as exc:
            return {"error": f"Request error: {exc}"}
        return self._coerce_response(resp)

    def detect_image(self, image_url: str, api_key: str, base_url: str) -> Dict[str, Any]:
        payload = {
            "model": "wan2.2-s2v-detect",
            "input": {"image_url": image_url},
        }
        url = f"{base_url}{DETECT_PATH}"
        return self._request("POST", url, api_key, payload=payload)

    def submit_task(
        self,
        image_url: str,
        audio_url: str,
        prompt: Optional[str] = None,
        seed: int = -1,
        resolution: int = 720,
        fast_mode: bool = False,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        style: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing DashScope API Key (video.api_key or DASHSCOPE_API_KEY)."}

        try:
            resolved_base = self._normalize_base_url(base_url)
        except Exception as exc:
            return {"error": str(exc)}

        detect_resp = self.detect_image(image_url, resolved_key, resolved_base)
        detect_error = self.extract_error(detect_resp)
        if detect_error:
            return {"error": detect_error, "raw": detect_resp}
        check_pass = self._extract_value(detect_resp, ["check_pass", "checkPass"])
        if check_pass is False:
            message = self._extract_value(detect_resp, ["message", "msg", "error"])
            return {"error": message or "Image check failed", "raw": detect_resp}

        params: Dict[str, Any] = {
            "resolution": self._normalize_resolution(resolution)
        }

        normalized_style = self._normalize_style(style)
        if normalized_style:
            params["style"] = normalized_style

        payload = {
            "model": "wan2.2-s2v",
            "input": {
                "image_url": image_url,
                "audio_url": audio_url,
            },
            "parameters": params,
        }

        url = f"{resolved_base}{SYNTH_PATH}"
        return self._request("POST", url, resolved_key, payload=payload, async_call=True, timeout=120)

    def get_task_result(self, task_id: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> Dict[str, Any]:
        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing DashScope API Key (video.api_key or DASHSCOPE_API_KEY)."}

        try:
            resolved_base = self._normalize_base_url(base_url)
        except Exception as exc:
            return {"error": str(exc)}

        url = f"{resolved_base}{TASK_PATH.format(task_id=task_id)}"
        return self._request("GET", url, resolved_key, timeout=60)


    @staticmethod
    def extract_error(payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        if payload.get("error"):
            return str(payload["error"])

        status_code = payload.get("status_code")
        if isinstance(status_code, int) and status_code >= 400:
            message = payload.get("message") or payload.get("msg") or payload.get("raw")
            return str(message) if message else f"HTTP {status_code}"

        code = payload.get("code")
        if code is not None:
            code_text = str(code).strip().upper()
            if code_text not in ("OK", "SUCCESS", "200", "10000", "0"):
                return payload.get("message") or payload.get("msg") or str(code)

        output = payload.get("output")
        if isinstance(output, dict):
            check_pass = output.get("check_pass")
            if check_pass is False:
                return output.get("message") or "Image check failed"

            task_status = output.get("task_status") or output.get("taskStatus")
            if not task_status:
                out_code = output.get("code")
                if out_code and str(out_code).upper() not in ("OK", "SUCCESS", "200"):
                    return output.get("message") or output.get("msg") or str(out_code)

        return None

    def normalize_submit_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        task_id = self._extract_value(payload, ["task_id", "taskId", "TaskID", "TaskId"])
        return {"task_id": task_id} if task_id else {}

    def normalize_status_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_status = self._extract_value(
            payload,
            ["task_status", "taskStatus", "status", "Status", "state", "State"],
        )
        status = self._normalize_status(raw_status)
        video_url = self._extract_value(payload, ["video_url", "videoUrl", "VideoURL", "VideoUrl"])
        error_message = self._extract_value(payload, ["message", "Message", "error", "Error"])

        data: Dict[str, Any] = {}
        if status is not None:
            data["status"] = status
        if video_url is not None:
            data["video_url"] = video_url
        if error_message is not None:
            data["error_message"] = error_message
        return data
