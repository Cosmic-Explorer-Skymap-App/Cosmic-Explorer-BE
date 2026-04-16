from app.auth_utils import create_access_token
from app.models import Post, SupportMessage, User


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_admin_overview_requires_auth(client):
    resp = client.get("/api/admin/overview")
    assert resp.status_code == 401


def test_admin_overview_forbidden_for_non_admin(client, db):
    user = User(email="user@example.com", google_id="g-user-1", is_admin=False)
    db.add(user)
    db.commit()

    resp = client.get("/api/admin/overview", headers=_auth_header(user.email))
    assert resp.status_code == 403


def test_admin_overview_success_for_admin(client, db):
    admin_user = User(email="admin@example.com", google_id="g-admin-1", is_admin=True, is_premium=True)
    regular_user = User(email="member@example.com", google_id="g-member-1", is_admin=False)
    db.add_all([admin_user, regular_user])
    db.commit()
    db.refresh(admin_user)

    post = Post(user_id=admin_user.id, image_url="/media/p1.jpg", title="Nebula", caption="First")
    open_ticket = SupportMessage(
        user_id=admin_user.id,
        full_name="Admin",
        email="admin@example.com",
        subject="Issue",
        message="Open ticket",
        status="open",
    )
    pending_ticket = SupportMessage(
        user_id=admin_user.id,
        full_name="Admin",
        email="admin@example.com",
        subject="Issue 2",
        message="Pending ticket",
        status="pending",
    )
    closed_ticket = SupportMessage(
        user_id=regular_user.id,
        full_name="Member",
        email="member@example.com",
        subject="Resolved",
        message="Closed ticket",
        status="closed",
    )

    db.add_all([post, open_ticket, pending_ticket, closed_ticket])
    db.commit()

    resp = client.get("/api/admin/overview", headers=_auth_header(admin_user.email))
    assert resp.status_code == 200

    body = resp.json()
    assert body["total_users"] == 2
    assert body["premium_users"] == 1
    assert body["total_posts"] == 1
    assert body["open_reports"] == 2
    assert body["support"]["open"] == 1
    assert body["support"]["pending"] == 1
    assert body["support"]["closed"] == 1
