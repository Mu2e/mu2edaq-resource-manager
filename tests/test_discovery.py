"""Tests for UDP broadcast discovery."""

import importlib.util
import json
import pathlib
import socket

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_discovery():
    spec = importlib.util.spec_from_file_location(
        "discovery", ROOT / "server" / "discovery.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


discovery = _load_discovery()


def test_resolve_advertise_host_prefers_explicit():
    assert discovery.resolve_advertise_host("rm.fnal.gov", "0.0.0.0") == "rm.fnal.gov"


def test_resolve_advertise_host_uses_concrete_bind():
    assert discovery.resolve_advertise_host(None, "192.168.1.5") == "192.168.1.5"


def test_resolve_advertise_host_detects_when_wildcard():
    # No explicit host and a wildcard bind -> a concrete (non-empty) address.
    host = discovery.resolve_advertise_host(None, "0.0.0.0")
    assert host and host not in discovery._NON_ROUTABLE


@pytest.fixture
def responder():
    # Bind the responder on an ephemeral-ish high port on loopback.
    r = discovery.DiscoveryResponder(
        http_port=9999, discovery_port=18077, advertise_host="127.0.0.1"
    )
    r.start()
    yield r
    r.stop()


def _query(port, payload=discovery.DISCOVERY_MAGIC, timeout=2.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(payload, ("127.0.0.1", port))
        try:
            data, _ = s.recvfrom(1024)
            return data
        except socket.timeout:
            return None
    finally:
        s.close()


def test_responder_replies_to_magic(responder):
    # Give the thread a moment to bind.
    import time
    time.sleep(0.3)
    data = _query(18077)
    assert data is not None
    msg = json.loads(data)
    assert msg["service"] == "mu2e-resource-manager"
    assert msg["host"] == "127.0.0.1"
    assert msg["port"] == 9999


def test_responder_ignores_non_magic(responder):
    import time
    time.sleep(0.3)
    assert _query(18077, payload=b"not-the-magic") is None
