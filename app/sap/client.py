"""SAP RFC client for BAPI Explorer.

All public methods open a fresh pyrfc.Connection, call the remote function,
and close the connection in a ``finally`` block — avoiding connection leaks.

``pyrfc`` is Windows-only (requires the SAP NW RFC SDK).  The import is
deferred to runtime so the module can be imported on non-Windows hosts for
testing purposes (mock the client in tests).
"""

from __future__ import annotations

import json
from typing import Any

from .config import SapConfig
from .models import (
    BapiParameter,
    BapiReturnMessage,
    BapiRunResult,
    BapiStructureResult,
    FunctionModule,
    SearchResult,
    TypeField,
    TypeStructureResult,
)

# ── Direction code → human-readable label ──────────────────────────────────
_DIRECTION_LABEL: dict[str, str] = {
    "I": "Import",
    "E": "Export",
    "C": "Changing",
    "T": "Tables",
    "X": "Exception",
}

# BAPIRET2-style return table key candidates
_RETURN_KEYS = ("RETURN", "ET_RETURN", "RETURN_TAB", "T_RETURN")

# EXID codes that map to Python int / float
_INT_EXIDS = frozenset({"I", "b", "s", "8"})
_FLOAT_EXIDS = frozenset({"F"})


class SapConnectionError(Exception):
    """RFC transport / authentication failure.

    Does NOT cover BAPIRET2 business-logic errors — those surface as
    ``BapiReturnMessage`` entries inside ``BapiRunResult``.
    """


