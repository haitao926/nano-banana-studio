import os
import secrets
from typing import Any, Dict, List, Literal, Optional

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


def _safe_base_url(url: Optional[str]) -> str:
    value = (url or DEFAULT_MOONSHOT_BASE_URL or "").strip().rstrip("/")
    return value or "https://api.moonshot.cn/v1"


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

    if require_moonshot:
        raise HTTPException(
            status_code=400,
            detail=(
                "File API requires MOONSHOT_API_KEY (or pass x-model-key + x-model-base-url). "
                "Current system prompt keys are not guaranteed to support /v1/files."
            ),
        )

    candidates = _build_model_candidates("prompt", model=model_name)
    for item in candidates:
        key = (item.get("key") or "").strip()
        if not key:
            continue
        return {
            "model": model_name,
            "api_key": key,
            "base_url": _safe_base_url(item.get("base_url") or x_model_base_url),
        }

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

    payload = {
        "model": model_name,
        "messages": outgoing_messages,
        "temperature": float(req.temperature),
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
        metadata={"usage": body.get("usage") if isinstance(body, dict) else {}},
    )

    return {
        "success": True,
        "conversation_id": conversation_id,
        "model": model_name,
        "message": assistant_text,
        "usage": body.get("usage") if isinstance(body, dict) else {},
    }
