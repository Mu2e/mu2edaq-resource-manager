"""Request validation tests for empty resource lists (issue #2)."""

AUTH = {"Authorization": "Bearer tok-p1"}


def test_empty_reserve_list_rejected(client_factory):
    c = client_factory()
    r = c.post("/api/reserve", json={"resources": []}, headers=AUTH)
    assert r.status_code == 422


def test_empty_release_list_rejected(client_factory):
    c = client_factory()
    r = c.post("/api/release", json={"resources": []}, headers=AUTH)
    assert r.status_code == 422


def test_valid_reserve_accepted(client_factory):
    c = client_factory()
    r = c.post(
        "/api/reserve",
        json={"resources": [{"resource_class": "DTC", "name": "DTC", "enumerator": "01"}]},
        headers=AUTH,
    )
    assert r.status_code == 200
