"""BAPI Explorer — FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

Or via the helper script:
    python -m app.main
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import ai, bapi, profiles, ui

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="BAPI Explorer",
    description=(
        "A web-based tool for searching, inspecting, and executing "
        "SAP RFC function modules / BAPIs via pyrfc."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Static files ───────────────────────────────────────────────────────────
_STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(bapi.router)      # /api/bapi/*
app.include_router(profiles.router)  # /api/profiles/*
app.include_router(ai.router)        # /api/ai/*
app.include_router(ui.router)        # /, /bapi/{name}


# ── Dev entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv(override=False)

    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))

    logger.info("Starting BAPI Explorer on http://%s:%d", host, port)
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
