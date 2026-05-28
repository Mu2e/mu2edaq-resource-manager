"""Pytest fixtures: load the server app with a fresh, isolated config.

The server entry point file has a hyphenated name, so it is loaded via
importlib from its path rather than a plain import.
"""

import importlib.util
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_FILE = ROOT / "server" / "mu2e-resource-manager.py"

RESOURCES_YAML = """\
resources:
  - class: DTC
    name: DTC
    enumerator: "01"
    location:
      node: node01
      user: daq
      ports: [2000]
  - class: CFO
    name: CFO
    enumerator: "01"
    location:
      node: node02
      user: daq
      ports: [3000]
"""

AUTH_YAML = """\
auth:
  tokens:
    - token: tok-p1
      principal: partition1
      role: client
    - token: tok-p2
      principal: partition2
      role: client
    - token: tok-op
      principal: operator
      role: operator
"""


def _load_server(tmp_path, *, auth_yaml=AUTH_YAML, disabled=False):
    config = tmp_path / "resources.yaml"
    config.write_text(RESOURCES_YAML)
    os.environ["RM_CONFIG"] = str(config)
    os.environ["RM_STATE"] = str(tmp_path / "state.json")

    if disabled:
        os.environ["RM_AUTH_DISABLED"] = "1"
        os.environ.pop("RM_AUTH_CONFIG", None)
    else:
        os.environ.pop("RM_AUTH_DISABLED", None)
        auth = tmp_path / "auth.yaml"
        auth.write_text(auth_yaml)
        os.environ["RM_AUTH_CONFIG"] = str(auth)

    # Force a fresh import so module-level state (rm, auth backend) is rebuilt.
    for name in ("rm_server", "resource_manager", "auth", "models"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(ROOT / "server"))

    spec = importlib.util.spec_from_file_location("rm_server", SERVER_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def client_factory(tmp_path):
    """Return a factory producing a configured FastAPI TestClient."""
    from fastapi.testclient import TestClient

    def make(**kwargs):
        mod = _load_server(tmp_path, **kwargs)
        return TestClient(mod.app)

    return make
