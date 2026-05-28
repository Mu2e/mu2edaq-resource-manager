"""Authentication and authorization for the resource manager.

A bearer-token backend is implemented now. The endpoints depend only on
``require_principal()``, so an OIDC/SSO backend can be added later (see
``OIDCAuthBackend`` stub) without changing any endpoint logic.

Roles:
- ``client``   — may reserve/release only resources it owns.
- ``operator`` — may release any resource and release-all for any client.
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional

import yaml
from fastapi import Header, HTTPException

ROLE_CLIENT = "client"
ROLE_OPERATOR = "operator"


@dataclass(frozen=True)
class Principal:
    """The authenticated identity that owns/authorizes an operation."""

    name: str
    role: str = ROLE_CLIENT

    @property
    def is_operator(self) -> bool:
        return self.role == ROLE_OPERATOR


def truthy(value: Optional[str]) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class TokenAuthBackend:
    """Resolves bearer tokens to principals from a YAML config file."""

    def __init__(self, config_path: Optional[str] = None):
        self._tokens: Dict[str, Principal] = {}
        self.config_path = config_path
        if config_path and os.path.exists(config_path):
            self._load(config_path)

    def _load(self, path: str) -> None:
        with open(path) as f:
            cfg = yaml.safe_load(f) or {}
        auth = (cfg.get("auth") or {})
        for entry in (auth.get("tokens") or []):
            token = entry.get("token")
            principal = entry.get("principal")
            role = entry.get("role", ROLE_CLIENT)
            if token and principal:
                self._tokens[str(token)] = Principal(name=str(principal), role=str(role))

    @property
    def token_count(self) -> int:
        return len(self._tokens)

    def principal_for(self, token: str) -> Optional[Principal]:
        return self._tokens.get(token)


class OIDCAuthBackend:  # pragma: no cover - future SSO integration point
    """Placeholder for a future Fermilab/Google OIDC backend.

    Implement ``principal_for_request`` to validate an OIDC bearer/JWT and map
    it to a Principal; then wire it into ``require_principal``.
    """

    def principal_for(self, token: str) -> Optional[Principal]:
        raise NotImplementedError("OIDC auth backend is not implemented yet")


# Module-level state, configured once at startup via configure_auth().
_backend: Optional[TokenAuthBackend] = None
_auth_disabled: bool = False


def configure_auth(config_path: Optional[str], disabled: bool) -> TokenAuthBackend:
    """Initialize the auth backend. Called once at server startup."""
    global _backend, _auth_disabled
    _auth_disabled = disabled
    _backend = TokenAuthBackend(config_path)

    if disabled:
        print(
            "WARNING: authentication is DISABLED (RM_AUTH_DISABLED); "
            "state-changing endpoints are open to any caller.",
            file=sys.stderr,
        )
    elif _backend.token_count == 0:
        print(
            "WARNING: authentication is enabled but no tokens are configured; "
            "reserve/release/release-all will reject all callers with 401. "
            f"Add tokens to {config_path or 'config/auth.yaml'} "
            "(see config/auth.example.yaml) or set RM_AUTH_DISABLED=1 for "
            "trusted/local use.",
            file=sys.stderr,
        )
    return _backend


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def require_principal(authorization: Optional[str] = Header(default=None)) -> Principal:
    """FastAPI dependency: resolve the caller's Principal or raise 401.

    When auth is explicitly disabled, returns a synthetic operator principal so
    the API stays usable in trusted/local deployments.
    """
    if _auth_disabled:
        return Principal(name="anonymous", role=ROLE_OPERATOR)

    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    principal = _backend.principal_for(token) if _backend else None
    if principal is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal
