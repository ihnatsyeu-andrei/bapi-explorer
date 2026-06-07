"""AI assistant router — GitHub Copilot SDK integration.

Provides a streaming SSE endpoint that proxies chat messages to the
Copilot SDK, maintaining per-browser-session conversation state with
a SAP BAPI expert system prompt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

# ── Model selection ────────────────────────────────────────────────────────
# Ordered preference list — first available model wins.
_FAST_MODEL_PREFERENCE = [
    "gpt-5-mini",
    "claude-haiku-4.5",
    "gpt-4o-mini",
    "gpt-4.5-mini",
    "claude-haiku-4-5",
    "gemini-2.0-flash",
]

_selected_model: str | None = None  # cached after first resolution
_model_lock = asyncio.Lock()


async def _get_fast_model(client: object) -> str | None:
    """Query available models and return the fastest available one."""
    global _selected_model
    async with _model_lock:
        if _selected_model is not None:
            return _selected_model
        try:
            models = await client.list_models()  # type: ignore[attr-defined]
            available_ids = {
                (m.id if hasattr(m, "id") else str(m)).lower()
                for m in (models or [])
            }
            logger.info("Available Copilot models: %s", available_ids)
            for preferred in _FAST_MODEL_PREFERENCE:
                if preferred.lower() in available_ids:
                    _selected_model = preferred
                    logger.info("Selected fast model: %s", _selected_model)
                    return _selected_model
            # No preferred model found — let SDK use its default
            logger.info("No fast model found in available set; using SDK default")
        except Exception:
            logger.exception("Failed to list models; using SDK default")
        return None


# ── In-memory session store ────────────────────────────────────────────────

_SESSION_TTL = 1800  # seconds (30 min idle)


class _SessionEntry:
    def __init__(self, client: object, session: object, bapi_name: str | None) -> None:
        self.client = client
        self.session = session
        self.bapi_name = bapi_name
        self.last_used = time.monotonic()

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self.last_used > _SESSION_TTL


_sessions: dict[str, _SessionEntry] = {}
_sessions_lock = asyncio.Lock()

# ── System prompt ──────────────────────────────────────────────────────────

_BASE_SYSTEM_PROMPT = """You are an expert SAP BAPI/RFC assistant embedded in BAPI Explorer — a developer tool for exploring and executing SAP RFC function modules.

Your role:
- Help developers understand SAP BAPIs, RFC function modules, and their parameters
- Explain DDIC parameter types, structures (TypedDict/BAPI structures), and expected values
- Guide users on how to fill complex nested structures (e.g. ORDER_HEADER_IN, BAPISDH1, BAPIRET2)
- Help interpret RETURN/BAPIRET2 messages and SAP error codes
- Suggest related BAPIs for common tasks (e.g. for sales orders: BAPI_SALESORDER_CREATEFROMDAT2)
- Provide minimal but complete JSON payload examples