class SapRfcClient:
    """High-level SAP RFC client for BAPI Explorer."""

    def __init__(self, config: SapConfig) -> None:
        self._config = config
        try:
            import pyrfc  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "pyrfc is not installed or the SAP NW RFC SDK cannot be found.\n"
                "Set SAPNWRFC_HOME and run:  pip install pyrfc"
            ) from exc

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _connect(self):  # type: ignore[return]
        """Return an open pyrfc.Connection."""
        import pyrfc

        return pyrfc.Connection(**self._config.to_pyrfc_params())

    def _call_raw(self, func_name: str, **kwargs: Any) -> dict:
        """Open a connection, call func_name, close, return raw dict.

        Raises:
            SapConnectionError: on any pyrfc transport/auth/ABAP error.
        """
        import pyrfc

        conn = None
        try:
            conn = self._connect()
            return conn.call(func_name, **kwargs)
        except pyrfc.ABAPApplicationError as exc:
            raise SapConnectionError(f"ABAP application error in {func_name!r}: {exc}") from exc
        except pyrfc.ABAPRuntimeError as exc:
            raise SapConnectionError(f"ABAP runtime error in {func_name!r}: {exc}") from exc
        except pyrfc.LogonError as exc:
            raise SapConnectionError(
                f"SAP logon failed ({self._config.safe_repr()}): {exc}"
            ) from exc
        except pyrfc.CommunicationError as exc:
            raise SapConnectionError(f"SAP communication error in {func_name!r}: {exc}") from exc
        except pyrfc.RFCError as exc:
            raise SapConnectionError(f"RFC error in {func_name!r}: {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def search_function_modules(self, pattern: str, max_results: int = 100) -> SearchResult:
        """Search SAP function modules by name pattern.

        Args:
            pattern:     Wildcard pattern, e.g. ``'BAPI_SALES*'``.
                         An implicit trailing ``*`` is NOT added — include it explicitly.
            max_results: Maximum number of results to return.

        Returns:
            ``SearchResult`` with matching function module names and descriptions.
        """
        raw = self._call_raw(
            "RFC_FUNCTION_SEARCH",
            FUNCNAME=pattern.upper(),
            GROUPNAME="",
        )

        functions: list[FunctionModule] = []
        for row in (raw.get("FUNCTIONS") or []):
            functions.append(
                FunctionModule(
                    name=str(row.get("FUNCNAME") or row.get("NAME") or "").strip(),
                    group=str(row.get("GROUPNAME") or row.get("GROUP") or "").strip(),
                    description=str(row.get("STEXT") or row.get("SHORT_TEXT") or "").strip(),
                )
            )
            if len(functions) >= max_results:
                break

        return SearchResult(items=functions, total=len(functions))

    def get_function_structure(self, func_name: str) -> BapiStructureResult:
        """Retrieve the interface (parameter list) of a function module.

        Uses ``RFC_GET_FUNCTION_INTERFACE`` which returns a ``PARAMS`` table
        with one row per import / export / changing / table parameter plus
        exceptions.

        Args:
            func_name: Exact SAP function module name (e.g. ``'BAPI_SALESORDER_GETLIST'``).

        Returns:
            ``BapiStructureResult`` with a list of ``BapiParameter`` entries.
        """
        raw = self._call_raw("RFC_GET_FUNCTION_INTERFACE", FUNCNAME=func_name.upper())

        # Fetch the short description via RFC_FUNCTION_SEARCH (exact match)
        description = ""
        try:
            search_raw = self._call_raw(
                "RFC_FUNCTION_SEARCH",
                FUNCNAME=func_name.upper(),
                GROUPNAME="",
            )
            rows = search_raw.get("FUNCTIONS") or []
            if rows:
                description = str(rows[0].get("STEXT") or "").strip()
        except Exception:
            pass

        parameters: list[BapiParameter] = []
        for row in (raw.get("PARAMS") or []):
            direction_code = str(
                row.get("PARAMCLASS") or row.get("DIRECTION") or row.get("PARAMTYPE") or ""
            ).strip().upper()
            parameters.append(
                BapiParameter(
                    name=str(row.get("PARAMETER") or row.get("NAME") or "").strip(),
                    direction=direction_code,
                    direction_label=_DIRECTION_LABEL.get(direction_code, direction_code),
                    type_name=str(
                        row.get("TABNAME") or row.get("TYPEDEF") or row.get("ABAPTYPE") or ""
                    ).strip(),
                    exid=str(row.get("EXID") or "").strip(),
                    optional=bool(row.get("OPTIONAL") == "X"),
                    default_value=str(row.get("DEFAULT") or row.get("DEFAULTVAL") or "").strip(),
                    description=str(row.get("PARAMTEXT") or row.get("SHORT_TEXT") or "").strip(),
                    pass_by_value=bool(row.get("PASS_BY_VALUE") == "X"),
                )
            )

        return BapiStructureResult(
            func_name=func_name.upper(),
            description=description,
            parameters=parameters,
        )

    def get_type_structure(self, type_name: str) -> TypeStructureResult:
        """Retrieve the field list of an ABAP structure or table type.

        Uses ``DDIF_FIELDINFO_GET`` to look up dictionary metadata.

        Args:
            type_name: ABAP data dictionary object name (e.g. ``'BAPISDH1'``).

        Returns:
            ``TypeStructureResult`` with field name, data type, length, and description.
        """
        raw = self._call_raw(
            "DDIF_FIELDINFO_GET",
            TABNAME=type_name.upper(),
            ALL_TYPES="X",
        )

        fields: list[TypeField] = []
        for row in (raw.get("DFIES_TAB") or []):
            fname = str(row.get("FIELDNAME") or "").strip()
            if not fname or fname.startswith("."):
                continue
            fields.append(
                TypeField(
                    name=fname,
                    data_type=str(row.get("DATATYPE") or "").strip(),
                    length=int(row.get("INTLEN") or 0),
                    description=str(
                        row.get("FIELDTEXT") or row.get("SCRTEXT_M") or row.get("SCRTEXT_L") or ""
                    ).strip(),
                )
            )

        return TypeStructureResult(type_name=type_name.upper(), fields=fields)

    def run_bapi(self, func_name: str, parameters: dict[str, Any]) -> BapiRunResult:
        """Execute a BAPI / RFC function module with the given parameters.

        Opens a single connection, fetches the parameter EXID map to coerce
        string values to the correct Python types (int/float), then executes
        the function module.

        Args:
            func_name:   SAP function module name.
            parameters:  Dict mapping parameter names to values.
                         Table parameters should be ``list[dict]``.

        Returns:
            ``BapiRunResult`` with success flag, return messages, and raw data.
        """
        import pyrfc

        conn = None
        try:
            conn = self._connect()

            # Fetch EXID map and coerce string values to correct Python types
            try:
                meta = conn.call("RFC_GET_FUNCTION_INTERFACE", FUNCNAME=func_name.upper())
                exid_map = {
                    str(row.get("PARAMETER") or "").strip(): str(row.get("EXID") or "").strip()
                    for row in (meta.get("PARAMS") or [])
                    if row.get("PARAMETER")
                }
                parameters = _coerce_params(parameters, exid_map)
            except Exception:
                pass  # proceed with original parameters if metadata fetch fails

            try:
                raw = conn.call(func_name.upper(), **parameters)
            except TypeError as exc:
                raise SapConnectionError(
                    f"Type mismatch calling {func_name!r}: {exc}. "
                    "Check that parameter values match the expected ABAP types."
                ) from exc
            except pyrfc.ABAPApplicationError as exc:
                raise SapConnectionError(f"ABAP application error in {func_name!r}: {exc}") from exc
            except pyrfc.ABAPRuntimeError as exc:
                raise SapConnectionError(f"ABAP runtime error in {func_name!r}: {exc}") from exc
            except pyrfc.LogonError as exc:
                raise SapConnectionError(
                    f"SAP logon failed ({self._config.safe_repr()}): {exc}"
                ) from exc
            except pyrfc.CommunicationError as exc:
                raise SapConnectionError(f"SAP communication error in {func_name!r}: {exc}") from exc
            except pyrfc.RFCError as exc:
                raise SapConnectionError(f"RFC error in {func_name!r}: {exc}") from exc

            return_messages = _extract_return_messages(raw)
            has_error = any(m.is_error for m in return_messages)
            sanitised = _sanitise(raw)

            return BapiRunResult(
                func_name=func_name.upper(),
                success=not has_error,
                return_messages=return_messages,
                data=sanitised,
            )

        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


# ── Helpers ────────────────────────────────────────────────────────────────


def _coerce_params(params: dict[str, Any], exid_map: dict[str, str]) -> dict[str, Any]:
    """Coerce string parameter values to the correct Python type based on EXID."""
    result = {}
    for name, value in params.items():
        exid = exid_map.get(name, "")
        if isinstance(value, str) and value:
            if exid in _INT_EXIDS:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass
            elif exid in _FLOAT_EXIDS:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    pass
        result[name] = value
    return result


def _extract_return_messages(raw: dict) -> list[BapiReturnMessage]:
    for key in _RETURN_KEYS:
        if key in raw and isinstance(raw[key], (list, tuple)):
            return [
                BapiReturnMessage(
                    type=str(row.get("TYPE") or ""),
                    id=str(row.get("ID") or ""),
                    number=str(row.get("NUMBER") or ""),
                    message=str(row.get("MESSAGE") or ""),
                    parameter=str(row.get("PARAMETER") or ""),
                    row=int(row.get("ROW") or 0),
                    field_name=str(row.get("FIELD") or ""),
                    system=str(row.get("SYSTEM") or ""),
                )
                for row in raw[key]
                if row
            ]
    return []


def _sanitise(obj: Any) -> Any:
    """Recursively convert non-JSON-serialisable values to strings."""
    if isinstance(obj, dict):
        return {k: _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitise(i) for i in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
