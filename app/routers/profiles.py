"""Profiles router — manage multi-system SAP connection profiles.

Endpoints:
  GET  /api/profiles          – list all profiles (name, label, description)
  GET  /api/profiles/active   – return the currently active profile info
  POST /api/profiles/active   – switch active profile; body: {"name": "dev"}

Active profile is kept in a module-level dict (_state) so it resets on
server restart.  The "default" profile always means "read from .env / env
vars" (i.e. ``SapConfig.from_env()``); additional profiles live in
``profiles.json`` at the project root.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.sap.models import ProfileInfo, ProfileListResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

# ── File path ─────────────────────────────────────────────────────────────
_PROFILES_FILE = Path(__file__).parent.parent.parent / "profiles.json"

# ── In-memory state (resets on server restart) ────────────────────────────
_state: dict[str, str] = {"active": "default"}

# ── Default profiles definition (always present) ──────────────────────────
_BUILTIN_DEFAULT: dict[str, Any] = {
    "default": {
        "label": "Default (from .env)",
        "description": "Loaded from environment variables / .env file",
    }
}


# ── Helpers ───────────────────────────────────────────────────────────────


def _load_profiles() -> dict[str, Any]:
    """Load profiles.json; return built-in default if file is absent or invalid."""
    if not _PROFILES_FILE.exists():
        return dict(_BUILTIN_DEFAULT)
    try:
        with _PROFILES_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logger.warning("profiles.json has invalid format; using built-in defaults.")
            return dict(_BUILTIN_DEFAULT)
        return data
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load profiles.json: %s", exc)
        return dict(_BUILTIN_DEFAULT)


def get_active_profile_name() -> str:
    """Return the name of the currently active profile."""
    return _state["active"]


def get_active_profile_config() -> dict[str, Any]:
    """Return the raw config dict for the active profile (empty for 'default').

    Meta-only keys (``label``, ``description``) are stripped so that the
    caller can pass the dict directly to ``SapConfig.from_profile()``.
    """
    name = _state["active"]
    if name == "default":
        return {}
    profiles = _load_profiles()
    raw = profiles.get(name, {})
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k not in ("label", "description")}


# ── Request body ──────────────────────────────────────────────────────────


class _SetActiveRequest(BaseModel):
    name: str


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=ProfileListResult, summary="List all profiles")
def list_profiles() -> ProfileListResult:
    """Return every profile defined in ``profiles.json`` plus the built-in
    *default* profile."""
    profiles = _load_profiles()
    active = _state["active"]
    items = [
        ProfileInfo(
            name=name,
            label=info.get("label", name) if isinstance(info, dict) else name,
            description=info.get("description", "") if isinstance(info, dict) else "",
            is_active=(name == active),
        )
        for name, info in profiles.items()
    ]
    return ProfileListResult(profiles=items)


@router.get("/active", response_model=ProfileInfo, summary="Get active profile")
def get_active() -> ProfileInfo:
    """Return information about the currently active SAP connection profile."""
    name = _state["active"]
    profiles = _load_profiles()
    info = profiles.get(name, {})
    return ProfileInfo(
        name=name,
        label=info.get("label", name) if isinstance(info, dict) else name,
        description=info.get("description", "") if isinstance(info, dict) else "",
        is_active=True,
    )


@router.post("/active", response_model=ProfileInfo, summary="Switch active profile")
def set_active(body: _SetActiveRequest) -> ProfileInfo:
    """Switch the active SAP connection profile by name.

    Raises 404 if the requested profile does not exist in ``profiles.json``.
    """
    profiles = _load_profiles()
    if body.name not in profiles:
        raise HTTPException(
            status_code=404,
            detail=f"Profile {body.name!r} not found in profiles.json.",
        )
    _state["active"] = body.name
    info = profiles[body.name]
    logger.info("Active SAP profile switched to %r", body.name)
    return ProfileInfo(
        name=body.name,
        label=info.get("label", body.name) if isinstance(info, dict) else body.name,
        description=info.get("description", "") if isinstance(info, dict) else "",
        is_active=True,
    )
