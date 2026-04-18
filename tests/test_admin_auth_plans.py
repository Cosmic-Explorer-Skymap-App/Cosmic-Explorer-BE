from app.models import AdminAccount


def _admin_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_founder_login_and_me(client, db):
    login_resp = client.post(
        "/api/admin/auth/login",
        json={"username": "Fathertkt", "password": "586363"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/admin/auth/me", headers=_admin_header(token))
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["username"] == "Fathertkt"
    assert body["is_founder"] is True


def test_founder_can_create_and_block_admin(client, db):
    login_resp = client.post(
        "/api/admin/auth/login",
        json={"username": "Fathertkt", "password": "586363"},
    )
    token = login_resp.json()["access_token"]
    headers = _admin_header(token)

    create_resp = client.post(
        "/api/admin/auth/accounts",
        headers=headers,
        json={
            "username": "ops-chief",
            "password": "secret-123",
            "display_name": "Ops Chief",
            "permissions": ["planning", "overview"],
        },
    )
    assert create_resp.status_code == 201
    account_id = create_resp.json()["id"]
    assert sorted(create_resp.json()["permissions"]) == ["overview", "planning"]

    block_resp = client.patch(f"/api/admin/auth/accounts/{account_id}/block", headers=headers)
    assert block_resp.status_code == 200
    assert block_resp.json()["is_active"] is False

    unblock_resp = client.patch(f"/api/admin/auth/accounts/{account_id}/unblock", headers=headers)
    assert unblock_resp.status_code == 200
    assert unblock_resp.json()["is_active"] is True


def test_admin_permissions_sync_and_access_control(client, db):
    founder_login = client.post(
        "/api/admin/auth/login",
        json={"username": "Fathertkt", "password": "586363"},
    )
    founder_headers = _admin_header(founder_login.json()["access_token"])

    create_resp = client.post(
        "/api/admin/auth/accounts",
        headers=founder_headers,
        json={
            "username": "timeline-operator",
            "password": "secret-456",
            "display_name": "Timeline Operator",
            "permissions": ["planning"],
        },
    )
    assert create_resp.status_code == 201
    operator_id = create_resp.json()["id"]
    assert create_resp.json()["permissions"] == ["planning"]

    operator_login = client.post(
        "/api/admin/auth/login",
        json={"username": "timeline-operator", "password": "secret-456"},
    )
    assert operator_login.status_code == 200
    operator_headers = _admin_header(operator_login.json()["access_token"])

    me_resp = client.get("/api/admin/auth/me", headers=operator_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["permissions"] == ["planning"]

    overview_resp = client.get("/api/admin/overview", headers=operator_headers)
    assert overview_resp.status_code == 403

    plans_resp = client.get("/api/admin/plans", headers=operator_headers)
    assert plans_resp.status_code == 200

    update_permissions_resp = client.patch(
        f"/api/admin/auth/accounts/{operator_id}/permissions",
        headers=founder_headers,
        json={"permissions": ["planning", "overview", "system"]},
    )
    assert update_permissions_resp.status_code == 200
    assert sorted(update_permissions_resp.json()["permissions"]) == ["overview", "planning", "system"]

    operator_login2 = client.post(
        "/api/admin/auth/login",
        json={"username": "timeline-operator", "password": "secret-456"},
    )
    operator_headers2 = _admin_header(operator_login2.json()["access_token"])

    overview_resp2 = client.get("/api/admin/overview", headers=operator_headers2)
    assert overview_resp2.status_code == 200


def test_planning_item_crud(client, db):
    login_resp = client.post(
        "/api/admin/auth/login",
        json={"username": "Fathertkt", "password": "586363"},
    )
    headers = _admin_header(login_resp.json()["access_token"])

    create_resp = client.post(
        "/api/admin/plans",
        headers=headers,
        json={
            "title": "MVP Launch",
            "details": "Coordinate launch window, QA, and content rollout.",
            "start_at": "2026-04-18T08:00:00Z",
            "end_at": "2026-04-18T12:00:00Z",
            "color": "#7c5cff",
            "status": "planned",
        },
    )
    assert create_resp.status_code == 201
    plan_id = create_resp.json()["id"]

    list_resp = client.get("/api/admin/plans", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = client.put(
        f"/api/admin/plans/{plan_id}",
        headers=headers,
        json={"status": "in_progress", "details": "QA window in progress."},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "in_progress"

    delete_resp = client.delete(f"/api/admin/plans/{plan_id}", headers=headers)
    assert delete_resp.status_code == 204