"""BAPI API router.

All endpoints return JSON.  The SAP client is instantiated per-request using
the currently active connection profile.  When the active profile is "default",
``SapConfig.from_env()`` is used; otherwise ``SapConfig.from_profile()`` is
called with that profile's config dict.

Endpoints:
  GET  /api/bapi/search?q=BAPI_SALES*&max=100   – search function modules
  GET  /api/bapi/{name}/structure                – get parameter interface
  POST /api/bapi/{name}/run                      – execute a BAPI
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.routers import profiles as profiles_router
from app.sap.client import SapConnectionError, SapRfcClient
from app.sap.config import SapConfig
from app.sap.models import (
    BapiRunRequest,
    BapiRunResult,
    BapiStructureResult,
    SearchResult,
    TypeStructureResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bapi", tags=["bapi"])


def _get_client() -> SapRfcClient:
    """Build a SAP client for the currently active profile; raise 503 on failure."""
    try:
        active = profiles_router.get_active_profile_name()
        if active == "default":
            config = SapConfig.from_env()
        else:
            config = SapConfig.from_profile(profiles_router.get_active_profile_config())
        return SapRfcClient(config)
    except (RuntimeError, ImportError) as exc:
        logger.error("SAP client init failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ──────────────────────────────────────────────────────────────────────────── #
# Search
# ──────────────────────────────────────────────────────────────────────────── #


@router.get("/search", response_model=SearchResult, summary="Search function modules")
def search_bapi(
    q: Annotated[
        str,
        Query(
            min_length=1,
            description="Wildcard search pattern, e.g. `BAPI_SALES*`. "
                        "Use `*` to match any characters.",
        ),
    ],
    max: Annotated[int, Query(ge=1, le=500, description="Max results")] = 100,
) -> SearchResult:
    """Search for RFC function modules matching the given pattern.

    The pattern supports SAP-style wildcards:
    - ``*`` matches any sequence of characters
    - ``+`` matches exactly one character

    Examples: ``BAPI_SALESORDER*``, ``RFC_READ*``, ``*MATERIAL*``
    """
    client = _get_client()
    try:
        return client.search_function_modules(pattern=q, max_results=max)
    except SapConnectionError as exc:
        logger.error("RFC_FUNCTION_SEARCH failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ──────────────────────────────────────────────────────────────────────────── #
# Type info
# ──────────────────────────────────────────────────────────────────────────── #


@router.get("/type-info", response_model=TypeStructureResult, summary="Get ABAP type fields")
def get_type_info(
    name: Annotated[
        str,
        Query(min_length=1, description="ABAP data dictionary type/structure name, e.g. BAPISDH1"),
    ],
) -> TypeStructureResult:
    """Return the field list (name, type, length, description) for an ABAP type.

    Uses ``DDIF_FIELDINFO_GET`` internally.  Works for structures, table types,
    and transparent tables.
    """
    client = _get_client()
    try:
        return client.get_type_structure(type_name=name)
    except SapConnectionError as exc:
        logger.error("DDIF_FIELDINFO_GET(%r) failed: %s", name, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ──────────────────────────────────────────────────────────────────────────── #
# Structure
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{name:path}/structure",
    response_model=BapiStructureResult,
    summary="Get BAPI parameter interface",
)
def get_structure(name: str) -> BapiStructureResult:
    """Return the import / export / changing / table parameter list for a function module.

    Each parameter entry includes its direction, ABAP type, optional flag,
    default value, and description.
    """
    client = _get_client()
    try:
        return client.get_function_structure(func_name=name)
    except SapConnectionError as exc:
        logger.error("RFC_GET_FUNCTION_INTERFACE(%r) failed: %s", name, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ──────────────────────────────────────────────────────────────────────────── #
# Run
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{name:path}/run",
    response_model=BapiRunResult,
    summary="Execute a BAPI",
)
def run_bapi(name: str, body: BapiRunRequest) -> BapiRunResult:
    """Execute a function module with the provided parameters.

    Pass import / changing parameters as simple key-value pairs.
    Table parameters should be arrays of objects.

    The response always includes the full raw RFC output in ``data``,
    even when ``success`` is ``false``.
    """
    client = _get_client()
    try:
        return client.run_bapi(func_name=name, parameters=body.parameters)
    except SapConnectionError as exc:
        logger.error("RFC call %r failed: %s", name, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
