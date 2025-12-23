#!/usr/bin/env python3
"""Simple smoke test for the nanoapi.poloai.top endpoint."""

import argparse
import json
import os
from pathlib import Path
from typing import Tuple

import requests

DEFAULT_BASE_URL = "https://nanoapi.poloai.top"
DEFAULT_MODEL = "gemini-2.5-flash-image"


def load_credentials() -> Tuple[str, str]:
    """Load base URL and API key from env vars or the bundled config."""
    base_url = os.getenv("NANO_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    api_key = os.getenv("NANO_API_KEY")

    if not api_key:
        cfg_path = Path(__file__).parent / "backend" / "data" / "config.json"
        try:
            with cfg_path.open(encoding="utf-8") as fh:
                api_key = json.load(fh)["auth"]["api_key"]
        except FileNotFoundError as exc:  # pragma: no cover - quick script
            raise RuntimeError("API key missing: set NANO_API_KEY or update config.json") from exc

    return base_url, api_key


def list_models(base_url: str, headers: dict) -> dict:
    url = f"{base_url}/v1/models"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    print("Models response:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def generate_image(base_url: str, headers: dict, prompt: str, size: str) -> str:
    url = f"{base_url}/v1/images/generations"
    payload = {"model": DEFAULT_MODEL, "prompt": prompt, "n": 1, "size": size}
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    image_url = data["data"][0]["url"]
    print(f"Image URL: {image_url}")
    return image_url


def download_image(image_url: str, dest: Path) -> Path:
    resp = requests.get(image_url, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"Saved image to {dest}")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Nano API smoke test.")
    parser.add_argument(
        "--prompt",
        default="Cute banana icon on a white background, minimal style",
        help="Prompt for image generation.",
    )
    parser.add_argument("--size", default="512x512", help="Image size, e.g. 512x512.")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the generated image to ./nano_test.png.",
    )
    parser.add_argument(
        "--mode",
        choices=["models", "image", "both"],
        default="image",
        help="Which endpoint(s) to call.",
    )
    args = parser.parse_args()

    base_url, api_key = load_credentials()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    print(f"Using base_url={base_url}")

    if args.mode in {"models", "both"}:
        try:
            list_models(base_url, headers)
        except Exception as exc:  # pragma: no cover - quick script
            print(f"Model listing failed: {exc}")

    if args.mode in {"image", "both"}:
        try:
            image_url = generate_image(base_url, headers, args.prompt, args.size)
            if args.download:
                download_image(image_url, Path("nano_test.png"))
        except Exception as exc:  # pragma: no cover - quick script
            print(f"Image generation failed: {exc}")


if __name__ == "__main__":
    main()
