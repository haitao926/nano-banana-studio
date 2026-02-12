import os
import re
from typing import List, Optional


def load_env_file(file_path: str) -> None:
    """Load key=value pairs from a file without overriding existing env vars."""
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if value.startswith("'") and not value.endswith("'"):
            buffer = [value[1:]]
            while i < len(lines):
                chunk = lines[i]
                i += 1
                if chunk.endswith("'"):
                    buffer.append(chunk[:-1])
                    break
                buffer.append(chunk)
            value = "\n".join(buffer)
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        elif value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        os.environ[key] = value


def normalize_key_list(raw) -> List[str]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        items = re.split(r"[,\\n]", raw)
    else:
        items = []
    return [str(k).strip() for k in items if str(k).strip()]


def get_env_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_env_list(name: str) -> Optional[List[str]]:
    raw = os.getenv(name)
    if raw is None:
        return None
    items = normalize_key_list(raw)
    return items or None
