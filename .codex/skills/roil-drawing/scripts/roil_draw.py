#!/usr/bin/env python3
"""Roil Drawing executable entry.

This script gives agents one command to try before falling back to prose:
- If OPENAI_API_KEY is available, generate through the OpenAI Image API.
- Otherwise, prepare a Roil-ready prompt file and return the Roil Web login path.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from roil_preflight import build_status


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "low"
DEFAULT_OUTPUT = "output/roil-drawing/roil-drawing.png"


def _write_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _maybe_open_platform(platform_url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", platform_url], check=False)
    elif os.name == "posix":
        subprocess.run(["xdg-open", platform_url], check=False)


def _prepare_prompt(prompt: str, out: Path, platform_url: str, *, open_platform: bool) -> int:
    prompt_path = out.with_suffix(".prompt.txt")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt.strip() + "\n", encoding="utf-8")
    if open_platform:
        _maybe_open_platform(platform_url)
    _write_json(
        {
            "success": False,
            "status": "needs_platform_login",
            "via": "roil-web",
            "platform_url": platform_url,
            "prompt_path": str(prompt_path),
            "message": (
                f"请先打开 Roil 平台 {platform_url} 并登录。"
                "我已经把可直接粘贴的提示词写入 prompt_path。"
            ),
        }
    )
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
    platform_url = status["platform_url"]
    out = Path(args.out)

    if os.environ.get("OPENAI_API_KEY"):
        return _generate_openai(args.prompt, out, model=args.model, size=args.size, quality=args.quality)

    return _prepare_prompt(args.prompt, out, platform_url, open_platform=args.open_platform)


if __name__ == "__main__":
    raise SystemExit(main())
