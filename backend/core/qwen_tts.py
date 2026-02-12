import json
import os
from typing import Optional, Tuple

import requests


def synthesize_tts(
    text: str,
    output_dir: str,
    filename_base: str,
    voice: str,
    model: str,
    instructions: Optional[str] = None,
    optimize_instructions: bool = True,
    response_format: str = "wav",
    sample_rate: int = 24000,
    mode: str = "server_commit",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    language_type: str = "Auto",
    timeout: int = 120,
) -> Tuple[str, str]:
    if not api_key:
        raise RuntimeError("Missing API Key (configure model or provide x-tts-key).")
    if response_format != "wav":
        raise RuntimeError("REST TTS only supports wav output.")

    # REST (MultiModalConversation) mode for qwen3-tts-flash / qwen-tts
    try:
        import dashscope
    except Exception as exc:
        raise RuntimeError("DashScope SDK not installed. Please run `pip install dashscope`.") from exc

    dashscope.api_key = api_key
    if base_url:
        dashscope.base_http_api_url = base_url

    resp = dashscope.MultiModalConversation.call(
        model=model,
        api_key=api_key,
        text=text,
        voice=voice,
        language_type=language_type,
        stream=False
    )

    def _coerce_payload(obj):
        if isinstance(obj, dict):
            return obj
        for method_name in ("model_dump", "dict", "to_dict"):
            try:
                method = getattr(obj, method_name, None)
            except Exception:
                method = None
            if callable(method):
                try:
                    data = method()
                    if data is not None:
                        return data
                except Exception:
                    pass
        candidate = {}
        for attr in ("status_code", "code", "message", "msg", "output", "data", "result", "results"):
            try:
                if hasattr(obj, attr):
                    candidate[attr] = getattr(obj, attr)
            except Exception:
                pass
        if candidate:
            return candidate
        try:
            data = obj.__dict__
            if data:
                return data
        except Exception:
            pass
        return {"raw": str(obj)}

    payload = _coerce_payload(resp)
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {"raw": payload}

    if isinstance(payload, dict):
        status_code = payload.get("status_code") or payload.get("code")
        if status_code not in (None, 200, "200", "SUCCESS"):
            message = payload.get("message") or payload.get("msg") or str(payload)
            raise RuntimeError(f"TTS request failed: {message}")

    def _extract_audio_url(obj):
        if isinstance(obj, dict):
            for key in ("url", "audio_url", "audioUrl"):
                if key in obj and isinstance(obj[key], str):
                    return obj[key]
            for value in obj.values():
                found = _extract_audio_url(value)
                if found:
                    return found
        if isinstance(obj, list):
            for item in obj:
                found = _extract_audio_url(item)
                if found:
                    return found
        return None

    audio_url = _extract_audio_url(payload)
    if not audio_url:
        raise RuntimeError(f"No audio url found in response: {payload}")

    os.makedirs(output_dir, exist_ok=True)
    wav_path = os.path.join(output_dir, f"{filename_base}.wav")
    resp = requests.get(audio_url, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to download audio: {resp.status_code}")
    with open(wav_path, "wb") as f:
        f.write(resp.content)
    return wav_path, "audio/wav"
