#!/usr/bin/env python3
"""Report Roil Drawing runtime availability without exposing secrets."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import sys
from urllib import error, request


DEFAULT_PLATFORM_URL = "https://image.roil.top/"
KEY_NAMES = ("ROIL_API_KEY", "OPENAI_API_KEY", "IMAGE_API_KEY")
DEFAULT_PROBE_TIMEOUT = 8.0
PROBE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _request_platform(platform_url: str, *, timeout: float, context: ssl.SSLContext | None = None) -> dict:
    last_error = None
    for method in ("HEAD", "GET"):
        try:
            req = request.Request(platform_url, headers=PROBE_HEADERS, method=method)
            with request.urlopen(req, timeout=timeout, context=context) as response:
                return {
                    "reachable": 200 <= response.status < 500,
                    "status_code": response.status,
                    "final_url": response.geturl(),
                    "method": method,
                    "error": None,
                }
        except error.HTTPError as exc:
            last_error = exc
            if method == "GET" or exc.code not in (403, 405):
                return {
                    "reachable": 200 <= exc.code < 500,
                    "status_code": exc.code,
                    "final_url": exc.geturl(),
                    "method": method,
                    "error": str(exc),
                }
    raise last_error


def probe_platform(platform_url: str, timeout: float = DEFAULT_PROBE_TIMEOUT) -> dict:
    """Check that the Roil Web entry can be reached without logging in."""

    result = {
        "checked": True,
        "reachable": False,
        "tls_verified": True,
        "status_code": None,
        "final_url": platform_url,
        "method": None,
        "error": None,
    }
    try:
        result.update(_request_platform(platform_url, timeout=timeout))
    except error.HTTPError as exc:
        result["reachable"] = 200 <= exc.code < 500
        result["status_code"] = exc.code
        result["final_url"] = exc.geturl()
        result["method"] = exc.headers.get("Allow") or "HEAD"
        result["error"] = str(exc)
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            try:
                context = ssl._create_unverified_context()
                result.update(_request_platform(platform_url, timeout=timeout, context=context))
                result["tls_verified"] = False
                result["error"] = "Local Python certificate verification failed; unverified reachability probe succeeded."
                return result
            except Exception as retry_exc:
                result["tls_verified"] = False
                result["error"] = f"{exc}; unverified retry failed: {retry_exc}"
                return result
        result["error"] = str(exc)
    return result


def build_status(*, check_platform: bool = True, timeout: float = DEFAULT_PROBE_TIMEOUT) -> dict:
    platform_url = os.environ.get("ROIL_PLATFORM_URL", DEFAULT_PLATFORM_URL).strip() or DEFAULT_PLATFORM_URL
    key_status = {name: env_present(name) for name in KEY_NAMES}
    has_base_url = env_present("ROIL_BASE_URL")
    has_fallback_key = any(key_status.values())
    platform_probe = probe_platform(platform_url, timeout) if check_platform else {
        "checked": False,
        "reachable": None,
        "status_code": None,
        "final_url": platform_url,
        "error": None,
    }
    browser_hints = {
        "open_command": shutil.which("open") is not None,
        "xdg_open_command": shutil.which("xdg-open") is not None,
    }

    return {
        "skill": "roil-drawing",
        "platform_entry_available": True,
        "platform_url": platform_url,
        "platform_probe": platform_probe,
        "roil_base_url_configured": has_base_url,
        "fallback_key_available": has_fallback_key,
        "keys_present": key_status,
        "browser_hints": browser_hints,
        "safe_to_show_user": {
            "login_prompt": f"请先登录 Roil 平台：{platform_url}",
            "no_cli_note": "没有本地 CLI 不等于没有 Roil 出图入口；Roil Web 平台就是有效入口。",
            "fallback_note": (
                "只有在无法使用 Roil 平台且用户接受 fallback 时，才考虑环境中的图片生成 key。"
            ),
        },
        "recommended_next_step": (
            "open_or_login_platform"
            if platform_probe["reachable"] is not False
            else "check_network_or_open_platform_manually"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Roil Drawing entry availability.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--no-platform-check", action="store_true", help="Skip the HTTP reachability probe.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_PROBE_TIMEOUT, help="Platform probe timeout.")
    args = parser.parse_args()

    status = build_status(check_platform=not args.no_platform_check, timeout=args.timeout)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"Roil platform: {status['platform_url']}")
        print("Platform entry available: yes")
        if status["platform_probe"]["checked"]:
            reachable = "yes" if status["platform_probe"]["reachable"] else "no"
            print(f"Platform reachable: {reachable}")
        print(f"Fallback key available: {'yes' if status['fallback_key_available'] else 'no'}")
        print(status["safe_to_show_user"]["login_prompt"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
