import argparse
import contextlib
import getpass
import io
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests


BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
BACKEND_CONNECT_TIMEOUT_SECONDS = float(os.getenv("NBS_BACKEND_CONNECT_TIMEOUT_SECONDS", "8"))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("NBS_QUIET", "1")

from app_state import AUDIO_DIR, BATCH_DIR, GENERATED_DIR, STATIC_DIR, batch_gen, digital_human_gen, img_gen, video_gen  # noqa: E402
from core.qwen_tts import synthesize_tts  # noqa: E402
from helpers import (  # noqa: E402
    _build_model_candidates,
    _get_default_model,
    _get_model_catalog,
    _resolve_public_media_url,
    sanitize_filename,
)


def _print(data: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(str(data))


def _fail(message: str, as_json: bool = False, extra: Optional[Dict[str, Any]] = None) -> int:
    payload = {"success": False, "error": message}
    if extra:
        payload.update(extra)
    _print(payload if as_json else message, as_json=as_json)
    return 1


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _should_quiet(as_json: bool) -> bool:
    return as_json and not _env_flag("NBS_VERBOSE")


def _http_timeout(read_timeout: int | float) -> tuple[float, float]:
    read_value = max(1.0, float(read_timeout))
    connect_value = max(1.0, min(BACKEND_CONNECT_TIMEOUT_SECONDS, read_value))
    return (connect_value, read_value)


def _invoke_core(func: Any, *args: Any, quiet: bool = False, **kwargs: Any) -> Any:
    if not quiet:
        return func(*args, **kwargs)
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        return func(*args, **kwargs)


def _resolve_candidates(service: str, model: Optional[str], explicit_key: Optional[str], explicit_base_url: Optional[str]) -> list[Dict[str, Any]]:
    candidates = _build_model_candidates(
        service,
        model=model,
        runtime_key=explicit_key,
        runtime_base_url=explicit_base_url,
        fallback_base_url=explicit_base_url,
    )
    if not candidates:
        raise RuntimeError(f"No available key candidates for service={service}, model={model or '-'}")
    return candidates


def _default_output_path(directory: str, prefix: str, extension: str, prompt_like: str) -> str:
    safe = sanitize_filename(prompt_like) or prefix
    timestamp = int(time.time())
    filename = f"{safe}_{timestamp}{extension}"
    return os.path.join(directory, filename)


def _build_image_model_attempt_chain(preferred: Optional[str]) -> list[str]:
    chain: list[str] = []
    seen: set[str] = set()

    def add(model_name: Optional[str]) -> None:
        text = str(model_name or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        chain.append(text)

    add(preferred)
    for item in _get_model_catalog():
        if item.get("service") != "image" or not item.get("enabled", True):
            continue
        add(item.get("model"))
    return chain


def _write_json_sidecar(path: str, payload: Dict[str, Any]) -> None:
    sidecar = f"{os.path.splitext(path)[0]}.json"
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _auth_file_path() -> Path:
    override = os.getenv("NBS_AUTH_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".nbs" / "auth.json"


def _auth_base_url(explicit: Optional[str] = None) -> str:
    value = str(explicit or os.getenv("NBS_API_BASE_URL") or "http://127.0.0.1:8000").strip().rstrip("/")
    if not value:
        raise RuntimeError("Missing API base URL. Set --base-url or NBS_API_BASE_URL.")
    return value


def _load_auth_session() -> Dict[str, Any]:
    path = _auth_file_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _save_auth_session(payload: Dict[str, Any]) -> Path:
    path = _auth_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return path


def _clear_auth_session() -> None:
    path = _auth_file_path()
    if path.exists():
        path.unlink()


def _auth_request(method: str, path: str, *, base_url: Optional[str] = None, access_token: Optional[str] = None, json_body: Optional[Dict[str, Any]] = None, form_body: Optional[Dict[str, Any]] = None, timeout: int = 60) -> requests.Response:
    url = f"{_auth_base_url(base_url)}{path}"
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    response = requests.request(
        method.upper(),
        url,
        headers=headers,
        json=json_body,
        data=form_body,
        timeout=_http_timeout(timeout),
    )
    return response


def _refresh_auth_session(session: Dict[str, Any], base_url: Optional[str] = None) -> Dict[str, Any]:
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("No stored refresh token. Please run `nbs auth login` first.")
    response = _auth_request(
        "POST",
        "/api/auth/refresh",
        base_url=base_url or session.get("base_url"),
        json_body={"refresh_token": refresh_token},
    )
    payload = response.json()
    if response.status_code >= 400:
        raise RuntimeError(str(payload.get("detail") or payload))
    session.update(
        {
            "base_url": _auth_base_url(base_url or session.get("base_url")),
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "token_type": payload.get("token_type", "bearer"),
        }
    )
    _save_auth_session(session)
    return session


def _get_backend_session(force_direct: bool = False) -> Optional[Dict[str, Any]]:
    if force_direct or _env_flag("NBS_FORCE_DIRECT"):
        return None
    session = _load_auth_session()
    if not session.get("access_token") or not session.get("base_url"):
        return None
    return session


DIRECT_REASON_WARNINGS = {
    "missing_backend_session": "No backend session found; running in direct mode with local/API-key candidates.",
    "explicit_override": "Explicit --api-key/--base-url override detected; running in direct mode.",
    "env_force_direct": "NBS_FORCE_DIRECT is enabled; running in direct mode.",
    "backend_unavailable": "Backend session is configured but unavailable; falling back to direct mode.",
}


def _resolve_direct_reason(force_direct: bool) -> str:
    if _env_flag("NBS_FORCE_DIRECT"):
        return "env_force_direct"
    if force_direct:
        return "explicit_override"
    return "missing_backend_session"


def _build_direct_meta(
    force_direct: bool,
    *,
    reason_override: Optional[str] = None,
    backend_error: Optional[str] = None,
) -> Dict[str, str]:
    reason = reason_override or _resolve_direct_reason(force_direct)
    payload = {
        "direct_reason": reason,
        "direct_warning": DIRECT_REASON_WARNINGS[reason],
    }
    if backend_error:
        payload["backend_fallback_error"] = backend_error
    return payload


def _is_backend_fallback_worthy_error(exc: Exception) -> bool:
    if isinstance(exc, requests.RequestException):
        return True
    text = str(exc or "").strip().lower()
    if not text:
        return False
    markers = (
        "timed out",
        "timeout",
        "gateway timeout",
        "max retries exceeded",
        "failed to establish a new connection",
        "connection refused",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "bad gateway",
        "http 502",
        "http 503",
        "http 504",
    )
    return any(marker in text for marker in markers)


def _backend_url(session: Dict[str, Any], path_or_url: str) -> str:
    text = str(path_or_url or "").strip()
    if text.startswith(("http://", "https://")):
        return text
    return f"{_auth_base_url(session.get('base_url'))}{text if text.startswith('/') else '/' + text}"


def _backend_json_request(session: Dict[str, Any], method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None, timeout: int = 300) -> Dict[str, Any]:
    def _request(active_session: Dict[str, Any]) -> requests.Response:
        headers = {"Authorization": f"Bearer {active_session['access_token']}"}
        return requests.request(
            method.upper(),
            _backend_url(active_session, path),
            headers=headers,
            json=json_body,
            params=params,
            timeout=_http_timeout(timeout),
        )

    response = _request(session)
    if response.status_code == 401 and session.get("refresh_token"):
        session = _refresh_auth_session(session)
        response = _request(session)
    try:
        payload = response.json()
    except Exception:
        payload = {"detail": response.text}
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise RuntimeError(str(detail or f"Backend request failed: {response.status_code}"))
    return payload if isinstance(payload, dict) else {"data": payload}


def cmd_auth_login(args: argparse.Namespace) -> int:
    username = str(args.username or "").strip()
    if not username:
        username = input("Username: ").strip()
    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
    if not username or not password:
        return _fail("Username and password are required.", as_json=args.json)

    try:
        response = _auth_request(
            "POST",
            "/api/auth/login",
            base_url=args.base_url,
            form_body={"username": username, "password": password},
        )
        payload = response.json()
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)

    if response.status_code >= 400:
        return _fail(str(payload.get("detail") or payload), as_json=args.json)

    session = {
        "base_url": _auth_base_url(args.base_url),
        "username": username,
        "access_token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "token_type": payload.get("token_type", "bearer"),
    }
    _save_auth_session(session)
    result = {
        "success": True,
        "base_url": session["base_url"],
        "username": username,
        "auth_file": str(_auth_file_path()),
    }
    _print(result if args.json else f"Logged in as {username}", as_json=args.json)
    return 0


def cmd_auth_refresh(args: argparse.Namespace) -> int:
    session = _load_auth_session()
    try:
        session = _refresh_auth_session(session, base_url=args.base_url or session.get("base_url"))
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)
    result = {
        "success": True,
        "base_url": session["base_url"],
        "username": session.get("username"),
    }
    _print(result if args.json else "Token refreshed", as_json=args.json)
    return 0


def cmd_auth_whoami(args: argparse.Namespace) -> int:
    session = _load_auth_session()
    if not session.get("access_token"):
        return _fail("Not logged in. Please run `nbs auth login` first.", as_json=args.json)

    def _call_me(access_token: str):
        return _auth_request("GET", "/api/auth/me", base_url=args.base_url or session.get("base_url"), access_token=access_token)

    try:
        response = _call_me(session["access_token"])
        if response.status_code == 401 and session.get("refresh_token"):
            session = _refresh_auth_session(session, base_url=args.base_url or session.get("base_url"))
            response = _call_me(session["access_token"])
        payload = response.json()
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)

    if response.status_code >= 400:
        return _fail(str(payload.get("detail") or payload), as_json=args.json)
    payload = {"success": True, **payload}
    _print(payload if args.json else payload.get("username", ""), as_json=args.json)
    return 0


