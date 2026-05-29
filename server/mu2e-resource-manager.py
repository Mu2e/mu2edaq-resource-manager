#!/usr/bin/env python3
"""Mu2e DAQ Resource Manager Server"""

import argparse
import os
import sys

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Optional

# Allow running from the server/ directory or from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import Resource, ResourceIdentifier, ReservationRequest, ReleaseRequest, ServerStatus
from resource_manager import ResourceManager
from auth import Principal, configure_auth, require_principal, truthy

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB_DIR = os.path.join(_HERE, "..", "web")
_DEFAULT_CONFIG = os.path.join(_HERE, "..", "config", "resources.yaml")
_DEFAULT_STATE = os.path.join(_HERE, "..", "config", "state.json")
_DEFAULT_AUTH_CONFIG = os.path.join(_HERE, "..", "config", "auth.yaml")

# Load environment variables from a .env file at the project root, if present.
# Variables already set in the real environment take precedence.
try:
    from dotenv import load_dotenv

    load_dotenv(os.environ.get("RM_ENV_FILE", os.path.join(_HERE, "..", ".env")))
except ImportError:
    pass

app = FastAPI(
    title="Mu2e DAQ Resource Manager",
    version="1.0.0",
    description="Manages hardware resources distributed across Mu2e DAQ nodes",
)

# Serve static assets (CSS, JS)
_static_dir = os.path.join(_WEB_DIR, "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Global resource manager instance — replaced by startup args when run as __main__
rm: ResourceManager = None  # type: ignore


# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_ui():
    index = os.path.join(_WEB_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Mu2e DAQ Resource Manager — web UI not found"}


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.get("/api/resources", response_model=List[Resource], tags=["resources"])
async def list_resources(status: Optional[str] = Query(None, pattern="^(available|reserved)$")):
    """List all resources, optionally filtered by status."""
    return rm.list_resources(status=status)


@app.get("/api/resources/{resource_class}/{name}/{enumerator}", response_model=Resource, tags=["resources"])
async def get_resource(resource_class: str, name: str, enumerator: str):
    """Get a specific resource by class, name, and enumerator."""
    resource = rm.get_resource(resource_class, name, enumerator)
    if resource is None:
        raise HTTPException(
            status_code=404,
            detail=f"Resource '{resource_class}:{name}:{enumerator}' not found",
        )
    return resource


@app.post("/api/reserve", tags=["reservations"])
async def reserve_resources(
    request: ReservationRequest,
    principal: Principal = Depends(require_principal),
):
    """Reserve one or more resources for the authenticated principal.

    The resources are owned by the authenticated identity; any ``client_id``
    in the request body is ignored. Returns 409 if any resource is already
    reserved or does not exist. All-or-nothing: no resources are reserved if
    any validation fails.
    """
    success, message, resources = rm.reserve_resources(
        principal.name, request.resources, who=request.who
    )
    if not success:
        raise HTTPException(
            status_code=409,
            detail={
                "message": message,
                "resources": [r.model_dump() for r in resources],
            },
        )
    return {"message": message, "resources": resources}


@app.post("/api/release", tags=["reservations"])
async def release_resources(
    request: ReleaseRequest,
    principal: Principal = Depends(require_principal),
):
    """Release one or more resources.

    Clients may only release resources they own; operators may release any.
    """
    success, message = rm.release_resources(
        principal.name, request.resources, operator_override=principal.is_operator
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@app.delete("/api/clients/{client_id}/resources", tags=["reservations"])
async def release_all_for_client(
    client_id: str,
    principal: Principal = Depends(require_principal),
):
    """Release all resources held by a client.

    A client may only release its own resources; an operator may release for
    any client.
    """
    if not principal.is_operator and client_id != principal.name:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to release resources for another client",
        )
    count = rm.release_all_for_client(client_id)
    return {"message": f"Released {count} resource(s) for client '{client_id}'", "count": count}


@app.get("/api/status", response_model=ServerStatus, tags=["server"])
async def get_status():
    """Get server summary: total, available, and reserved resource counts."""
    return rm.get_status()


@app.get("/api/whoami", tags=["server"])
async def whoami(principal: Principal = Depends(require_principal)):
    """Return the authenticated principal and role for the supplied token."""
    return {"principal": principal.name, "role": principal.role}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Mu2e DAQ Resource Manager Server")
    parser.add_argument(
        "--host",
        default=os.environ.get("RM_HOST", "127.0.0.1"),
        help="Bind host (default: 127.0.0.1; set 0.0.0.0 to expose on all interfaces)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("RM_PORT", "8080")),
        help="Bind port (default: 8080)",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("RM_CONFIG", _DEFAULT_CONFIG),
        help="Path to resources YAML config",
    )
    parser.add_argument(
        "--state",
        default=os.environ.get("RM_STATE", _DEFAULT_STATE),
        help="Path to reservation state JSON file",
    )
    parser.add_argument(
        "--auth-config",
        default=os.environ.get("RM_AUTH_CONFIG", _DEFAULT_AUTH_CONFIG),
        help="Path to the auth token YAML config",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        default=truthy(os.environ.get("RM_AUTH_DISABLED")),
        help="Disable authentication (trusted/local use only)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    args = parse_args()
    rm = ResourceManager(args.config, args.state)
    configure_auth(args.auth_config, disabled=args.no_auth)
    print(f"Loaded config: {args.config}")
    print(f"State file:    {args.state}")
    uvicorn.run(app, host=args.host, port=args.port)
else:
    # When imported (e.g., by uvicorn directly), use defaults
    rm = ResourceManager(
        os.environ.get("RM_CONFIG", _DEFAULT_CONFIG),
        os.environ.get("RM_STATE", _DEFAULT_STATE),
    )
    configure_auth(
        os.environ.get("RM_AUTH_CONFIG", _DEFAULT_AUTH_CONFIG),
        disabled=truthy(os.environ.get("RM_AUTH_DISABLED")),
    )
