"""SAP RFC connection configuration.

Reads connection parameters from environment variables.  A ``.env`` file in
the project root is loaded automatically (``override=False``), so real
environment variables always take precedence over ``.env`` values.

Two connection types are supported (``SAP_CONN_TYPE``):
  direct      – single application server via SAP_HOST + SAP_SYSNR
  msgserver   – load-balanced via SAP_MSHOST + SAP_MSSERV + SAP_SYSID

Two authentication modes are supported (``SAP_AUTH_MODE``):
  snc         – Windows SNC/SSO via sapcrypto, no password stored (default)
  password    – explicit SAP_USER / SAP_PASSWORD
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv(override=False)

_AUTH_SNC = "snc"
_AUTH_PASSWORD = "password"
_VALID_AUTH = (_AUTH_SNC, _AUTH_PASSWORD)

_CONN_DIRECT = "direct"
_CONN_MSGSERVER = "msgserver"
_VALID_CONN = (_CONN_DIRECT, _CONN_MSGSERVER)


@dataclass
class SapConfig:
    """Immutable SAP connection configuration."""

    auth_mode: str
    conn_type: str

    # direct connection
    host: str = ""
    sysnr: str = ""

    # msgserver connection
    mshost: str = ""
    msserv: str = ""
    sysid: str = ""
    group: str = "SPACE"

    # shared
    client: str = ""
    lang: str = "EN"

    # SNC
    snc_name: str = ""
    snc_qop: str = "9"

    # password auth
    user: str = ""
    _password: str = field(default="", repr=False)

    # ------------------------------------------------------------------ #

    @classmethod
    def from_env(cls) -> SapConfig:
        """Build a SapConfig from environment variables.

        Raises:
            RuntimeError: if a required variable is missing or an
                          auth_mode / conn_type value is invalid.
        """
        auth_mode = os.environ.get("SAP_AUTH_MODE", _AUTH_SNC).strip().lower()
        if auth_mode not in _VALID_AUTH:
            raise RuntimeError(
                f"SAP_AUTH_MODE must be one of {_VALID_AUTH!r}, got {auth_mode!r}"
            )

        conn_type = os.environ.get("SAP_CONN_TYPE", _CONN_DIRECT).strip().lower()
        if conn_type not in _VALID_CONN:
            raise RuntimeError(
                f"SAP_CONN_TYPE must be one of {_VALID_CONN!r}, got {conn_type!r}"
            )

        client = _require("SAP_CLIENT")
        lang = os.environ.get("SAP_LANG", "EN").strip() or "EN"
        group = os.environ.get("SAP_GROUP", "SPACE").strip() or "SPACE"

        cfg = cls(
            auth_mode=auth_mode,
            conn_type=conn_type,
            client=client,
            lang=lang,
            group=group,
        )

        if conn_type == _CONN_DIRECT:
            object.__setattr__(cfg, "host", _require("SAP_HOST"))
            object.__setattr__(cfg, "sysnr", _require("SAP_SYSNR"))
        else:
            object.__setattr__(cfg, "mshost", _require("SAP_MSHOST"))
            object.__setattr__(cfg, "msserv", _require("SAP_MSSERV"))
            object.__setattr__(cfg, "sysid", _require("SAP_SYSID"))

        if auth_mode == _AUTH_SNC:
            object.__setattr__(cfg, "snc_name", _require("SAP_SNC_NAME"))
            object.__setattr__(
                cfg,
                "snc_qop",
                os.environ.get("SAP_SNC_QOP", "9").strip() or "9",
            )
        else:
            object.__setattr__(cfg, "user", _require("SAP_USER"))
            object.__setattr__(cfg, "_password", _require("SAP_PASSWORD"))

        return cfg

    @classmethod
    def from_profile(cls, profile: dict) -> "SapConfig":
        """Build a SapConfig from a profile dict, falling back to env vars.

        Keys in *profile* take precedence over the current environment; any
        key absent from *profile* falls back to the corresponding env var.
        Non-connection metadata keys (``label``, ``description``) are ignored.
        """

        def _get(key: str, default: str = "") -> str:
            return str(profile.get(key, os.environ.get(key, default))).strip()

        def _require_p(key: str) -> str:
            val = str(profile.get(key, os.environ.get(key, ""))).strip()
            if not val:
                raise RuntimeError(
                    f"Required key {key!r} is not set in profile or environment."
                )
            return val

        auth_mode = _get("SAP_AUTH_MODE", _AUTH_SNC).lower()
        if auth_mode not in _VALID_AUTH:
            raise RuntimeError(
                f"SAP_AUTH_MODE must be one of {_VALID_AUTH!r}, got {auth_mode!r}"
            )

        conn_type = _get("SAP_CONN_TYPE", _CONN_DIRECT).lower()
        if conn_type not in _VALID_CONN:
            raise RuntimeError(
                f"SAP_CONN_TYPE must be one of {_VALID_CONN!r}, got {conn_type!r}"
            )

        client = _require_p("SAP_CLIENT")
        lang = _get("SAP_LANG", "EN") or "EN"
        group = _get("SAP_GROUP", "SPACE") or "SPACE"

        cfg = cls(
            auth_mode=auth_mode,
            conn_type=conn_type,
            client=client,
            lang=lang,
            group=group,
        )

        if conn_type == _CONN_DIRECT:
            object.__setattr__(cfg, "host", _require_p("SAP_HOST"))
            object.__setattr__(cfg, "sysnr", _require_p("SAP_SYSNR"))
        else:
            object.__setattr__(cfg, "mshost", _require_p("SAP_MSHOST"))
            object.__setattr__(cfg, "msserv", _require_p("SAP_MSSERV"))
            object.__setattr__(cfg, "sysid", _require_p("SAP_SYSID"))

        if auth_mode == _AUTH_SNC:
            object.__setattr__(cfg, "snc_name", _require_p("SAP_SNC_NAME"))
            object.__setattr__(
                cfg,
                "snc_qop",
                _get("SAP_SNC_QOP", "9") or "9",
            )
        else:
            object.__setattr__(cfg, "user", _require_p("SAP_USER"))
            object.__setattr__(cfg, "_password", _require_p("SAP_PASSWORD"))

        return cfg

    def to_pyrfc_params(self) -> dict:
        """Return kwargs for ``pyrfc.Connection()``.

        The dict may contain a password — never log it directly.
        """
        params: dict = {"client": self.client, "lang": self.lang}

        if self.conn_type == _CONN_DIRECT:
            params.update({"ashost": self.host, "sysnr": self.sysnr})
        else:
            params.update(
                {
                    "mshost": self.mshost,
                    "msserv": self.msserv,
                    "sysid": self.sysid,
                    "group": self.group,
                }
            )

        if self.auth_mode == _AUTH_SNC:
            params.update(
                {
                    "snc_partnername": self.snc_name,
                    "snc_qop": self.snc_qop,
                    "snc_sso": "1",
                }
            )
        else:
            params.update({"user": self.user, "passwd": self._password})

        return params

    def safe_repr(self) -> str:
        """Log-safe representation (no passwords or SNC keys)."""
        if self.conn_type == _CONN_DIRECT:
            conn = f"host={self.host!r}, sysnr={self.sysnr!r}"
        else:
            conn = (
                f"mshost={self.mshost!r}, msserv={self.msserv!r}, "
                f"sysid={self.sysid!r}, group={self.group!r}"
            )

        auth = f"snc_qop={self.snc_qop!r}" if self.auth_mode == _AUTH_SNC else f"user={self.user!r}"
        return f"SapConfig(mode={self.auth_mode}, conn={self.conn_type}, {conn}, client={self.client!r}, {auth})"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Required environment variable {name!r} is not set or empty."
        )
    return value