def cmd_auth_logout(args: argparse.Namespace) -> int:
    session = _load_auth_session()
    refresh_token = session.get("refresh_token")
    try:
        if refresh_token:
            _auth_request(
                "POST",
                "/api/auth/logout",
                base_url=args.base_url or session.get("base_url"),
                json_body={"refresh_token": refresh_token},
            )
    except Exception:
        pass
    _clear_auth_session()
    result = {"success": True}
    _print(result if args.json else "Logged out", as_json=args.json)
    return 0


def _batch_prompt_payload() -> Dict[str, Any]:
    return {
        "system_prompts": dict(batch_gen.system_prompts),
        "requirement_prompts": list(batch_gen.requirement_prompts),
        "generation_history": list(batch_gen.generation_history[-20:]),
    }


def _batch_history_payload(limit: int) -> list[Dict[str, Any]]:
    normalized_limit = max(1, int(limit or 10))
    return list(batch_gen.generation_history[-normalized_limit:])


def _parse_batch_combinations(combo_args: Optional[list[str]]) -> list[Dict[str, Any]]:
    combinations: list[Dict[str, Any]] = []
    for raw in combo_args or []:
        value = str(raw or "").strip()
        if not value or ":" not in value:
            raise ValueError(f"Invalid combo '{raw}'. Expected format system_key:requirement_index")
        system_key, index_text = value.split(":", 1)
        system_key = system_key.strip()
        if not system_key:
            raise ValueError(f"Invalid combo '{raw}'. Missing system_key")
        try:
            requirement_index = int(index_text.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid combo '{raw}'. requirement_index must be an integer") from exc
        combinations.append({"system_key": system_key, "requirement_index": requirement_index})
    return combinations


def _run_command_json(func: Any, params: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
    namespace = argparse.Namespace(**params, json=True)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = int(func(namespace) or 0)
    raw = buffer.getvalue().strip()
    if not raw:
        return code, {"success": code == 0}
    payload = json.loads(raw)
    if isinstance(payload, dict):
        return code, payload
    return code, {"success": code == 0, "data": payload}


def _load_json_tasks(path: str) -> list[Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("tasks"), list):
        return data["tasks"]
    raise ValueError("Task file must be a JSON array or an object with a 'tasks' array.")


def _normalize_queue_type(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"image", "audio", "video", "digital_human"}:
        return normalized
    return ""


def _infer_queue_type(raw: Any) -> str:
    if not isinstance(raw, dict):
        return "image"
    explicit = _normalize_queue_type(raw.get("type"))
    if explicit:
        return explicit
    if any(key in raw for key in ("digital_human", "avatarUrl", "avatar_url", "audio_model")):
        return "digital_human"
    if any(key in raw for key in ("video", "image_url", "imageUrl", "duration_seconds", "durationSeconds", "aspect_ratio", "aspectRatio", "mode", "resolution", "video_model", "videoModel")):
        return "video"
    if any(key in raw for key in ("audio", "voice", "language_type", "instructions")):
        return "audio"
    return "image"


def _merge_task_settings(raw: Any, key: str) -> Dict[str, Any]:
    if isinstance(raw, dict):
        node = raw.get(key)
        if isinstance(node, dict):
            return dict(node)
    return {}


def _normalize_queue_task(raw: Any, index: int) -> Dict[str, Any]:
    task_type = _infer_queue_type(raw)
    prompt = raw.strip() if isinstance(raw, str) else str((raw or {}).get("prompt") or (raw or {}).get("text") or "").strip()
    if not prompt:
        raise ValueError(f"Task #{index + 1} is missing prompt/text.")

    image = _merge_task_settings(raw, "image")
    audio = _merge_task_settings(raw, "audio")
    video = _merge_task_settings(raw, "video")
    digital_human = _merge_task_settings(raw, "digital_human")

    if isinstance(raw, dict):
        for src, dest in (
            ("subject", ("image", "subject")),
            ("model", ("image", "model")),
            ("size", ("image", "size")),
            ("quality", ("image", "quality")),
            ("style", ("image", "style")),
            ("optimize", ("image", "optimize")),
            ("voice", ("audio", "voice")),
            ("instructions", ("audio", "instructions")),
            ("language_type", ("audio", "language_type")),
            ("optimize_instructions", ("audio", "optimize_instructions")),
            ("audio_model", ("audio", "model")),
            ("mode", ("video", "mode")),
            ("video_model", ("video", "model")),
            ("image_url", ("video", "image_url")),
            ("imageUrl", ("video", "image_url")),
            ("aspect_ratio", ("video", "aspect_ratio")),
            ("aspectRatio", ("video", "aspect_ratio")),
            ("resolution", ("video", "resolution")),
            ("duration_seconds", ("video", "duration_seconds")),
            ("durationSeconds", ("video", "duration_seconds")),
            ("avatar_url", ("digital_human", "image_url")),
            ("avatarUrl", ("digital_human", "image_url")),
            ("provider", ("digital_human", "provider")),
            ("style", ("digital_human", "style")),
        ):
            if raw.get(src) is None:
                continue
            bucket_name, field = dest
            if bucket_name == "image":
                image[field] = raw[src]
            elif bucket_name == "audio":
                audio[field] = raw[src]
            elif bucket_name == "video":
                video[field] = raw[src]
            else:
                digital_human[field] = raw[src]

    return {
        "index": index,
        "type": task_type,
        "prompt": prompt,
        "image": image,
        "audio": audio,
        "video": video,
        "digital_human": digital_human,
    }


def _guess_extension_from_url(url: str, default_ext: str) -> str:
    parsed = str(url or "").split("#", 1)[0].split("?", 1)[0]
    ext = os.path.splitext(parsed)[1].lower()
    if ext:
        return ext
    guessed, _ = mimetypes.guess_type(parsed)
    if guessed:
        mime_ext = mimetypes.guess_extension(guessed)
        if mime_ext:
            return mime_ext
    return default_ext


def _download_remote_file(url: str, output_path: str, timeout: int = 300) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)
    return output_path


def _queue_output_path(base_dir: str, index: int, task_type: str, prompt: str, default_ext: str) -> str:
    safe_prompt = sanitize_filename(prompt) or task_type
    subdir = os.path.join(base_dir, task_type)
    os.makedirs(subdir, exist_ok=True)
    filename = f"{index + 1:03d}_{safe_prompt}{default_ext}"
    return os.path.join(subdir, filename)


def _local_path_to_static_url(path: str) -> Optional[str]:
    absolute = os.path.abspath(path)
    static_root = os.path.abspath(STATIC_DIR)
    if absolute == static_root or not absolute.startswith(f"{static_root}{os.sep}"):
        return None
    relative = os.path.relpath(absolute, static_root).replace(os.sep, "/")
    return f"/static/{relative}"


def _resolve_task_media_url(value: Optional[str]) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://", "oss://", "/static/", "static/")):
        return _resolve_public_media_url(text)
    candidate = Path(text).expanduser().resolve()
    if candidate.exists():
        static_url = _local_path_to_static_url(str(candidate))
        if static_url:
            return _resolve_public_media_url(static_url)
        return str(candidate)
    return text


def _queue_template_payload(template_type: str) -> list[Dict[str, Any]]:
    image_model = _get_default_model("image") or "z-image-turbo"
    audio_model = _get_default_model("audio") or "qwen-tts-latest"
    video_model = _get_default_model("video") or "sora-2"
    dh_model = _get_default_model("digital_human") or "wan2.2-s2v"

    templates = {
        "image": [
            {
                "type": "image",
                "prompt": "示例图片提示词：一位 AI 老师在智慧教室中讲课。",
                "image": {
                    "model": image_model,
                    "subject": "general",
                    "optimize": True,
                    "size": "1024x1024",
                    "quality": "standard",
                },
            }
        ],
        "audio": [
            {
                "type": "audio",
                "prompt": "示例音频文案：大家好，今天我们学习分数加减法。",
                "audio": {
                    "model": audio_model,
                    "voice": "Cherry",
                    "language_type": "Auto",
                },
            }
        ],
        "video": [
            {
                "type": "video",
                "prompt": "示例视频提示词：清晨校园航拍，阳光穿过树叶，慢速推镜。",
                "video": {
                    "mode": "text",
                    "model": video_model,
                    "aspect_ratio": "16:9",
                    "resolution": "720p",
                    "duration_seconds": 8,
                },
            }
        ],
        "digital_human": [
            {
                "type": "digital_human",
                "prompt": "示例数字人脚本：大家好，我是今天的讲解员，让我们开始吧。",
                "audio": {
                    "model": audio_model,
                    "voice": "Cherry",
                    "language_type": "Auto",
                },
                "digital_human": {
                    "model": dh_model,
                    "image_url": "https://example.com/avatar.png",
                    "resolution": 720,
                    "style": "speech",
                },
            }
        ],
    }
    if template_type == "mixed":
        return templates["image"] + templates["audio"] + templates["video"] + templates["digital_human"]
    return templates[template_type]


def cmd_models(args: argparse.Namespace) -> int:
    items = []
    for item in _get_model_catalog():
        if args.service and item.get("service") != args.service:
            continue
        items.append(
            {
                "service": item.get("service"),
                "model": item.get("model"),
                "label": item.get("label"),
                "platform": item.get("platform"),
                "enabled": item.get("enabled", True),
                "cost": item.get("cost"),
            }
        )
    _print(items, as_json=args.json)
    return 0


def cmd_prompt_optimize(args: argparse.Namespace) -> int:
    image_model = args.image_model or _get_default_model("image")
    prompt_model = args.model
    quiet = _should_quiet(args.json)
    force_direct = bool(args.api_key or args.base_url)
    backend_session = _get_backend_session(force_direct=force_direct)
    direct_meta = _build_direct_meta(force_direct) if not backend_session else {}
    if not backend_session and not prompt_model:
        prompt_model = _get_default_model("prompt")
    if not prompt_model and not backend_session:
        return _fail("No prompt model configured.", as_json=args.json)
    if backend_session:
        request_body = {
            "prompt": args.prompt,
            "subject": args.subject,
        }
        # Keep backend channel routing effective unless user explicitly pins a model.
        if prompt_model:
            request_body["model"] = prompt_model
        try:
            payload = _backend_json_request(
                backend_session,
                "POST",
                "/api/optimize_prompt",
                json_body=request_body,
            )
            optimized_prompt = payload.get("optimized_prompt") or args.prompt
            result = {
                "success": True,
                "prompt": args.prompt,
                "optimized_prompt": optimized_prompt,
                "prompt_model": payload.get("model") or prompt_model or _get_default_model("prompt"),
                "image_model": image_model,
                "optimized": bool(payload.get("optimized")),
                "fallback_to_original": bool(payload.get("fallback_to_original")),
                "errors": list(payload.get("errors") or []),
                "via": "backend",
            }
            _print(result if args.json else optimized_prompt, as_json=args.json)
            return 0
        except Exception as exc:
            return _fail(str(exc), as_json=args.json)
    try:
        candidates = _resolve_candidates("prompt", prompt_model, args.api_key, args.base_url)
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)

    optimized = None
    last_error = None
    for candidate in candidates:
        optimized = _invoke_core(
            img_gen.optimize_prompt,
            args.prompt,
            subject=args.subject,
            model=prompt_model,
            api_key=candidate.get("key"),
            base_url=candidate.get("base_url"),
            quiet=quiet,
        )
        if optimized:
            break
        last_error = getattr(img_gen, "last_error", None) or last_error

    if not optimized:
        detail = (last_error or {}).get("message") or "Prompt optimization returned empty result."
        return _fail(detail, as_json=args.json, extra=direct_meta if args.json else None)

    payload = {
        "success": True,
        "prompt": args.prompt,
        "optimized_prompt": optimized,
        "prompt_model": prompt_model,
        "image_model": image_model,
        "optimized": optimized != args.prompt,
        "fallback_to_original": optimized == args.prompt,
        "errors": [],
        "via": "direct",
        **direct_meta,
    }
    _print(payload if args.json else optimized, as_json=args.json)
    return 0


