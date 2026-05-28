"""Auth/authz tests for state-changing endpoints (issue #1)."""

RES_DTC = {"resource_class": "DTC", "name": "DTC", "enumerator": "01"}


def _reserve(client, token, resources=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(
        "/api/reserve",
        json={"resources": resources or [RES_DTC]},
        headers=headers,
    )


def test_reserve_requires_token(client_factory):
    c = client_factory()
    assert _reserve(c, None).status_code == 401


def test_invalid_token_rejected(client_factory):
    c = client_factory()
    assert _reserve(c, "not-a-real-token").status_code == 401


def test_reserve_owner_is_principal_not_body_client_id(client_factory):
    c = client_factory()
    r = c.post(
        "/api/reserve",
        json={"client_id": "attacker", "resources": [RES_DTC]},
        headers={"Authorization": "Bearer tok-p1"},
    )
    assert r.status_code == 200
    assert c.get("/api/resources/DTC/DTC/01").json()["owner"] == "partition1"


def test_client_cannot_release_others_resource(client_factory):
    c = client_factory()
    assert _reserve(c, "tok-p1").status_code == 200
    r = c.post(
        "/api/release",
        json={"resources": [RES_DTC]},
        headers={"Authorization": "Bearer tok-p2"},
    )
    assert r.status_code == 400


def test_operator_can_release_any_resource(client_factory):
    c = client_factory()
    assert _reserve(c, "tok-p1").status_code == 200
    r = c.post(
        "/api/release",
        json={"resources": [RES_DTC]},
        headers={"Authorization": "Bearer tok-op"},
    )
    assert r.status_code == 200


def test_release_all_blocked_for_other_client(client_factory):
    c = client_factory()
    assert _reserve(c, "tok-p1").status_code == 200
    r = c.delete(
        "/api/clients/partition1/resources",
        headers={"Authorization": "Bearer tok-p2"},
    )
    assert r.status_code == 403


def test_release_all_allowed_for_operator(client_factory):
    c = client_factory()
    assert _reserve(c, "tok-p1").status_code == 200
    r = c.delete(
        "/api/clients/partition1/resources",
        headers={"Authorization": "Bearer tok-op"},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_read_endpoints_do_not_require_token(client_factory):
    c = client_factory()
    assert c.get("/api/status").status_code == 200
    assert c.get("/api/resources").status_code == 200


def test_auth_disabled_allows_unauthenticated_reserve(client_factory):
    c = client_factory(disabled=True)
    assert _reserve(c, None).status_code == 200
