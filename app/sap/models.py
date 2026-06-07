"""Pydantic models for SAP RFC responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ─────────────────────────── BAPI search ───────────────────────────────────


class FunctionModule(BaseModel):
    """Single search result entry from ``RFC_FUNCTION_SEARCH``."""

    name: str
    group: str = ""
    description: str = ""


class SearchResult(BaseModel):
    items: list[FunctionModule] = Field(default_factory=list)
    total: int = 0


# ─────────────────────────── BAPI structure ────────────────────────────────


class BapiParameter(BaseModel):
    """One parameter in a function module's interface."""

    name: str
    direction: str          # I=Import, E=Export, C=Changing, T=Tables, X=Exception
    direction_label: str    # human-readable
    type_name: str = ""     # ABAP type or structure name
    exid: str = ""          # RFC type code: C=char, I=int, F=float, b=int1, s=int2, 8=int8, …
    optional: bool = False
    default_value: str = ""
    description: str = ""
    pass_by_value: bool = False


class BapiStructureResult(BaseModel):
    func_name: str
    description: str = ""
    parameters: list[BapiParameter] = Field(default_factory=list)


# ─────────────────────────── BAPI run ──────────────────────────────────────


class BapiReturnMessage(BaseModel):
    """Single BAPIRET2 entry."""

    type: str = ""
    id: str = ""
    number: str = ""
    message: str = ""
    parameter: str = ""
    row: int = 0
    field_name: str = ""
    system: str = ""

    @property
    def is_error(self) -> bool:
        return self.type in ("E", "A")

    @property
    def is_warning(self) -> bool:
        return self.type == "W"

    @property
    def is_success(self) -> bool:
        return self.type == "S"


class BapiRunResult(BaseModel):
    func_name: str
    success: bool
    return_messages: list[BapiReturnMessage] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────── Type structure ────────────────────────────────


class TypeField(BaseModel):
    """One field inside an ABAP structure / internal table type."""

    name: str
    data_type: str = ""
    length: int = 0
    description: str = ""


class TypeStructureResult(BaseModel):
    type_name: str
    fields: list[TypeField] = Field(default_factory=list)


# ─────────────────────────── Request body ──────────────────────────────────


class BapiRunRequest(BaseModel):
    """Payload for executing a BAPI."""

    parameters: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────── Profiles ─────────────────────────────────────


class ProfileInfo(BaseModel):
    """A named SAP connection profile."""

    name: str
    label: str = ""
    description: str = ""
    is_active: bool = False


class ProfileListResult(BaseModel):
    """Response body for listing profiles."""

    profiles: list[ProfileInfo] = Field(default_factory=list)
