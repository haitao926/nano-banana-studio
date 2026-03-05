import os
import secrets
import json
import re
import socket
import ipaddress
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import parse_qs, urlparse, unquote
from html import unescape

import requests
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile

from app_state import db
from deps import get_current_user
from helpers import _build_model_candidates
from schemas import AssistantChatRequest

router = APIRouter()

DEFAULT_ASSISTANT_MODEL = os.getenv("ASSISTANT_MODEL", "kimi-k2.5")
DEFAULT_MOONSHOT_BASE_URL = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
DEFAULT_SYSTEM_PROMPT = (
    "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文对话。"
    "请给出安全、准确、有帮助的回答。"
)
MAX_UPLOAD_FILE_BYTES = 100 * 1024 * 1024
MAX_FILE_COUNT = 1000
MAX_TOTAL_FILE_BYTES = 10 * 1024 * 1024 * 1024
MAX_INLINE_FILE_CHARS = int(os.getenv("ASSISTANT_MAX_FILE_CONTEXT_CHARS", "120000"))
DEFAULT_MAX_TOOL_RESULTS = int(os.getenv("ASSISTANT_TOOL_MAX_SEARCH_RESULTS", "5"))
DEFAULT_WEB_TIMEOUT = int(os.getenv("ASSISTANT_WEB_TIMEOUT", "20"))
MAX_TOOL_CRAWL_CHARS = int(os.getenv("ASSISTANT_TOOL_MAX_CRAWL_CHARS", "16000"))
MAX_TOOL_ARG_CHARS = int(os.getenv("ASSISTANT_TOOL_MAX_ARG_CHARS", "4000"))
REQUEST_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
KNOWN_FILE_API_UNSUPPORTED_HOSTS = {"api.vectorengine.ai", "www.packyapi.com", "packyapi.com"}
TAG_RE = re.compile(r"(?is)<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style|noscript|iframe|svg)[^>]*>.*?</\1>")
WHITESPACE_RE = re.compile(r"\s+")


def _safe_base_url(url: Optional[str]) -> str:
    value = (url or DEFAULT_MOONSHOT_BASE_URL or "").strip().rstrip("/")
    return value or "https://api.moonshot.cn/v1"


def _base_host(url: Optional[str]) -> str:
    return (urlparse(_safe_base_url(url)).netloc or "").lower()


def _is_moonshot_base_url(url: Optional[str]) -> bool:
    host = _base_host(url)
    return host.endswith("moonshot.cn")


def _is_known_file_api_unsupported(url: Optional[str]) -> bool:
    return _base_host(url) in KNOWN_FILE_API_UNSUPPORTED_HOSTS


def _resolve_chat_temperature(model: str, base_url: str, requested: float) -> float:
    # Moonshot kimi models currently accept temperature=1 in chat completions.
    if _is_moonshot_base_url(base_url) and str(model or "").strip().lower().startswith("kimi-"):
        return 1.0
    try:
        return float(requested)
    except (TypeError, ValueError):
        return 0.6


