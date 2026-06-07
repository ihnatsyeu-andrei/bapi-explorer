"""UI page router — serves Jinja2-rendered HTML pages."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Main search page."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/bapi/{name:path}", response_class=HTMLResponse)
def bapi_detail(request: Request, name: str) -> HTMLResponse:
    """BAPI detail page — loads structure and provides run form via JS."""
    return templates.TemplateResponse(
        "bapi_detail.html",
        {"request": request, "bapi_name": name.upper()},
    )