Guidelines:
- Be concise and technical — your audience are developers familiar with SAP
- Use SAP terminology correctly (BAPI, RFC, DDIC, ABAP, transport, posting, etc.)
- When showing JSON, prefer short realistic examples over full empty templates
- If a field name is unclear, explain its SAP meaning (e.g. VBELN = sales order number)
- Focus on the BAPI currently being viewed when context is provided
"""

_PARAMCLASS_LABEL = {
    "I": "Import", "IMPORT": "Import",
    "E": "Export", "EXPORT": "Export",
    "C": "Changing", "CHANGING": "Changing",
    "T": "Tables", "TABLES": "Tables",
}


def _build_system_message(
    bapi_name: str | None,
    bapi_description: str | None,
    bapi_params: list[dict] | None,
    bapi_type_fields: dict[str, list[dict]] | None,
) -> str:
    msg = _BASE_SYSTEM_PROMPT

    if not bapi_name:
        return msg

    msg += f"\n\n## Current BAPI: `{bapi_name}`"
    if bapi_description:
        msg += f"\n**Description:** {bapi_description}"

    if bapi_params:
        sections: dict[str, list[dict]] = {}
        for p in bapi_params:
            cls = _PARAMCLASS_LABEL.get(p.get("paramclass", ""), p.get("paramclass", "Other"))
            sections.setdefault(cls, []).append(p)

        for section_name, params in sections.items():
            msg += f"\n\n### {section_name} Parameters\n"
            for p in params:
                name = p.get("name", "?")
                typedef = p.get("tabname") or p.get("typedef") or ""
                desc = p.get("description") or p.get("paramtext") or ""
                optional = "optional" if p.get("optional") else "required"
                default = p.get("default") or ""

                line = f"- **{name}**"
                if typedef:
                    line += f" `[{typedef}]`"
                line += f" ({optional})"
                if desc:
                    line += f" — {desc}"
                if default:
                    line += f" (default: `{default}`)"
                msg += line + "\n"

                # Include type field details if available from drill-down cache
                if typedef and bapi_type_fields and typedef in bapi_type_fields:
                    fields = bapi_type_fields[typedef]
                    if fields:
                        field_lines = ", ".join(
                            f"{f.get('name')}:{f.get('data_type','?')}"
                            + (f"({f.get('description','')})" if f.get("description") else "")
                            for f in fields[:30]
                        )
                        msg += f"  Fields: {field_lines}\n"

    return msg


# ── SDK session management ─────────────────────────────────────────────────


async def _get_or_create_session(
    session_id: str,
    bapi_name: str | None,
    bapi_description: str | None,
    bapi_params: list[dict] | None,
    bapi_type_fields: dict[str, list[dict]] | None,
) -> _SessionEntry:
    from copilot import CopilotClient  # lazy import — avoids startup cost when SDK unused
    from copilot.session import PermissionHandler, SystemMessageConfig  # type: ignore[attr-defined]

    async with _sessions_lock:
        entry = _sessions.get(session_id)

        needs_new = (
            entry is None
            or entry.is_expired
            or (bapi_name is not None and entry.bapi_name != bapi_name)
        )

        if needs_new:
            if entry is not None:
                await _cleanup_entry(entry)

            system_text = _build_system_message(
                bapi_name, bapi_description, bapi_params, bapi_type_fields
            )
            system_msg: SystemMessageConfig = {"mode": "append", "content": system_text}

            client = CopilotClient()
            await client.start()

            model = await _get_fast_model(client)
            create_kwargs: dict = {
                "on_permission_request": PermissionHandler.approve_all,
                "streaming": True,
                "system_message": system_msg,
            }
            if model:
                create_kwargs["model"] = model

            session = await client.create_session(**create_kwargs)

            entry = _SessionEntry(client, session, bapi_name)
            _sessions[session_id] = entry

        entry.last_used = time.monotonic()
        return entry


async def _cleanup_entry(entry: _SessionEntry) -> None:
    try:
        await entry.session.disconnect()
    except Exception:
        pass
    try:
        await entry.client.stop()
    except Exception:
        pass


# ── Streaming SSE helper ───────────────────────────────────────────────────


async def _sse_stream(session: object, message: str):
    """Yield SSE data lines with streamed assistant response chunks."""
    from copilot.session_events import (  # type: ignore[attr-defined]
        AssistantMessageDeltaData,
        SessionIdleData,
    )

    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def handler(event: object) -> None:
        match event.data:  # type: ignore[attr-defined]
            case AssistantMessageDeltaData() as d:
                loop.call_soon_threadsafe(q.put_nowait, ("delta", d.delta_content or ""))
            case SessionIdleData():
                loop.call_soon_threadsafe(q.put_nowait, ("done", ""))

    unsubscribe: Callable[[], None] = session.on(handler)  # type: ignore[attr-defined]

    try:
        await session.send(message)  # type: ignore[attr-defined]

        while True:
            kind, content = await asyncio.wait_for(q.get(), timeout=90.0)
            if kind == "done":
                yield "data: [DONE]\n\n"
                return
            yield f"data: {json.dumps(content)}\n\n"

    except asyncio.TimeoutError:
        yield f"data: {json.dumps('(response timed out)')}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as exc:
        logger.exception("Error streaming Copilot response")
        yield f"data: {json.dumps(f'(error: {exc})')}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        unsubscribe()


# ── Request model ──────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    session_id: str
    bapi_name: str | None = None
    bapi_description: str | None = None
    bapi_params: list[dict] | None = None
    bapi_type_fields: dict[str, list[dict]] | None = None  # type drill-down cache


# ── Routes ─────────────────────────────────────────────────────────────────


@router.post("/chat")
async def chat(req: ChatRequest):
    """Stream an AI assistant response via Server-Sent Events."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        entry = await _get_or_create_session(
            req.session_id,
            req.bapi_name,
            req.bapi_description,
            req.bapi_params,
            req.bapi_type_fields,
        )
    except Exception as exc:
        logger.exception("Failed to create Copilot session")
        raise HTTPException(status_code=503, detail=f"Copilot unavailable: {exc}") from exc

    return StreamingResponse(
        _sse_stream(entry.session, req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Destroy a chat session and free its Copilot SDK resources."""
    async with _sessions_lock:
        entry = _sessions.pop(session_id, None)

    if entry:
        await _cleanup_entry(entry)

    return {"status": "ok"}