def cmd_image_generate(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("image")
    quiet = _should_quiet(args.json)
    force_direct = bool(args.api_key or args.base_url or args.prompt_api_key or args.prompt_base_url)
    backend_session = _get_backend_session(force_direct=force_direct)
    direct_meta = _build_direct_meta(force_direct) if not backend_session else {}
    if not model:
        return _fail("No image model configured.", as_json=args.json)

    prompt = args.prompt
    optimized_prompt = None
    optimize_error = None
    backend_fallback_error = None

    if backend_session:
        try:
            if args.optimize:
                prompt_model = args.prompt_model
                optimize_body = {
                    "prompt": args.prompt,
                    "subject": args.subject,
                }
                if prompt_model:
                    optimize_body["model"] = prompt_model
                try:
                    optimized_payload = _backend_json_request(
                        backend_session,
                        "POST",
                        "/api/optimize_prompt",
                        json_body=optimize_body,
                    )
                    optimized_prompt = optimized_payload.get("optimized_prompt")
                    if optimized_prompt:
                        prompt = optimized_prompt
                except Exception as exc:
                    optimize_error = str(exc)

            payload = _backend_json_request(
                backend_session,
                "POST",
                "/api/generate/single",
                json_body={
                    "prompt": prompt,
                    "size": args.size,
                    "quality": args.quality,
                    "style": args.style or "standard",
                    "subject": args.subject,
                    "model": model,
                },
            )
            image_urls = payload.get("urls") or ([payload.get("url")] if payload.get("url") else [])
            if not image_urls:
                return _fail("Backend image generation returned no url.", as_json=args.json)

            output_path = args.output or _default_output_path(GENERATED_DIR, "image", ".png", prompt)
            downloaded_paths: list[str] = []
            if len(image_urls) == 1:
                _download_remote_file(_backend_url(backend_session, image_urls[0]), output_path)
                downloaded_paths.append(output_path)
            else:
                base, ext = os.path.splitext(output_path)
                for idx, url in enumerate(image_urls, start=1):
                    target_path = f"{base}_{idx}{ext or '.png'}"
                    _download_remote_file(_backend_url(backend_session, url), target_path)
                    downloaded_paths.append(target_path)

            result = {
                "success": True,
                "model": payload.get("actual_model") or model,
                "requested_model": model,
                "prompt": prompt,
                "original_prompt": args.prompt,
                "optimized_prompt": optimized_prompt,
                "optimize_error": optimize_error,
                "image_url": image_urls[0],
                "image_urls": image_urls,
                "output_path": downloaded_paths[0],
                "output_paths": downloaded_paths,
                "attempted_models": payload.get("attempted_models"),
                "fallback_used": payload.get("fallback_used"),
                "via": "backend",
            }
            _write_json_sidecar(downloaded_paths[0], result)
            _print(result if args.json else downloaded_paths[0], as_json=args.json)
            return 0
        except Exception as exc:
            if not _is_backend_fallback_worthy_error(exc):
                return _fail(str(exc), as_json=args.json)
            backend_fallback_error = str(exc)
            direct_meta = _build_direct_meta(
                force_direct,
                reason_override="backend_unavailable",
                backend_error=backend_fallback_error,
            )

    if args.optimize and not optimized_prompt:
        prompt_model = args.prompt_model or _get_default_model("prompt")
        if not prompt_model:
            return _fail(
                "No prompt model configured for --optimize.",
                as_json=args.json,
                extra=direct_meta if args.json else None,
            )
        try:
            prompt_candidates = _resolve_candidates("prompt", prompt_model, args.prompt_api_key, args.prompt_base_url)
            last_error = None
            for prompt_candidate in prompt_candidates:
                optimized_prompt = _invoke_core(
                    img_gen.optimize_prompt,
                    args.prompt,
                    subject=args.subject,
                    model=prompt_model,
                    api_key=prompt_candidate.get("key"),
                    base_url=prompt_candidate.get("base_url"),
                    quiet=quiet,
                )
                if optimized_prompt:
                    break
                last_error = getattr(img_gen, "last_error", None) or last_error
            if optimized_prompt:
                prompt = optimized_prompt
            else:
                optimize_error = (last_error or {}).get("message") or "Prompt optimization returned empty result."
        except Exception as exc:
            optimize_error = str(exc)

    try:
        image_url = None
        last_error = None
        attempt_errors: list[str] = []
        actual_model = model
        attempted_models: list[str] = []
        fallback_used = False
        for attempt_model in _build_image_model_attempt_chain(model):
            attempted_models.append(attempt_model)
            try:
                candidates = _resolve_candidates("image", attempt_model, args.api_key, args.base_url)
            except Exception as exc:
                last_error = {"message": str(exc)}
                continue
            for candidate in candidates:
                generated_image_url = _invoke_core(
                    img_gen.generate_image,
                    prompt,
                    size=args.size,
                    quality=args.quality,
                    style=args.style,
                    api_key=candidate.get("key"),
                    base_url=candidate.get("base_url"),
                    model=attempt_model,
                    quiet=quiet,
                )
                if generated_image_url:
                    output_path = args.output or _default_output_path(GENERATED_DIR, "image", ".png", prompt)
                    if _invoke_core(img_gen.download_image, generated_image_url, output_path, quiet=quiet):
                        image_url = generated_image_url
                        actual_model = attempt_model
                        fallback_used = attempt_model != model
                        break
                    last_error = getattr(img_gen, "last_error", None) or {"message": "Image downloaded failed."}
                    detail = (last_error or {}).get("message") or "Image downloaded failed."
                    attempt_errors.append(f"{attempt_model}: {detail}")
                    continue
                last_error = getattr(img_gen, "last_error", None) or last_error
                detail = (last_error or {}).get("message")
                if detail:
                    attempt_errors.append(f"{attempt_model}: {detail}")
            if image_url:
                break

        output_path = args.output or _default_output_path(GENERATED_DIR, "image", ".png", prompt)
        local_fallback = False
        if not image_url:
            if not _invoke_core(img_gen.create_local_fallback_image, prompt, output_path, size=args.size, quiet=quiet):
                detail = (last_error or {}).get("message") or "Image generation returned empty result."
                return _fail(detail, as_json=args.json, extra=direct_meta if args.json else None)
            actual_model = "local-fallback-image"
            fallback_used = True
            local_fallback = True

        result = {
            "success": True,
            "model": actual_model,
            "requested_model": model,
            "prompt": prompt,
            "original_prompt": args.prompt,
            "optimized_prompt": optimized_prompt,
            "optimize_error": optimize_error,
            "image_url": image_url,
            "output_path": output_path,
            "attempted_models": attempted_models,
            "attempt_errors": attempt_errors[-8:],
            "fallback_used": fallback_used,
            "local_fallback": local_fallback,
            "via": "direct",
            **direct_meta,
        }
        _write_json_sidecar(output_path, result)
        _print(result if args.json else output_path, as_json=args.json)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=args.json, extra=direct_meta if args.json else None)