def _resolve_assistant_runtime(
    model: Optional[str],
    x_model_key: Optional[str] = None,
    x_model_base_url: Optional[str] = None,
    require_moonshot: bool = False,
) -> Dict[str, str]:
    model_name = (model or DEFAULT_ASSISTANT_MODEL or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="Assistant model is required")

    if x_model_key and x_model_key.strip():
        return {
            "model": model_name,
            "api_key": x_model_key.strip(),
            "base_url": _safe_base_url(x_model_base_url),
        }

    env_key = (os.getenv("MOONSHOT_API_KEY") or "").strip()
    if env_key:
        return {
            "model": model_name,
            "api_key": env_key,
            "base_url": _safe_base_url(os.getenv("MOONSHOT_BASE_URL")),
        }

    candidates = _build_model_candidates("prompt", model=model_name)
    resolved_candidates: List[Dict[str, str]] = []
    for item in candidates:
        key = (item.get("key") or "").strip()
        if not key:
            continue
        resolved_candidates.append(
            {
                "model": model_name,
                "api_key": key,
                "base_url": _safe_base_url(item.get("base_url") or x_model_base_url),
            }
        )

    if require_moonshot and resolved_candidates:
        for runtime in resolved_candidates:
            if _is_moonshot_base_url(runtime.get("base_url")):
                return runtime
        for runtime in resolved_candidates:
            if not _is_known_file_api_unsupported(runtime.get("base_url")):
                return runtime
        hosts = sorted({_base_host(item.get("base_url")) for item in resolved_candidates if item.get("base_url")})
        host_text = ", ".join(hosts) or "configured gateway"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Current prompt keys route to unsupported file gateways ({host_text}). "
                "Please configure MOONSHOT_API_KEY or add a prompt key with base_url=https://api.moonshot.cn/v1."
            ),
        )

    if resolved_candidates:
        return {
            "model": model_name,
            "api_key": resolved_candidates[0]["api_key"],
            "base_url": resolved_candidates[0]["base_url"],
        }

    if require_moonshot:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Missing file API key for model '{model_name}'. "
                "Please configure prompt model keys or set MOONSHOT_API_KEY."
            ),
        )

    raise HTTPException(
        status_code=400,
        detail=(
            f"Missing assistant API key for model '{model_name}'. "
            "Please set MOONSHOT_API_KEY or configure the prompt model key."
        ),
    )


def _raise_upstream_error(response: requests.Response) -> None:
    detail = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error_obj = payload.get("error")
            if isinstance(error_obj, dict):
                detail = str(error_obj.get("message") or error_obj.get("msg") or "")
            detail = detail or str(payload.get("message") or payload.get("msg") or "")
        if not detail:
            detail = str(payload)
    except Exception:
        detail = response.text.strip()
    detail = detail or f"Upstream request failed with HTTP {response.status_code}"
    status = response.status_code if 400 <= response.status_code < 600 else 502
    raise HTTPException(status_code=status, detail=detail)


def _upstream_request(
    method: Literal["GET", "POST", "DELETE"],
    path: str,
    runtime: Dict[str, str],
    *,
    json_body: Optional[Dict[str, Any]] = None,
    form_data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    timeout: int = 180,
) -> requests.Response:
    path = path if path.startswith("/") else f"/{path}"
    base = runtime["base_url"].rstrip("/")
    if path.startswith("/v1/") and (base.endswith("/v1") or base.endswith("/api/v3")):
        path = path[len("/v1") :]
    url = f"{base}{path}"
    headers = {"Authorization": f"Bearer {runtime['api_key']}"}
    if files is None and json_body is not None:
        headers["Content-Type"] = "application/json"
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            data=form_data,
            files=files,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Assistant upstream network error: {exc}") from exc

    if resp.status_code >= 400:
        _raise_upstream_error(resp)
    return resp


def _response_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except Exception:
        return {"text": resp.text}


def _extract_assistant_text(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    return _extract_message_text(message)


def _extract_message_text(message: Dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("text"), str):
                chunks.append(item["text"])
                continue
            if item.get("type") == "text" and isinstance(item.get("content"), str):
                chunks.append(item["content"])
        return "\n".join([v.strip() for v in chunks if isinstance(v, str) and v.strip()]).strip()
    return ""


def _load_file_content(file_id: str, runtime: Dict[str, str]) -> str:
    resp = _upstream_request("GET", f"/v1/files/{file_id}/content", runtime, timeout=180)
    content_text = resp.text or ""
    if len(content_text) > MAX_INLINE_FILE_CHARS:
        content_text = content_text[:MAX_INLINE_FILE_CHARS]
    return content_text


def _normalize_text(value: str, limit: int = 1200) -> str:
    text = WHITESPACE_RE.sub(" ", value or "").strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _html_to_text(html: str, limit: int = MAX_TOOL_CRAWL_CHARS) -> str:
    if not html:
        return ""
    cleaned = SCRIPT_STYLE_RE.sub(" ", html)
    cleaned = TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) > limit:
        return cleaned[:limit]
    return cleaned


