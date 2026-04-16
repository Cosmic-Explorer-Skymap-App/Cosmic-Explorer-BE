from app.auth_utils import create_access_token
from app.models import BugReport, User


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_social_content_flow(client, db):
    admin = User(email="social-admin@example.com", google_id="g-social-admin", is_admin=True)
    db.add(admin)
    db.commit()

    headers = _auth_header(admin.email)

    conn_resp = client.post(
        "/api/admin/social/connections",
        headers=headers,
        json={
            "platform": "instagram",
            "account_name": "cosmic_explorer_official",
        },
    )
    assert conn_resp.status_code == 201
    connection_id = conn_resp.json()["id"]

    content_resp = client.post(
        "/api/admin/social/contents",
        headers=headers,
        json={
            "platform": "instagram",
            "connection_id": connection_id,
            "title": "Daily Sky",
            "body": "Tonight we observe Orion.",
            "status": "scheduled",
        },
    )
    assert content_resp.status_code == 201

    summary_resp = client.get("/api/admin/social/analytics/summary", headers=headers)
    assert summary_resp.status_code == 200
    assert summary_resp.json()["total_contents"] == 1


def test_system_and_users_panel(client, db):
    admin = User(email="ops-admin@example.com", google_id="g-ops-admin", is_admin=True, is_premium=True)
    regular = User(email="regular@example.com", google_id="g-regular", is_admin=False, is_premium=False)
    db.add_all([admin, regular])
    db.commit()
    db.refresh(regular)

    bug = BugReport(
        user_id=regular.id,
        source_platform="android",
        severity="high",
        title="Crash",
        description="App crashes on launch",
        status="open",
    )
    db.add(bug)
    db.commit()

    headers = _auth_header(admin.email)
    system_resp = client.get("/api/admin/system/status", headers=headers)
    assert system_resp.status_code == 200
    assert "open_bug_reports" in system_resp.json()

    users_resp = client.get("/api/admin/users/panel", headers=headers)
    assert users_resp.status_code == 200
    users_data = users_resp.json()
    assert users_data["total_users"] == 2
    assert users_data["by_tier"]["premium"] == 1


def test_finance_panel_flow(client, db):
    admin = User(email="finance-admin@example.com", google_id="g-finance-admin", is_admin=True)
    db.add(admin)
    db.commit()

    headers = _auth_header(admin.email)

    inc = client.post(
        "/api/admin/finance/entries",
        headers=headers,
        json={"entry_type": "income", "category": "sponsorship", "amount": 150000},
    )
    exp = client.post(
        "/api/admin/finance/entries",
        headers=headers,
        json={"entry_type": "expense", "category": "ads", "amount": 50000},
    )
    assert inc.status_code == 201
    assert exp.status_code == 201

    summary_resp = client.get("/api/admin/finance/summary?days=30", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_income"] == 150000
    assert summary["total_expense"] == 50000
    assert summary["net"] == 100000