def cmd_image_edit(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("image")
    quiet = _should_quiet(args.json)
    if not model:
        return _fail("No image model configured.", as_json=args.json)
    if not args.image:
        return _fail("--image is required.", as_json=args.json)

    image_paths = [str(Path(p).expanduser().resolve()) for p in args.image]
    try:
        candidates = _resolve_candidates("image", model, args.api_key, args.base_url)
        image_url = None
        last_error = None
        attempt_errors: list[str] = []
        output_path = args.output or _default_output_path(GENERATED_DIR, "edited", ".png", args.prompt)
        for candidate in candidates:
            generated_image_url = _invoke_core(
                img_gen.generate_modified_image,
                args.prompt,
                image_paths,
                api_key=candidate.get("key"),
                base_url=candidate.get("base_url"),
                model=model,
                quiet=quiet,
            )
            if generated_image_url:
                if _invoke_core(img_gen.download_image, generated_image_url, output_path, quiet=quiet):
                    image_url = generated_image_url
                    break
                last_error = getattr(img_gen, "last_error", None) or {"message": "Image downloaded failed."}
                detail = (last_error or {}).get("message") or "Image downloaded failed."
                attempt_errors.append(detail)
                continue
            last_error = getattr(img_gen, "last_error", None) or last_error
            detail = (last_error or {}).get("message")
            if detail:
                attempt_errors.append(detail)
        if not image_url:
            detail = (last_error or {}).get("message") or "Image edit returned empty result."
            return _fail(detail, as_json=args.json)
        result = {
            "success": True,
            "model": model,
            "prompt": args.prompt,
            "input_images": image_paths,
            "image_url": image_url,
            "output_path": output_path,
            "attempt_errors": attempt_errors[-8:],
            "via": "direct",
        }
        _write_json_sidecar(output_path, result)
        _print(result if args.json else output_path, as_json=args.json)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)


def cmd_audio_tts(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("audio")
    quiet = _should_quiet(args.json)
    backend_session = _get_backend_session(force_direct=bool(args.api_key or args.base_url))
    if not model:
        return _fail("No audio model configured.", as_json=args.json)
    if backend_session:
        try:
            payload = _backend_json_request(
                backend_session,
                "POST",
                "/api/audio/tts",
                json_body={
                    "text": args.text,
                    "voice": args.voice,
                    "model": model,
                    "language_type": args.language_type,
                    "instructions": args.instructions,
                    "optimize_instructions": not args.no_optimize_instructions,
                },
            )
            relative_url = payload.get("url")
            if not relative_url:
                return _fail("Backend TTS returned no url.", as_json=args.json)
            output_path = args.output or _default_output_path(AUDIO_DIR, "tts", ".wav", args.text)
            _download_remote_file(_backend_url(backend_session, relative_url), output_path)
            result = {
                "success": True,
                "model": model,
                "voice": args.voice,
                "output_path": output_path,
                "mime_type": payload.get("type") or "audio/wav",
                "source_url": relative_url,
                "via": "backend",
            }
            _print(result if args.json else output_path, as_json=args.json)
            return 0
        except Exception as exc:
            return _fail(str(exc), as_json=args.json)
    try:
        output_path = args.output or _default_output_path(AUDIO_DIR, "tts", ".wav", args.text)
        output_dir = os.path.dirname(output_path)
        filename_base = os.path.splitext(os.path.basename(output_path))[0]
        candidates = _resolve_candidates("audio", model, args.api_key, args.base_url)
        last_error = None
        wav_path = None
        mime_type = None
        for candidate in candidates:
            try:
                wav_path, mime_type = _invoke_core(
                    synthesize_tts,
                    text=args.text,
                    output_dir=output_dir,
                    filename_base=filename_base,
                    voice=args.voice,
                    model=model,
                    instructions=args.instructions,
                    optimize_instructions=not args.no_optimize_instructions,
                    api_key=candidate.get("key"),
                    base_url=candidate.get("base_url"),
                    language_type=args.language_type,
                    quiet=quiet,
                )
                break
            except Exception as exc:
                last_error = exc
        if not wav_path:
            raise RuntimeError(str(last_error) if last_error else "TTS failed")
        result = {
            "success": True,
            "model": model,
            "voice": args.voice,
            "output_path": wav_path,
            "mime_type": mime_type,
            "via": "direct",
        }
        _print(result if args.json else wav_path, as_json=args.json)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)