def _extract_title(html: str) -> str:
    if not html:
        return ""
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not match:
        return ""
    return _normalize_text(_html_to_text(match.group(1), limit=256), limit=256)


def _is_blocked_ip(raw_ip: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(raw_ip)
    except ValueError:
        return True
    return bool(
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def _validate_public_host(hostname: str) -> None:
    host = (hostname or "").strip().lower()
    if not host:
        raise ValueError("Missing hostname")
    if host in BLOCKED_HOSTS or host.endswith(".local"):
        raise ValueError(f"Blocked host: {host}")

    try:
        # Literal IP host
        ipaddress.ip_address(host)
        if _is_blocked_ip(host):
            raise ValueError(f"Blocked IP: {host}")
        return
    except ValueError:
        # Domain host
        pass

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve host: {host}") from exc

    if not infos:
        raise ValueError(f"Cannot resolve host: {host}")

    for info in infos:
        addr = info[4][0]
        if _is_blocked_ip(addr):
            raise ValueError(f"Blocked resolved IP: {addr}")


def _normalize_public_url(url: str) -> str:
    candidate = (url or "").strip()
    if not candidate:
        raise ValueError("URL is required")
    if len(candidate) > 2048:
        raise ValueError("URL too long")
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are allowed")
    if not parsed.hostname:
        raise ValueError("Invalid URL host")
    _validate_public_host(parsed.hostname)
    return parsed.geturl()


def _unwrap_search_href(href: str) -> str:
    target = (href or "").strip()
    if not target:
        return ""
    if target.startswith("//duckduckgo.com/l/?"):
        target = f"https:{target}"
    if target.startswith("https://duckduckgo.com/l/?") or target.startswith("http://duckduckgo.com/l/?"):
        parsed = urlparse(target)
        query = parse_qs(parsed.query)
        redirect_url = query.get("uddg", [""])[0]
        if redirect_url:
            return unquote(redirect_url)
    if target.startswith("//"):
        return f"https:{target}"
    if target.startswith("/l/?"):
        parsed = urlparse(target)
        query = parse_qs(parsed.query)
        redirect_url = query.get("uddg", [""])[0]
        if redirect_url:
            return unquote(redirect_url)
    if target.startswith("http://") or target.startswith("https://"):
        return target
    return ""


def _search_web(query: str, max_results: int = DEFAULT_MAX_TOOL_RESULTS) -> Dict[str, Any]:
    text = (query or "").strip()
    if not text:
        raise ValueError("query is required")
    if len(text) > 400:
        text = text[:400]

    top_k = max(1, min(int(max_results or DEFAULT_MAX_TOOL_RESULTS), 10))
    headers = {"User-Agent": REQUEST_UA}
    results: List[Dict[str, str]] = []
    seen = set()

    try:
        resp = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": text},
            headers=headers,
            timeout=DEFAULT_WEB_TIMEOUT,
        )
        resp.raise_for_status()
        html = resp.text or ""
    except requests.RequestException as exc:
        raise ValueError(f"Search request failed: {exc}") from exc

    pattern = re.compile(r'(?is)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>')
    for match in pattern.finditer(html):
        raw_href = match.group(1)
        raw_title = match.group(2)
        url = _unwrap_search_href(raw_href)
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        host = (parsed.hostname or "").lower()
        if not host or host.endswith("duckduckgo.com"):
            continue
        try:
            _validate_public_host(host)
        except ValueError:
            continue

        title = _normalize_text(_html_to_text(raw_title, limit=300), limit=300)
        if len(title) < 3:
            continue
        if url in seen:
            continue

        # Try extracting a nearby snippet in the same chunk.
        nearby = html[match.end() : match.end() + 1400]
        snippet_match = re.search(
            r'(?is)(?:result__snippet|result-snippet)[^>]*>(.*?)</(?:a|div|span|td)>',
            nearby,
        )
        snippet = ""
        if snippet_match:
            snippet = _normalize_text(_html_to_text(snippet_match.group(1), limit=500), limit=500)

        seen.add(url)
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= top_k:
            break

    if not results:
        try:
            fallback = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": text, "format": "json", "no_redirect": "1", "no_html": "1"},
                headers=headers,
                timeout=DEFAULT_WEB_TIMEOUT,
            )
            fallback.raise_for_status()
            data = fallback.json() if fallback.content else {}
            abstract_url = str(data.get("AbstractURL") or "").strip()
            abstract = _normalize_text(str(data.get("AbstractText") or ""), limit=500)
            heading = _normalize_text(str(data.get("Heading") or text), limit=200)
            if abstract_url:
                results.append({"title": heading, "url": abstract_url, "snippet": abstract})
        except Exception:
            pass

    if not results:
        try:
            wiki = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": text,
                    "srlimit": str(top_k),
                    "format": "json",
                    "utf8": "1",
                },
                headers=headers,
                timeout=DEFAULT_WEB_TIMEOUT,
            )
            wiki.raise_for_status()
            data = wiki.json() if wiki.content else {}
            search_items = (
                data.get("query", {}).get("search", [])
                if isinstance(data, dict) and isinstance(data.get("query"), dict)
                else []
            )
            for item in search_items:
                if not isinstance(item, dict):
                    continue
                title = _normalize_text(str(item.get("title") or ""), limit=200)
                snippet = _normalize_text(_html_to_text(str(item.get("snippet") or ""), limit=500), limit=500)
                page_title = str(item.get("title") or "").replace(" ", "_")
                page_url = f"https://en.wikipedia.org/wiki/{page_title}" if page_title else ""
                if title and page_url:
                    results.append({"title": title, "url": page_url, "snippet": snippet})
                if len(results) >= top_k:
                    break
        except Exception:
            pass

    return {"query": text, "results": results[:top_k]}


