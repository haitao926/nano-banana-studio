#!/usr/bin/env python3
"""Roil Drawing executable entry.

This script gives agents one command to try before falling back to prose:
- Prefer an authenticated Roil/NBS runtime when available.
- Otherwise, try current-environment image generation tools.
- Only prepare a Roil-ready prompt file when no executable image path is available.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from roil_preflight import build_status, normalize_base_url


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "low"
DEFAULT_OUTPUT = "output/roil-drawing/roil-drawing.png"
DEFAULT_NBS_TIMEOUT = 420


def _write_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _maybe_open_platform(platform_url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", platform_url], check=False)
    elif os.name == "posix":
        subprocess.run(["xdg-open", platform_url], check=False)


def _prepare_prompt(
    prompt: str,
    out: Path,
    status: dict,
    *,
    open_platform: bool,
    previous_attempt: dict | None = None,
) -> int:
    platform_url = status["platform_url"]
    prompt_path = out.with_suffix(".prompt.txt")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt.strip() + "\n", encoding="utf-8")
    if open_platform:
        _maybe_open_platform(platform_url)
    payload = {
        "success": False,
        "status": "needs_platform_login",
        "via": "roil-web",
        "platform_url": platform_url,
        "platform_probe": status.get("platform_probe"),
        "prompt_path": str(prompt_path),
        "message": f"请先登录 Roil 平台：{platform_url}",
    }
    if previous_attempt:
        payload["previous_attempt"] = previous_attempt
    _write_json(payload)
    return 2


def _generate_openai(prompt: str, out: Path, *, model: str, size: str, quality: str) -> int:
    try:
        from openai import OpenAI
    except ImportError:
        _write_json(
            {
                "success": False,
                "status": "missing_dependency",
                "dependency": "openai",
                "message": "缺少 openai Python 包；请先安装 openai，或登录 Roil Web 平台继续。",
            }
        )
        return 3

    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    client = OpenAI()
    try:
        result = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
    except Exception as exc:
        _write_json(
            {
                "success": False,
                "status": "image_api_error",
                "via": "openai-image-api",
                "model": model,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            }
        )
        return 4

    image_b64 = result.data[0].b64_json
    out.write_bytes(base64.b64decode(image_b64))
    _write_json(
        {
            "success": True,
            "status": "generated",
            "via": "openai-image-api",
            "model": model,
            "output_path": str(out),
            "elapsed_seconds": round(time.time() - started, 2),
        }
    )
    return 0


def _parse_json(text: str) -> dict | None:
    payload = str(text or "").strip()
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except Exception:
        return None
    return data if isinstance(data, dict) else {"data": data}


def _prepare_auth_override(auth_info: dict) -> tuple[str | None, str | None]:
    auth_path = str(auth_info.get("auth_file_path") or "").strip()
    if not auth_info.get("auth_file_present") or not auth_path:
        return None, None

    session_base_url = normalize_base_url(auth_info.get("session_base_url"))
    stored_base_url = normalize_base_url(auth_info.get("stored_base_url"))
    if not session_base_url or session_base_url == stored_base_url:
        return auth_path, None

    source_path = Path(auth_path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Stored auth payload is not a JSON object.")
    payload["base_url"] = session_base_url

    tmp = tempfile.NamedTemporaryFile(prefix="roil_nbs_auth_", suffix=".json", delete=False)
    with tmp:
        tmp.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    return tmp.name, tmp.name


def _run_nbs_generate(prompt: str, out: Path, status: dict, *, model: str, size: str, quality: str, force_direct: bool) -> dict:
    cli_info = status.get("nbs_cli") or {}
    cli_path = str(cli_info.get("path") or "").strip()
    if not cli_path:
        return {
            "success": False,
            "status": "nbs_cli_unavailable",
            "message": "Current runtime did not expose an NBS CLI entry.",
        }

    env = os.environ.copy()
    auth_cleanup_path = None
    via = "nbs-cli-direct" if force_direct else "nbs-cli-backend"

    if force_direct:
        env["NBS_FORCE_DIRECT"] = "1"
    else:
        auth_info = status.get("nbs_auth") or {}
        try:
            auth_path, auth_cleanup_path = _prepare_auth_override(auth_info)
        except Exception as exc:
            return {
                "success": False,
                "status": "nbs_auth_override_failed",
                "via": via,
                "message": str(exc),
            }
        if auth_path:
            env["NBS_AUTH_FILE"] = auth_path

    cmd = [
        cli_path,
        "image",
        "generate",
        "--prompt",
        prompt,
        "--model",
        model,
        "--size",
        size,
        "--quality",
        quality,
        "--output",
        str(out),
        "--json",
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=DEFAULT_NBS_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "status": "nbs_cli_timeout",
            "via": via,
            "message": f"NBS image generation timed out after {DEFAULT_NBS_TIMEOUT}s.",
            "error": str(exc),
        }
    finally:
        if auth_cleanup_path:
            Path(auth_cleanup_path).unlink(missing_ok=True)

    payload = _parse_json(completed.stdout)
    if payload is None:
        payload = {
            "success": False,
            "status": "nbs_cli_invalid_output",
            "via": via,
            "stdout": completed.stdout.strip()[:1000],
            "stderr": completed.stderr.strip()[:1000],
        }

    payload.setdefault("via", via)
    payload["runner"] = "roil-drawing"
    if completed.returncode == 0:
        payload.setdefault("success", True)
    else:
        payload["success"] = False
        payload.setdefault("status", "nbs_cli_error")
        payload.setdefault("message", payload.get("error") or completed.stderr.strip() or completed.stdout.strip())
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate with Roil Drawing or prepare Roil Web prompt.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--open-platform", action="store_true")
    parser.add_argument("--json", action="store_true", help="Reserved for symmetry; output is always JSON.")
    args = parser.parse_args()

    status = build_status()
    out = Path(args.out)

    if status.get("nbs_auth", {}).get("session_available") and status.get("nbs_cli", {}).get("available"):
        backend_result = _run_nbs_generate(
            args.prompt,
            out,
            status,
            model=args.model,
            size=args.size,
            quality=args.quality,
            force_direct=False,
        )
        if backend_result.get("success"):
            _write_json(backend_result)
            return 0

        direct_result = _run_nbs_generate(
            args.prompt,
            out,
            status,
            model=args.model,
            size=args.size,
            quality=args.quality,
            force_direct=True,
        )
        if direct_result.get("success"):
            direct_result.setdefault("fallback_from", "nbs-cli-backend")
            _write_json(direct_result)
            return 0

        if os.environ.get("OPENAI_API_KEY"):
            return _generate_openai(args.prompt, out, model=args.model, size=args.size, quality=args.quality)

        backend_result["direct_attempt"] = direct_result
        _write_json(backend_result)
        return 4

    if status.get("nbs_cli", {}).get("available"):
        direct_result = _run_nbs_generate(
            args.prompt,
            out,
            status,
            model=args.model,
            size=args.size,
            quality=args.quality,
            force_direct=True,
        )
        if direct_result.get("success"):
            _write_json(direct_result)
            return 0

        if os.environ.get("OPENAI_API_KEY"):
            return _generate_openai(args.prompt, out, model=args.model, size=args.size, quality=args.quality)

        if status.get("platform_probe", {}).get("reachable") is not False:
            return _prepare_prompt(
                args.prompt,
                out,
                status,
                open_platform=args.open_platform,
                previous_attempt=direct_result,
            )

        _write_json(direct_result)
        return 4

    if os.environ.get("OPENAI_API_KEY"):
        return _generate_openai(args.prompt, out, model=args.model, size=args.size, quality=args.quality)

    return _prepare_prompt(args.prompt, out, status, open_platform=args.open_platform)


if __name__ == "__main__":
    raise SystemExit(main())