def _extract_task_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("task_id", "taskId", "id", "name", "operation", "operation_name", "operationName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _poll_video(task_id: str, model: str, api_key: Optional[str], base_url: Optional[str], timeout_seconds: int, interval_seconds: int) -> Dict[str, Any]:
    started = time.time()
    while True:
        result = video_gen.get_task_result(task_id, api_key=api_key, base_url=base_url, model=model)
        error = video_gen.extract_error(result)
        video_url = video_gen.extract_video_url(result)
        if video_url:
            return {"status": "done", "task_id": task_id, "video_url": video_url, "raw": result}
        if error:
            return {"status": "failed", "task_id": task_id, "error": error, "raw": result}
        if time.time() - started >= timeout_seconds:
            return {"status": "timeout", "task_id": task_id, "raw": result}
        time.sleep(interval_seconds)


def _poll_backend_video(session: Dict[str, Any], task_id: str, timeout_seconds: int, interval_seconds: int) -> Dict[str, Any]:
    started = time.time()
    while True:
        payload = _backend_json_request(session, "GET", "/api/video/status", params={"task_id": task_id}, timeout=max(120, interval_seconds + 60))
        status_data = payload.get("data") or {}
        status = status_data.get("status")
        if status == "done" and status_data.get("video_url"):
            return {"status": "done", "task_id": task_id, "video_url": status_data.get("video_url"), "raw": payload.get("raw")}
        if status in ("failed", "expired"):
            return {"status": status, "task_id": task_id, "error": status, "raw": payload.get("raw")}
        if time.time() - started >= timeout_seconds:
            return {"status": "timeout", "task_id": task_id, "raw": payload.get("raw")}
        time.sleep(interval_seconds)


def cmd_video_submit(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("video")
    backend_session = _get_backend_session(force_direct=bool(args.api_key or args.base_url))
    if not model:
        return _fail("No video model configured.", as_json=args.json)
    if backend_session:
        try:
            payload = _backend_json_request(
                backend_session,
                "POST",
                "/api/video/generate",
                json_body={
                    "mode": "image" if args.image_url or args.image_urls else "text",
                    "prompt": args.prompt,
                    "model": model,
                    "aspect_ratio": args.aspect_ratio,
                    "resolution": args.resolution,
                    "duration_seconds": args.duration,
                    "image_url": args.image_url,
                    "images": args.image_urls,
                },
            )
            task_id = (((payload.get("data") or {}) if isinstance(payload.get("data"), dict) else {}).get("task_id"))
            if not task_id:
                return _fail("Backend video submit returned no task id.", as_json=args.json)
            result = {
                "success": True,
                "model": model,
                "task_id": task_id,
                "raw": payload.get("raw"),
                "via": "backend",
            }
            if args.wait:
                polled = _poll_backend_video(backend_session, task_id, args.timeout, args.interval)
                if polled.get("status") != "done":
                    return _fail(polled.get("error") or polled.get("status") or "Video generation failed.", as_json=args.json, extra=polled if args.json else None)
                result.update(polled)
            _print(result, as_json=True if args.json or args.wait else False)
            if not args.json and not args.wait:
                print(task_id)
            return 0
        except Exception as exc:
            return _fail(str(exc), as_json=args.json)
    try:
        candidates = _resolve_candidates("video", model, args.api_key, args.base_url)
        result = None
        error = None
        chosen = None
        for candidate in candidates:
            chosen = candidate
            result = video_gen.submit_task(
                prompt=args.prompt,
                model=model,
                image_url=args.image_url,
                image_urls=args.image_urls,
                aspect_ratio=args.aspect_ratio,
                resolution=args.resolution,
                duration_seconds=args.duration,
                api_key=candidate.get("key"),
                base_url=candidate.get("base_url"),
                platform=args.platform,
            )
            error = video_gen.extract_error(result)
            if not error:
                break
        error = video_gen.extract_error(result)
        if error:
            return _fail(error, as_json=args.json, extra={"raw": result} if args.json else None)
        task_id = _extract_task_id(result)
        if not task_id:
            return _fail("Video submit succeeded but no task id was returned.", as_json=args.json, extra={"raw": result} if args.json else None)

        payload = {
            "success": True,
            "model": model,
            "task_id": task_id,
            "raw": result,
            "via": "direct",
        }
        if args.wait:
            polled = _poll_video(task_id, model, chosen.get("key"), chosen.get("base_url"), args.timeout, args.interval)
            if polled.get("status") != "done":
                return _fail(polled.get("error") or polled.get("status") or "Video generation failed.", as_json=args.json, extra=polled if args.json else None)
            payload.update(polled)
        _print(payload, as_json=True if args.json or args.wait else False)
        if not args.json and not args.wait:
            print(task_id)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)


def cmd_video_status(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("video")
    backend_session = _get_backend_session(force_direct=bool(args.api_key or args.base_url))
    if not model:
        return _fail("No video model configured.", as_json=args.json)
    if backend_session:
        try:
            payload = _backend_json_request(
                backend_session,
                "GET",
                "/api/video/status",
                params={"task_id": args.task_id},
            )
            status_data = payload.get("data") or {}
            result = {
                "success": True,
                "task_id": args.task_id,
                "model": model,
                "video_url": status_data.get("video_url"),
                "status": status_data.get("status"),
                "raw": payload.get("raw"),
                "via": "backend",
            }
            _print(result, as_json=True)
            return 0
        except Exception as exc:
            return _fail(str(exc), as_json=True)
    try:
        candidates = _resolve_candidates("video", model, args.api_key, args.base_url)
        result = None
        for candidate in candidates:
            result = video_gen.get_task_result(args.task_id, api_key=candidate.get("key"), base_url=candidate.get("base_url"), model=model)
            if video_gen.extract_video_url(result) or not video_gen.extract_error(result):
                break
        payload = {
            "success": True,
            "task_id": args.task_id,
            "model": model,
            "video_url": video_gen.extract_video_url(result),
            "error": video_gen.extract_error(result),
            "raw": result,
            "via": "direct",
        }
        _print(payload, as_json=True)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=True)


def _poll_digital_human(task_id: str, model: str, api_key: Optional[str], base_url: Optional[str], timeout_seconds: int, interval_seconds: int) -> Dict[str, Any]:
    started = time.time()
    while True:
        result = digital_human_gen.get_task_result(task_id, api_key=api_key, base_url=base_url, model=model)
        error = digital_human_gen.extract_error(result)
        normalized = digital_human_gen.normalize_status_response(result)
        if normalized.get("status") == "done" and normalized.get("video_url"):
            return {"status": "done", "task_id": task_id, "video_url": normalized.get("video_url"), "raw": result}
        if error or normalized.get("status") in ("failed", "expired"):
            return {
                "status": normalized.get("status") or "failed",
                "task_id": task_id,
                "error": normalized.get("error_message") or error,
                "raw": result,
            }
        if time.time() - started >= timeout_seconds:
            return {"status": "timeout", "task_id": task_id, "raw": result}
        time.sleep(interval_seconds)


def _poll_backend_digital_human(session: Dict[str, Any], task_id: str, model: str, timeout_seconds: int, interval_seconds: int) -> Dict[str, Any]:
    started = time.time()
    while True:
        payload = _backend_json_request(
            session,
            "GET",
            f"/api/digital_human/status/{task_id}",
            params={"model": model},
            timeout=max(120, interval_seconds + 60),
        )
        status_data = payload.get("data") or {}
        status = status_data.get("status")
        if status == "done" and status_data.get("video_url"):
            return {"status": "done", "task_id": task_id, "video_url": status_data.get("video_url"), "raw": payload.get("raw")}
        if status in ("failed", "expired"):
            return {
                "status": status,
                "task_id": task_id,
                "error": status_data.get("error_message") or status,
                "raw": payload.get("raw"),
            }
        if time.time() - started >= timeout_seconds:
            return {"status": "timeout", "task_id": task_id, "raw": payload.get("raw")}
        time.sleep(interval_seconds)


def cmd_dh_submit(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("digital_human")
    backend_session = _get_backend_session(force_direct=bool(args.api_key or args.base_url))
    if not model:
        return _fail("No digital human model configured.", as_json=args.json)
    if backend_session:
        try:
            payload = _backend_json_request(
                backend_session,
                "POST",
                "/api/digital_human/submit",
                json_body={
                    "image_url": args.image_url,
                    "audio_url": args.audio_url,
                    "prompt": args.prompt,
                    "model": model,
                    "resolution": args.resolution,
                    "style": args.style,
                },
            )
            task_data = payload.get("data") or {}
            task_id = task_data.get("task_id")
            if not task_id:
                return _fail("Backend digital human submit returned no task id.", as_json=args.json)
            result = {
                "success": True,
                "model": model,
                "task_id": task_id,
                "raw": payload.get("raw"),
                "via": "backend",
            }
            if args.wait:
                polled = _poll_backend_digital_human(backend_session, task_id, model, args.timeout, args.interval)
                if polled.get("status") != "done":
                    return _fail(polled.get("error") or polled.get("status") or "Digital human generation failed.", as_json=args.json, extra=polled if args.json else None)
                result.update(polled)
            _print(result, as_json=True if args.json or args.wait else False)
            if not args.json and not args.wait:
                print(task_id)
            return 0
        except Exception as exc:
            return _fail(str(exc), as_json=args.json)
    try:
        candidates = _resolve_candidates("digital_human", model, args.api_key, args.base_url)
        result = None
        error = None
        chosen = None
        for candidate in candidates:
            chosen = candidate
            result = digital_human_gen.submit_task(
                image_url=args.image_url,
                audio_url=args.audio_url,
                prompt=args.prompt,
                resolution=args.resolution,
                style=args.style,
                api_key=candidate.get("key"),
                base_url=candidate.get("base_url"),
                model=model,
            )
            error = digital_human_gen.extract_error(result)
            if not error:
                break
        error = digital_human_gen.extract_error(result)
        if error:
            return _fail(error, as_json=args.json, extra={"raw": result} if args.json else None)
        normalized = digital_human_gen.normalize_submit_response(result)
        task_id = normalized.get("task_id")
        if not task_id:
            return _fail("Digital human submit succeeded but no task id was returned.", as_json=args.json, extra={"raw": result} if args.json else None)
        payload = {
            "success": True,
            "model": model,
            "task_id": task_id,
            "raw": result,
            "via": "direct",
        }
        if args.wait:
            polled = _poll_digital_human(task_id, model, chosen.get("key"), chosen.get("base_url"), args.timeout, args.interval)
            if polled.get("status") != "done":
                return _fail(polled.get("error") or polled.get("status") or "Digital human generation failed.", as_json=args.json, extra=polled if args.json else None)
            payload.update(polled)
        _print(payload, as_json=True if args.json or args.wait else False)
        if not args.json and not args.wait:
            print(task_id)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)


def cmd_dh_status(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("digital_human")
    backend_session = _get_backend_session(force_direct=bool(args.api_key or args.base_url))
    if not model:
        return _fail("No digital human model configured.", as_json=args.json)
    if backend_session:
        try:
            payload = _backend_json_request(
                backend_session,
                "GET",
                f"/api/digital_human/status/{args.task_id}",
                params={"model": model},
            )
            status_data = payload.get("data") or {}
            result = {
                "success": True,
                "task_id": args.task_id,
                "model": model,
                "status": status_data.get("status"),
                "video_url": status_data.get("video_url"),
                "error": status_data.get("error_message"),
                "raw": payload.get("raw"),
                "via": "backend",
            }
            _print(result, as_json=True)
            return 0
        except Exception as exc:
            return _fail(str(exc), as_json=True)
    try:
        candidates = _resolve_candidates("digital_human", model, args.api_key, args.base_url)
        result = None
        normalized = {}
        for candidate in candidates:
            result = digital_human_gen.get_task_result(args.task_id, api_key=candidate.get("key"), base_url=candidate.get("base_url"), model=model)
            normalized = digital_human_gen.normalize_status_response(result)
            if normalized.get("video_url") or normalized.get("status") in ("done", "processing", "in_queue"):
                break
        payload = {
            "success": True,
            "task_id": args.task_id,
            "model": model,
            "status": normalized.get("status"),
            "video_url": normalized.get("video_url"),
            "error": normalized.get("error_message") or digital_human_gen.extract_error(result),
            "raw": result,
            "via": "direct",
        }
        _print(payload, as_json=True)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=True)


def cmd_batch_prompts(args: argparse.Namespace) -> int:
    payload = {
        "success": True,
        **_batch_prompt_payload(),
    }
    _print(payload if args.json else payload, as_json=args.json)
    return 0


def cmd_batch_history(args: argparse.Namespace) -> int:
    items = _batch_history_payload(args.limit)
    payload = {
        "success": True,
        "items": items,
        "count": len(items),
    }
    _print(payload if args.json else payload, as_json=args.json)
    return 0


def cmd_batch_add_system(args: argparse.Namespace) -> int:
    batch_gen.add_system_prompt(args.key, args.prompt)
    payload = {
        "success": True,
        "key": args.key,
        "prompt": args.prompt,
        "system_prompts": dict(batch_gen.system_prompts),
    }
    _print(payload if args.json else payload, as_json=args.json)
    return 0


def cmd_batch_remove_system(args: argparse.Namespace) -> int:
    existed = args.key in batch_gen.system_prompts
    batch_gen.remove_system_prompt(args.key)
    if not existed:
        return _fail(f"System prompt not found: {args.key}", as_json=args.json)
    payload = {
        "success": True,
        "key": args.key,
        "system_prompts": dict(batch_gen.system_prompts),
    }
    _print(payload if args.json else payload, as_json=args.json)
    return 0


def cmd_batch_add_requirement(args: argparse.Namespace) -> int:
    batch_gen.add_requirement_prompt(args.prompt)
    payload = {
        "success": True,
        "index": len(batch_gen.requirement_prompts) - 1,
        "prompt": args.prompt,
        "requirement_prompts": list(batch_gen.requirement_prompts),
    }
    _print(payload if args.json else payload, as_json=args.json)
    return 0


def cmd_batch_remove_requirement(args: argparse.Namespace) -> int:
    if args.index < 0 or args.index >= len(batch_gen.requirement_prompts):
        return _fail(f"Requirement prompt index out of range: {args.index}", as_json=args.json)
    removed_prompt = batch_gen.requirement_prompts[args.index]
    batch_gen.remove_requirement_prompt(args.index)
    payload = {
        "success": True,
        "index": args.index,
        "prompt": removed_prompt,
        "requirement_prompts": list(batch_gen.requirement_prompts),
    }
    _print(payload if args.json else payload, as_json=args.json)
    return 0


def cmd_batch_generate(args: argparse.Namespace) -> int:
    model = args.model or _get_default_model("image")
    quiet = _should_quiet(args.json)
    backend_session = _get_backend_session(force_direct=bool(args.api_key or args.base_url))
    if not model:
        return _fail("No image model configured.", as_json=args.json)
    try:
        custom_combinations = _parse_batch_combinations(args.combo)
    except ValueError as exc:
        return _fail(str(exc), as_json=args.json)

    system_key = None
    requirement_indices = None
    if custom_combinations:
        task_count = len(custom_combinations)
    else:
        system_keys = [item for item in (args.system_key or []) if item in batch_gen.system_prompts]
        requirement_indices = args.requirement_index or None
        system_key = system_keys[0] if len(system_keys) == 1 else None
        if args.system_key and not system_keys:
            return _fail("No valid batch system keys were provided.", as_json=args.json)
        if len(system_keys) > 1:
            custom_combinations = []
            selected_requirement_indices = requirement_indices or list(range(len(batch_gen.requirement_prompts)))
            for selected_key in system_keys:
                for req_index in selected_requirement_indices:
                    custom_combinations.append({"system_key": selected_key, "requirement_index": req_index})
            task_count = len(custom_combinations)
        else:
            selected_requirement_indices = requirement_indices or list(range(len(batch_gen.requirement_prompts)))
            selected_system_keys = [system_key] if system_key else list(batch_gen.system_prompts.keys())
            task_count = len(selected_system_keys) * len(selected_requirement_indices)

    if task_count <= 0:
        return _fail("No batch tasks selected.", as_json=args.json)

    output_dir = args.output_dir or BATCH_DIR
    os.makedirs(output_dir, exist_ok=True)

    if backend_session and (custom_combinations or len(args.system_key or []) <= 1):
        try:
            backend_system_keys = args.system_key or ([item["system_key"] for item in custom_combinations] if custom_combinations else [])
            backend_requirement_indices = args.requirement_index or ([item["requirement_index"] for item in custom_combinations] if custom_combinations else [])
            payload = _backend_json_request(
                backend_session,
                "POST",
                "/api/generate/batch",
                json_body={
                    "system_keys": backend_system_keys,
                    "requirement_indices": backend_requirement_indices,
                    "model": model,
                    "optimize": args.optimize,
                },
                timeout=max(300, len(backend_requirement_indices or [0]) * 120),
            )
            items = payload.get("items") or []
            downloaded = {}
            for idx, item in enumerate(items, start=1):
                url = item.get("url")
                if not url:
                    continue
                filename = os.path.basename(str(url).split("?", 1)[0]) or f"batch_{idx}.png"
                local_path = os.path.join(output_dir, filename)
                _download_remote_file(_backend_url(backend_session, url), local_path)
                downloaded[item.get("id") or filename] = local_path
                item["file_path"] = local_path
            result = {
                "success": bool(payload.get("success", True)),
                "model": model,
                "task_count": task_count,
                "output_dir": output_dir,
                "system_keys": args.system_key or [],
                "requirement_indices": args.requirement_index or [],
                "custom_combinations": custom_combinations,
                "total_tasks": payload.get("total_tasks", 0),
                "successful": payload.get("successful", 0),
                "failed": payload.get("failed", 0),
                "files": downloaded,
                "items": items,
                "errors": payload.get("errors", []),
                "via": "backend",
            }
            if result["successful"] <= 0:
                return _fail("Batch generation failed.", as_json=args.json, extra=result if args.json else None)
            _print(result if args.json else result, as_json=args.json)
            return 0
        except Exception:
            pass

    try:
        candidates = _resolve_candidates("image", model, args.api_key, args.base_url)
        results = None
        last_errors: list[str] = []
        for candidate in candidates:
            results = _invoke_core(
                batch_gen.generate_batch,
                system_key=system_key,
                requirement_indices=requirement_indices,
                custom_combinations=custom_combinations or None,
                model=model,
                base_url=candidate.get("base_url"),
                api_key=candidate.get("key"),
                optimize=args.optimize,
                output_dir=output_dir,
                max_workers=args.max_workers,
                delay_seconds=args.delay_seconds,
                quiet=quiet,
            )
            if results and results.get("successful", 0) > 0:
                break
            if results and results.get("errors"):
                last_errors.extend([str(item) for item in results.get("errors", []) if item])

        if not isinstance(results, dict):
            return _fail("Batch generation returned no result.", as_json=args.json)

        payload = {
            "success": bool(results.get("success", False)),
            "model": model,
            "task_count": task_count,
            "output_dir": output_dir,
            "system_keys": args.system_key or ([] if custom_combinations else ([system_key] if system_key else list(batch_gen.system_prompts.keys()))),
            "requirement_indices": args.requirement_index or ([] if custom_combinations else list(range(len(batch_gen.requirement_prompts)))),
            "custom_combinations": custom_combinations,
            "total_tasks": results.get("total_tasks", 0),
            "successful": results.get("successful", 0),
            "failed": results.get("failed", 0),
            "files": results.get("files", {}),
            "items": results.get("items", []),
            "errors": results.get("errors", []) or last_errors,
            "via": "direct",
        }
        if payload["successful"] <= 0:
            return _fail("Batch generation failed.", as_json=args.json, extra=payload if args.json else None)
        _print(payload if args.json else payload, as_json=args.json)
        return 0
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)