def _crawl_web(url: str) -> Dict[str, Any]:
    safe_url = _normalize_public_url(url)
    headers = {"User-Agent": REQUEST_UA}
    try:
        resp = requests.get(safe_url, headers=headers, timeout=DEFAULT_WEB_TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        raise ValueError(f"Crawl request failed: {exc}") from exc

    try:
        final_url = _normalize_public_url(resp.url or safe_url)
    except ValueError as exc:
        raise ValueError(f"Crawl redirected to blocked URL: {exc}") from exc

    content_type = (resp.headers.get("Content-Type") or "").lower()
    raw_text = resp.text or ""
    title = ""
    if "html" in content_type or "<html" in raw_text[:1200].lower():
        title = _extract_title(raw_text)
        text = _html_to_text(raw_text, limit=MAX_TOOL_CRAWL_CHARS)
    else:
        text = _normalize_text(raw_text, limit=MAX_TOOL_CRAWL_CHARS)

    return {
        "url": final_url,
        "title": title,
        "content_type": content_type,
        "status_code": int(resp.status_code),
        "content": text,
    }


def _get_builtin_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": (
                    "Use web search to find up-to-date information from the internet. "
                    "Call this when user asks for latest facts or asks you to search online."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "description": "Search keywords"},
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "How many results to return, default 5",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "crawl",
                "description": "Fetch and extract readable content from a web page URL.",
                "parameters": {
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {"type": "string", "description": "The target web page URL"},
                    },
                },
            },
        },
    ]


def _parse_tool_arguments(arguments: Any) -> Dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        raw = arguments.strip()
        if len(raw) > MAX_TOOL_ARG_CHARS:
            raise ValueError("tool arguments too large")
        if not raw:
            return {}
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
        raise ValueError("tool arguments must be a JSON object")
    return {}


def _execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    try:
        if tool_name == "search":
            query = str(arguments.get("query") or "").strip()
            max_results = arguments.get("max_results", DEFAULT_MAX_TOOL_RESULTS)
            result = _search_web(query=query, max_results=int(max_results or DEFAULT_MAX_TOOL_RESULTS))
            return result, None
        if tool_name == "crawl":
            url = str(arguments.get("url") or "").strip()
            result = _crawl_web(url=url)
            return result, None
        return {"error": f"Unknown tool: {tool_name}"}, "unknown_tool"
    except Exception as exc:
        return {"error": str(exc)}, "tool_error"


