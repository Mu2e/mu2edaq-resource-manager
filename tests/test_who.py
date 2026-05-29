"""Tests for the operator (Who) annotation, independent of owner."""

RES_DTC = {"resource_class": "DTC", "name": "DTC", "enumerator": "01"}
AUTH = {"Authorization": "Bearer tok-p1"}


def test_reserve_records_who_independent_of_owner(client_factory):
    c = client_factory()
    r = c.post("/api/reserve", json={"who": "Andrew", "resources": [RES_DTC]}, headers=AUTH)
    assert r.status_code == 200
    got = c.get("/api/resources/DTC/DTC/01").json()
    assert got["owner"] == "partition1"  # authenticated principal
    assert got["who"] == "Andrew"        # free-text annotation


def test_who_is_optional(client_factory):
    c = client_factory()
    c.post("/api/reserve", json={"resources": [RES_DTC]}, headers=AUTH)
    assert c.get("/api/resources/DTC/DTC/01").json()["who"] is None


def test_release_clears_who(client_factory):
    c = client_factory()
    c.post("/api/reserve", json={"who": "Andrew", "resources": [RES_DTC]}, headers=AUTH)
    c.post("/api/release", json={"resources": [RES_DTC]}, headers=AUTH)
    got = c.get("/api/resources/DTC/DTC/01").json()
    assert got["who"] is None and got["owner"] is None