def cmd_queue_template(args: argparse.Namespace) -> int:
    payload = _queue_template_payload(args.type)
    if args.output:
        output_path = str(Path(args.output).expanduser().resolve())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        result = {"success": True, "output_path": output_path, "type": args.type, "tasks": payload}
        _print(result if args.json else output_path, as_json=args.json)
        return 0
    _print({"success": True, "type": args.type, "tasks": payload} if args.json else payload, as_json=args.json)
    return 0


def cmd_queue_run(args: argparse.Namespace) -> int:
    try:
        raw_tasks = _load_json_tasks(args.file)
    except Exception as exc:
        return _fail(str(exc), as_json=args.json)

    output_dir = str(Path(args.output_dir or os.path.join(STATIC_DIR, "queue")).expanduser().resolve())
    os.makedirs(output_dir, exist_ok=True)

    tasks: list[Dict[str, Any]] = []
    for index, raw in enumerate(raw_tasks):
        try:
            tasks.append(_normalize_queue_task(raw, index))
        except Exception as exc:
            if not args.continue_on_error:
                return _fail(str(exc), as_json=args.json)
            tasks.append(
                {
                    "index": index,
                    "type": "unknown",
                    "prompt": "",
                    "error": str(exc),
                    "success": False,
                }
            )

    results: list[Dict[str, Any]] = []
    for task in tasks:
        if task.get("type") == "unknown":
            results.append(task)
            continue

        task_type = task["type"]
        prompt = task["prompt"]
        index = task["index"]
        try:
            if task_type == "image":
                output_path = _queue_output_path(output_dir, index, "image", prompt, ".png")
                code, payload = _run_command_json(
                    cmd_image_generate,
                    {
                        "prompt": prompt,
                        "model": task["image"].get("model"),
                        "subject": task["image"].get("subject", "general"),
                        "size": task["image"].get("size", "1024x1024"),
                        "quality": task["image"].get("quality", "standard"),
                        "style": task["image"].get("style"),
                        "optimize": bool(task["image"].get("optimize")),
                        "prompt_model": task["image"].get("prompt_model"),
                        "api_key": task["image"].get("api_key"),
                        "base_url": task["image"].get("base_url"),
                        "prompt_api_key": task["image"].get("prompt_api_key"),
                        "prompt_base_url": task["image"].get("prompt_base_url"),
                        "output": output_path,
                    },
                )
                payload.update({"task_index": index, "type": task_type})
                if code != 0 and not args.continue_on_error:
                    return _fail(payload.get("error") or "Queue image task failed.", as_json=args.json, extra=payload if args.json else None)
                results.append(payload)
                continue

            if task_type == "audio":
                output_path = _queue_output_path(output_dir, index, "audio", prompt, ".wav")
                code, payload = _run_command_json(
                    cmd_audio_tts,
                    {
                        "text": prompt,
                        "model": task["audio"].get("model"),
                        "voice": task["audio"].get("voice", "Cherry"),
                        "instructions": task["audio"].get("instructions"),
                        "language_type": task["audio"].get("language_type", "Auto"),
                        "no_optimize_instructions": not bool(task["audio"].get("optimize_instructions", True)),
                        "api_key": task["audio"].get("api_key"),
                        "base_url": task["audio"].get("base_url"),
                        "output": output_path,
                    },
                )
                payload.update({"task_index": index, "type": task_type, "prompt": prompt})
                if code != 0 and not args.continue_on_error:
                    return _fail(payload.get("error") or "Queue audio task failed.", as_json=args.json, extra=payload if args.json else None)
                results.append(payload)
                continue

            if task_type == "video":
                mode = str(task["video"].get("mode") or "text").strip().lower()
                image_url = _resolve_task_media_url(task["video"].get("image_url") or task["video"].get("imageUrl"))
                code, payload = _run_command_json(
                    cmd_video_submit,
                    {
                        "prompt": prompt,
                        "model": task["video"].get("model"),
                        "platform": task["video"].get("platform"),
                        "image_url": image_url if mode == "image" or image_url else None,
                        "image_urls": None,
                        "aspect_ratio": task["video"].get("aspect_ratio") or task["video"].get("aspectRatio") or "16:9",
                        "resolution": task["video"].get("resolution"),
                        "duration": task["video"].get("duration_seconds") or task["video"].get("durationSeconds"),
                        "api_key": task["video"].get("api_key"),
                        "base_url": task["video"].get("base_url"),
                        "wait": True,
                        "timeout": int(task["video"].get("timeout") or args.video_timeout),
                        "interval": int(task["video"].get("interval") or args.video_interval),
                    },
                )
                payload.update({"task_index": index, "type": task_type, "prompt": prompt, "mode": mode})
                if payload.get("success") and payload.get("video_url"):
                    ext = _guess_extension_from_url(payload["video_url"], ".mp4")
                    download_path = _queue_output_path(output_dir, index, "video", prompt, ext)
                    payload["output_path"] = _download_remote_file(payload["video_url"], download_path)
                if code != 0 and not args.continue_on_error:
                    return _fail(payload.get("error") or "Queue video task failed.", as_json=args.json, extra=payload if args.json else None)
                results.append(payload)
                continue

            if task_type == "digital_human":
                avatar_url = _resolve_task_media_url(
                    task["digital_human"].get("image_url")
                    or task["digital_human"].get("avatar_url")
                    or task["digital_human"].get("avatarUrl")
                )
                if not avatar_url:
                    raise RuntimeError(f"Task #{index + 1} missing digital_human.image_url")

                audio_output = _queue_output_path(output_dir, index, "audio", f"{prompt}_audio", ".wav")
                audio_code, audio_payload = _run_command_json(
                    cmd_audio_tts,
                    {
                        "text": prompt,
                        "model": task["audio"].get("model"),
                        "voice": task["audio"].get("voice", "Cherry"),
                        "instructions": task["audio"].get("instructions"),
                        "language_type": task["audio"].get("language_type", "Auto"),
                        "no_optimize_instructions": not bool(task["audio"].get("optimize_instructions", True)),
                        "api_key": task["audio"].get("api_key"),
                        "base_url": task["audio"].get("base_url"),
                        "output": audio_output,
                    },
                )
                if audio_code != 0:
                    audio_payload.update({"task_index": index, "type": task_type, "stage": "audio"})
                    if not args.continue_on_error:
                        return _fail(audio_payload.get("error") or "Queue digital human audio stage failed.", as_json=args.json, extra=audio_payload if args.json else None)
                    results.append(audio_payload)
                    continue

                audio_url = _resolve_task_media_url(task["digital_human"].get("audio_url"))
                if not audio_url and audio_payload.get("output_path"):
                    audio_url = _resolve_task_media_url(audio_payload.get("output_path"))
                if not audio_url:
                    raise RuntimeError(f"Task #{index + 1} digital human audio stage returned no output path.")

                code, payload = _run_command_json(
                    cmd_dh_submit,
                    {
                        "image_url": avatar_url,
                        "audio_url": audio_url,
                        "prompt": task["digital_human"].get("prompt") or prompt,
                        "model": task["digital_human"].get("model"),
                        "resolution": int(task["digital_human"].get("resolution") or 720),
                        "style": task["digital_human"].get("style"),
                        "api_key": task["digital_human"].get("api_key"),
                        "base_url": task["digital_human"].get("base_url"),
                        "wait": True,
                        "timeout": int(task["digital_human"].get("timeout") or args.video_timeout),
                        "interval": int(task["digital_human"].get("interval") or args.digital_human_interval),
                    },
                )
                payload.update(
                    {
                        "task_index": index,
                        "type": task_type,
                        "prompt": prompt,
                        "audio_output_path": audio_payload.get("output_path"),
                    }
                )
                if payload.get("success") and payload.get("video_url"):
                    ext = _guess_extension_from_url(payload["video_url"], ".mp4")
                    download_path = _queue_output_path(output_dir, index, "digital_human", prompt, ext)
                    payload["output_path"] = _download_remote_file(payload["video_url"], download_path)
                if code != 0 and not args.continue_on_error:
                    return _fail(payload.get("error") or "Queue digital human task failed.", as_json=args.json, extra=payload if args.json else None)
                results.append(payload)
                continue

            raise RuntimeError(f"Unsupported task type: {task_type}")
        except Exception as exc:
            payload = {
                "success": False,
                "task_index": index,
                "type": task_type,
                "prompt": prompt,
                "error": str(exc),
            }
            if not args.continue_on_error:
                return _fail(str(exc), as_json=args.json, extra=payload if args.json else None)
            results.append(payload)

    summary = {
        "success": all(bool(item.get("success")) for item in results) if results else True,
        "input_file": str(Path(args.file).expanduser().resolve()),
        "output_dir": output_dir,
        "total_tasks": len(results),
        "successful": sum(1 for item in results if item.get("success")),
        "failed": sum(1 for item in results if not item.get("success")),
        "items": results,
    }
    _print(summary if args.json else summary, as_json=args.json)
    return 0 if summary["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nbs", description="Nano Banana Studio CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_auth = subparsers.add_parser("auth", help="Authenticate against the NBS backend")
    p_auth_sub = p_auth.add_subparsers(dest="auth_command", required=True)

    p_auth_login = p_auth_sub.add_parser("login", help="Login with username/password")
    p_auth_login.add_argument("--username")
    p_auth_login.add_argument("--password")
    p_auth_login.add_argument("--base-url")
    p_auth_login.add_argument("--json", action="store_true")
    p_auth_login.set_defaults(func=cmd_auth_login)

    p_auth_refresh = p_auth_sub.add_parser("refresh", help="Refresh the stored access token")
    p_auth_refresh.add_argument("--base-url")
    p_auth_refresh.add_argument("--json", action="store_true")
    p_auth_refresh.set_defaults(func=cmd_auth_refresh)

    p_auth_whoami = p_auth_sub.add_parser("whoami", help="Show the current authenticated user")
    p_auth_whoami.add_argument("--base-url")
    p_auth_whoami.add_argument("--json", action="store_true")
    p_auth_whoami.set_defaults(func=cmd_auth_whoami)

    p_auth_logout = p_auth_sub.add_parser("logout", help="Logout and clear local auth state")
    p_auth_logout.add_argument("--base-url")
    p_auth_logout.add_argument("--json", action="store_true")
    p_auth_logout.set_defaults(func=cmd_auth_logout)

    p_models = subparsers.add_parser("models", help="List configured models")
    p_models.add_argument("--service", choices=["image", "audio", "video", "digital_human", "prompt"])
    p_models.add_argument("--json", action="store_true")
    p_models.set_defaults(func=cmd_models)

    p_prompt = subparsers.add_parser("prompt", help="Prompt tools")
    p_prompt_sub = p_prompt.add_subparsers(dest="prompt_command", required=True)
    p_opt = p_prompt_sub.add_parser("optimize", help="Optimize a prompt")
    p_opt.add_argument("--prompt", required=True)
    p_opt.add_argument("--subject", default="general")
    p_opt.add_argument("--model", help="Prompt model")
    p_opt.add_argument("--image-model", help="Target image model")
    p_opt.add_argument("--api-key")
    p_opt.add_argument("--base-url")
    p_opt.add_argument("--json", action="store_true")
    p_opt.set_defaults(func=cmd_prompt_optimize)

    p_image = subparsers.add_parser("image", help="Image tools")
    p_image_sub = p_image.add_subparsers(dest="image_command", required=True)
    p_img_gen = p_image_sub.add_parser("generate", help="Generate image")
    p_img_gen.add_argument("--prompt", required=True)
    p_img_gen.add_argument("--model")
    p_img_gen.add_argument("--subject", default="general")
    p_img_gen.add_argument("--size", default="1024x1024")
    p_img_gen.add_argument("--quality", default="standard")
    p_img_gen.add_argument("--style")
    p_img_gen.add_argument("--optimize", action="store_true")
    p_img_gen.add_argument("--prompt-model")
    p_img_gen.add_argument("--api-key")
    p_img_gen.add_argument("--base-url")
    p_img_gen.add_argument("--prompt-api-key")
    p_img_gen.add_argument("--prompt-base-url")
    p_img_gen.add_argument("--output")
    p_img_gen.add_argument("--json", action="store_true")
    p_img_gen.set_defaults(func=cmd_image_generate)

    p_img_edit = p_image_sub.add_parser("edit", help="Edit image with reference image(s)")
    p_img_edit.add_argument("--prompt", required=True)
    p_img_edit.add_argument("--image", action="append", required=True, help="Local image path; can be repeated")
    p_img_edit.add_argument("--model")
    p_img_edit.add_argument("--api-key")
    p_img_edit.add_argument("--base-url")
    p_img_edit.add_argument("--output")
    p_img_edit.add_argument("--json", action="store_true")
    p_img_edit.set_defaults(func=cmd_image_edit)

    p_audio = subparsers.add_parser("audio", help="Audio tools")
    p_audio_sub = p_audio.add_subparsers(dest="audio_command", required=True)
    p_tts = p_audio_sub.add_parser("tts", help="Synthesize TTS audio")
    p_tts.add_argument("--text", required=True)
    p_tts.add_argument("--model")
    p_tts.add_argument("--voice", default="Cherry")
    p_tts.add_argument("--instructions")
    p_tts.add_argument("--language-type", default="Auto")
    p_tts.add_argument("--no-optimize-instructions", action="store_true")
    p_tts.add_argument("--api-key")
    p_tts.add_argument("--base-url")
    p_tts.add_argument("--output")
    p_tts.add_argument("--json", action="store_true")
    p_tts.set_defaults(func=cmd_audio_tts)

    p_video = subparsers.add_parser("video", help="Video tools")
    p_video_sub = p_video.add_subparsers(dest="video_command", required=True)
    p_video_submit = p_video_sub.add_parser("submit", help="Submit video generation task")
    p_video_submit.add_argument("--prompt", required=True)
    p_video_submit.add_argument("--model")
    p_video_submit.add_argument("--platform", choices=["vector", "ark", "bailian"])
    p_video_submit.add_argument("--image-url")
    p_video_submit.add_argument("--image-urls", nargs="*")
    p_video_submit.add_argument("--aspect-ratio", default="16:9")
    p_video_submit.add_argument("--resolution")
    p_video_submit.add_argument("--duration", type=int)
    p_video_submit.add_argument("--api-key")
    p_video_submit.add_argument("--base-url")
    p_video_submit.add_argument("--wait", action="store_true")
    p_video_submit.add_argument("--timeout", type=int, default=600)
    p_video_submit.add_argument("--interval", type=int, default=10)
    p_video_submit.add_argument("--json", action="store_true")
    p_video_submit.set_defaults(func=cmd_video_submit)

    p_video_status = p_video_sub.add_parser("status", help="Check video task status")
    p_video_status.add_argument("--task-id", required=True)
    p_video_status.add_argument("--model")
    p_video_status.add_argument("--api-key")
    p_video_status.add_argument("--base-url")
    p_video_status.add_argument("--json", action="store_true")
    p_video_status.set_defaults(func=cmd_video_status)

    p_dh = subparsers.add_parser("digital-human", help="Digital human tools")
    p_dh_sub = p_dh.add_subparsers(dest="dh_command", required=True)
    p_dh_submit = p_dh_sub.add_parser("submit", help="Submit digital human generation task")
    p_dh_submit.add_argument("--image-url", required=True)
    p_dh_submit.add_argument("--audio-url", required=True)
    p_dh_submit.add_argument("--prompt")
    p_dh_submit.add_argument("--model")
    p_dh_submit.add_argument("--resolution", type=int, default=720)
    p_dh_submit.add_argument("--style")
    p_dh_submit.add_argument("--api-key")
    p_dh_submit.add_argument("--base-url")
    p_dh_submit.add_argument("--wait", action="store_true")
    p_dh_submit.add_argument("--timeout", type=int, default=600)
    p_dh_submit.add_argument("--interval", type=int, default=5)
    p_dh_submit.add_argument("--json", action="store_true")
    p_dh_submit.set_defaults(func=cmd_dh_submit)

    p_dh_status = p_dh_sub.add_parser("status", help="Check digital human task status")
    p_dh_status.add_argument("--task-id", required=True)
    p_dh_status.add_argument("--model")
    p_dh_status.add_argument("--api-key")
    p_dh_status.add_argument("--base-url")
    p_dh_status.add_argument("--json", action="store_true")
    p_dh_status.set_defaults(func=cmd_dh_status)

    p_batch = subparsers.add_parser("batch", help="Batch image tools")
    p_batch_sub = p_batch.add_subparsers(dest="batch_command", required=True)

    p_batch_prompts = p_batch_sub.add_parser("prompts", help="Show batch prompt config")
    p_batch_prompts.add_argument("--json", action="store_true")
    p_batch_prompts.set_defaults(func=cmd_batch_prompts)

    p_batch_history = p_batch_sub.add_parser("history", help="Show batch generation history")
    p_batch_history.add_argument("--limit", type=int, default=10)
    p_batch_history.add_argument("--json", action="store_true")
    p_batch_history.set_defaults(func=cmd_batch_history)

    p_batch_add_system = p_batch_sub.add_parser("add-system", help="Add a batch system prompt")
    p_batch_add_system.add_argument("--key", required=True)
    p_batch_add_system.add_argument("--prompt", required=True)
    p_batch_add_system.add_argument("--json", action="store_true")
    p_batch_add_system.set_defaults(func=cmd_batch_add_system)

    p_batch_remove_system = p_batch_sub.add_parser("remove-system", help="Remove a batch system prompt")
    p_batch_remove_system.add_argument("--key", required=True)
    p_batch_remove_system.add_argument("--json", action="store_true")
    p_batch_remove_system.set_defaults(func=cmd_batch_remove_system)

    p_batch_add_requirement = p_batch_sub.add_parser("add-requirement", help="Add a batch requirement prompt")
    p_batch_add_requirement.add_argument("--prompt", required=True)
    p_batch_add_requirement.add_argument("--json", action="store_true")
    p_batch_add_requirement.set_defaults(func=cmd_batch_add_requirement)

    p_batch_remove_requirement = p_batch_sub.add_parser("remove-requirement", help="Remove a batch requirement prompt")
    p_batch_remove_requirement.add_argument("--index", required=True, type=int, help="Zero-based requirement prompt index")
    p_batch_remove_requirement.add_argument("--json", action="store_true")
    p_batch_remove_requirement.set_defaults(func=cmd_batch_remove_requirement)

    p_batch_generate = p_batch_sub.add_parser("generate", help="Generate images from batch prompt config")
    p_batch_generate.add_argument("--system-key", action="append", help="System prompt key; can be repeated")
    p_batch_generate.add_argument("--requirement-index", action="append", type=int, help="Zero-based requirement prompt index; can be repeated")
    p_batch_generate.add_argument("--combo", action="append", help="Explicit combination in system_key:requirement_index form; can be repeated")
    p_batch_generate.add_argument("--model")
    p_batch_generate.add_argument("--optimize", action="store_true")
    p_batch_generate.add_argument("--api-key")
    p_batch_generate.add_argument("--base-url")
    p_batch_generate.add_argument("--output-dir")
    p_batch_generate.add_argument("--max-workers", type=int, default=1)
    p_batch_generate.add_argument("--delay-seconds", type=float, default=0.0)
    p_batch_generate.add_argument("--json", action="store_true")
    p_batch_generate.set_defaults(func=cmd_batch_generate)

    p_queue = subparsers.add_parser("queue", help="JSON-driven multi-type batch runner")
    p_queue_sub = p_queue.add_subparsers(dest="queue_command", required=True)

    p_queue_template = p_queue_sub.add_parser("template", help="Print or write a queue task template")
    p_queue_template.add_argument("--type", choices=["image", "audio", "video", "digital_human", "mixed"], default="mixed")
    p_queue_template.add_argument("--output")
    p_queue_template.add_argument("--json", action="store_true")
    p_queue_template.set_defaults(func=cmd_queue_template)

    p_queue_run = p_queue_sub.add_parser("run", help="Run queue tasks from a JSON file")
    p_queue_run.add_argument("--file", required=True)
    p_queue_run.add_argument("--output-dir")
    p_queue_run.add_argument("--continue-on-error", action="store_true")
    p_queue_run.add_argument("--video-timeout", type=int, default=600)
    p_queue_run.add_argument("--video-interval", type=int, default=10)
    p_queue_run.add_argument("--digital-human-interval", type=int, default=5)
    p_queue_run.add_argument("--json", action="store_true")
    p_queue_run.set_defaults(func=cmd_queue_run)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