@router.post("/api/assistant/files")
async def assistant_upload_file(
    file: UploadFile = File(...),
    purpose: Literal["file-extract", "image", "video"] = Form("file-extract"),
    model: Optional[str] = Form(None),
    current_user: Dict = Depends(get_current_user),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    del current_user
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")

    try:
        file.file.seek(0, os.SEEK_END)
        file_size = int(file.file.tell() or 0)
        file.file.seek(0)
    except Exception:
        file_size = 0

    if file_size > MAX_UPLOAD_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Max size is 100MB.")

    runtime = _resolve_assistant_runtime(
        model=model,
        x_model_key=x_model_key,
        x_model_base_url=x_model_base_url,
        require_moonshot=True,
    )
    try:
        listing = _response_json(_upstream_request("GET", "/v1/files", runtime))
        existing_files = listing.get("data") if isinstance(listing.get("data"), list) else []
        total_files = len(existing_files)
        total_bytes = sum(int(item.get("bytes") or 0) for item in existing_files if isinstance(item, dict))
        if total_files >= MAX_FILE_COUNT:
            raise HTTPException(
                status_code=400,
                detail=f"File quota exceeded: max {MAX_FILE_COUNT} files per user.",
            )
        if file_size and (total_bytes + file_size > MAX_TOTAL_FILE_BYTES):
            raise HTTPException(
                status_code=400,
                detail="Storage quota exceeded: total uploaded files cannot exceed 10GB.",
            )
    except HTTPException:
        raise
    except Exception:
        # Keep upload path available even if pre-check fails unexpectedly.
        pass
    try:
        resp = _upstream_request(
            "POST",
            "/v1/files",
            runtime,
            form_data={"purpose": purpose},
            files={"file": (file.filename, file.file, file.content_type or "application/octet-stream")},
            timeout=300,
        )
    finally:
        await file.close()

    payload = _response_json(resp)
    return {"success": True, "file": payload}


@router.get("/api/assistant/files")
async def assistant_list_files(
    model: Optional[str] = Query(default=None),
    current_user: Dict = Depends(get_current_user),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    del current_user
    runtime = _resolve_assistant_runtime(
        model=model,
        x_model_key=x_model_key,
        x_model_base_url=x_model_base_url,
        require_moonshot=True,
    )
    payload = _response_json(_upstream_request("GET", "/v1/files", runtime))
    data = payload.get("data") if isinstance(payload.get("data"), list) else []
    return {"success": True, "data": data}


@router.get("/api/assistant/files/{file_id}")
async def assistant_get_file(
    file_id: str,
    model: Optional[str] = Query(default=None),
    current_user: Dict = Depends(get_current_user),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    del current_user
    runtime = _resolve_assistant_runtime(
        model=model,
        x_model_key=x_model_key,
        x_model_base_url=x_model_base_url,
        require_moonshot=True,
    )
    payload = _response_json(_upstream_request("GET", f"/v1/files/{file_id}", runtime))
    return {"success": True, "file": payload}


@router.delete("/api/assistant/files/{file_id}")
async def assistant_delete_file(
    file_id: str,
    model: Optional[str] = Query(default=None),
    current_user: Dict = Depends(get_current_user),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    del current_user
    runtime = _resolve_assistant_runtime(
        model=model,
        x_model_key=x_model_key,
        x_model_base_url=x_model_base_url,
        require_moonshot=True,
    )
    payload = _response_json(_upstream_request("DELETE", f"/v1/files/{file_id}", runtime))
    return {"success": True, "result": payload}


@router.get("/api/assistant/files/{file_id}/content")
async def assistant_get_file_content(
    file_id: str,
    model: Optional[str] = Query(default=None),
    current_user: Dict = Depends(get_current_user),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    del current_user
    runtime = _resolve_assistant_runtime(
        model=model,
        x_model_key=x_model_key,
        x_model_base_url=x_model_base_url,
        require_moonshot=True,
    )
    content = _load_file_content(file_id, runtime)
    return {"success": True, "file_id": file_id, "content": content}


@router.get("/api/assistant/conversations")
async def list_assistant_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Dict = Depends(get_current_user),
):
    data = db.list_assistant_conversations(user_id=current_user["id"], limit=limit)
    return {"success": True, "data": data}


@router.get("/api/assistant/conversations/{conversation_id}/messages")
async def get_assistant_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: Dict = Depends(get_current_user),
):
    conv = db.get_assistant_conversation(user_id=current_user["id"], conversation_id=conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    data = db.get_assistant_messages(user_id=current_user["id"], conversation_id=conversation_id, limit=limit)
    return {"success": True, "conversation_id": conversation_id, "data": data}


@router.delete("/api/assistant/conversations/{conversation_id}")
async def delete_assistant_conversation(
    conversation_id: str,
    current_user: Dict = Depends(get_current_user),
):
    deleted = db.delete_assistant_conversation(user_id=current_user["id"], conversation_id=conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}


@router.post("/api/assistant/chat")
async def assistant_chat(
    req: AssistantChatRequest,
    current_user: Dict = Depends(get_current_user),
    x_model_key: Optional[str] = Header(None, alias="x-model-key"),
    x_model_base_url: Optional[str] = Header(None, alias="x-model-base-url"),
):
    conversation_id = (req.conversation_id or "").strip() or secrets.token_hex(12)
    model_name = (req.model or DEFAULT_ASSISTANT_MODEL).strip() or DEFAULT_ASSISTANT_MODEL
    runtime = _resolve_assistant_runtime(model=model_name, x_model_key=x_model_key, x_model_base_url=x_model_base_url)
    model_name = runtime["model"]
    temperature = _resolve_chat_temperature(model_name, runtime.get("base_url") or "", req.temperature)

    title = req.message.strip().replace("\n", " ")[:48]
    db.create_or_touch_assistant_conversation(
        user_id=current_user["id"],
        conversation_id=conversation_id,
        model=model_name,
        title=title,
    )
    db.add_assistant_message(
        user_id=current_user["id"],
        conversation_id=conversation_id,
        role="user",
        content=req.message.strip(),
        metadata={"file_ids": req.file_ids},
    )

    history_messages = db.get_assistant_messages(
        user_id=current_user["id"],
        conversation_id=conversation_id,
        limit=req.max_history_messages,
    )
    outgoing_messages: List[Dict[str, str]] = [
        {"role": "system", "content": (req.system_prompt or DEFAULT_SYSTEM_PROMPT).strip()}
    ]

    seen_file_ids = set()
    for file_id in req.file_ids:
        file_id = str(file_id).strip()
        if not file_id or file_id in seen_file_ids:
            continue
        seen_file_ids.add(file_id)
        try:
            file_content = _load_file_content(file_id, runtime)
            if file_content:
                outgoing_messages.append(
                    {"role": "system", "content": f"[文件 {file_id}]\n{file_content}"}
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to read file {file_id}: {exc}") from exc

    for item in history_messages:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant", "system"} or not content:
            continue
        outgoing_messages.append({"role": role, "content": content})

    tool_events: List[Dict[str, Any]] = []
    body: Dict[str, Any] = {}
    assistant_text = ""

    if req.enable_tools:
        loop_messages: List[Dict[str, Any]] = list(outgoing_messages)
        max_rounds = max(1, int(req.max_tool_rounds or 4))
        for round_index in range(max_rounds + 1):
            payload = {
                "model": model_name,
                "messages": loop_messages,
                "temperature": temperature,
                "tools": _get_builtin_tools(),
                "tool_choice": "auto",
            }
            resp = _upstream_request("POST", "/v1/chat/completions", runtime, json_body=payload, timeout=300)
            body = _response_json(resp)
            choices = body.get("choices") if isinstance(body, dict) else None
            choice = choices[0] if isinstance(choices, list) and choices else {}
            finish_reason = str(choice.get("finish_reason") or "")
            model_message = choice.get("message") if isinstance(choice, dict) else None

            if finish_reason == "tool_calls":
                if round_index >= max_rounds:
                    forced_answer_messages: List[Dict[str, Any]] = list(loop_messages)
                    forced_answer_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "工具调用轮次已到上限。禁止继续调用任何工具，"
                                "请仅基于现有工具返回内容直接回答用户问题。"
                            ),
                        }
                    )
                    forced_payload = {
                        "model": model_name,
                        "messages": forced_answer_messages,
                        "temperature": temperature,
                    }
                    forced_resp = _upstream_request(
                        "POST",
                        "/v1/chat/completions",
                        runtime,
                        json_body=forced_payload,
                        timeout=300,
                    )
                    body = _response_json(forced_resp)
                    forced_choices = body.get("choices") if isinstance(body, dict) else None
                    forced_choice = forced_choices[0] if isinstance(forced_choices, list) and forced_choices else {}
                    forced_message = forced_choice.get("message") if isinstance(forced_choice, dict) else None
                    if isinstance(forced_message, dict):
                        assistant_text = _extract_message_text(forced_message)
                    if not assistant_text:
                        assistant_text = "工具调用达到最大轮次，请缩小问题范围后重试。"
                    break
                if not isinstance(model_message, dict):
                    raise HTTPException(status_code=502, detail="Assistant returned invalid tool message")

                loop_messages.append(model_message)
                tool_calls = model_message.get("tool_calls")
                if not isinstance(tool_calls, list) or not tool_calls:
                    raise HTTPException(status_code=502, detail="Assistant tool call payload is empty")

                for call_index, tool_call in enumerate(tool_calls):
                    tool_call = tool_call if isinstance(tool_call, dict) else {}
                    call_id = str(tool_call.get("id") or f"tool-{round_index}-{call_index}")
                    function_obj = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
                    tool_name = str(function_obj.get("name") or "").strip()
                    raw_args = function_obj.get("arguments")
                    parsed_args: Dict[str, Any] = {}
                    result: Dict[str, Any]
                    status = "ok"
                    try:
                        parsed_args = _parse_tool_arguments(raw_args)
                        result, tool_status = _execute_tool_call(tool_name, parsed_args)
                        if tool_status:
                            status = tool_status
                    except Exception as exc:
                        result = {"error": str(exc)}
                        status = "tool_error"

                    loop_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": tool_name or "unknown",
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                    tool_events.append(
                        {
                            "round": round_index + 1,
                            "tool": tool_name or "unknown",
                            "status": status,
                            "arguments": parsed_args,
                        }
                    )
                continue

            if isinstance(model_message, dict):
                assistant_text = _extract_message_text(model_message)
            if not assistant_text:
                assistant_text = _extract_assistant_text(body)
            break
        else:
            assistant_text = "工具调用达到最大轮次，请缩小问题范围后重试。"
    else:
        payload = {
            "model": model_name,
            "messages": outgoing_messages,
            "temperature": temperature,
        }
        resp = _upstream_request("POST", "/v1/chat/completions", runtime, json_body=payload, timeout=300)
        body = _response_json(resp)
        assistant_text = _extract_assistant_text(body)

    if not assistant_text:
        raise HTTPException(status_code=502, detail="Assistant returned empty response")

    db.add_assistant_message(
        user_id=current_user["id"],
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_text,
        metadata={
            "usage": body.get("usage") if isinstance(body, dict) else {},
            "tool_events": tool_events,
            "tools_enabled": bool(req.enable_tools),
        },
    )

    return {
        "success": True,
        "conversation_id": conversation_id,
        "model": model_name,
        "message": assistant_text,
        "usage": body.get("usage") if isinstance(body, dict) else {},
        "tool_events": tool_events,
    }
