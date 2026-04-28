#!/usr/bin/env python3
"""Report Roil Drawing runtime availability without exposing secrets."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys


DEFAULT_PLATFORM_URL = "https://image.roil.top/"
KEY_NAMES = ("ROIL_API_KEY", "OPENAI_API_KEY", "IMAGE_API_KEY")


def env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def build_status() -> dict:
    platform_url = os.environ.get("ROIL_PLATFORM_URL", DEFAULT_PLATFORM_URL).strip() or DEFAULT_PLATFORM_URL
    key_status = {name: env_present(name) for name in KEY_NAMES}
    has_base_url = env_present("ROIL_BASE_URL")
    has_fallback_key = any(key_status.values())
    browser_hints = {
        "open_command": shutil.which("open") is not None,
        "xdg_open_command": shutil.which("xdg-open") is not None,
    }

    return {
        "skill": "roil-drawing",
        "platform_entry_available": True,
        "platform_url": platform_url,
        "roil_base_url_configured": has_base_url,
        "fallback_key_available": has_fallback_key,
        "keys_present": key_status,
        "browser_hints": browser_hints,
        "safe_to_show_user": {
            "login_prompt": (
                f"请先打开 Roil 平台 {platform_url} 并用你的账号登录；"
                "登录完成后告诉我“已登录”，我会继续生成/改图。"
                "日常使用不需要你提供模型 API Key。"
            ),
            "no_cli_note": "没有本地 CLI 不等于没有 Roil 出图入口；Roil Web 平台就是有效入口。",
            "fallback_note": (
                "只有在无法使用 Roil 平台且用户接受 fallback 时，才考虑环境中的图片生成 key。"
            ),
        },
        "recommended_next_step": "open_or_login_platform",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Roil Drawing entry availability.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    status = build_status()
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"Roil platform: {status['platform_url']}")
        print("Platform entry available: yes")
        print(f"Fallback key available: {'yes' if status['fallback_key_available'] else 'no'}")
        print(status["safe_to_show_user"]["login_prompt"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
