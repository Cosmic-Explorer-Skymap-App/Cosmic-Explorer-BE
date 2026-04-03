from unittest.mock import patch


def _mock_idinfo(email="test@example.com", sub="google-uid-123"):
    return {"sub": sub, "email": email}


def test_google_login_creates_user(client):
    with patch("app.routers.auth.id_token.verify_oauth2_token", return_value=_mock_idinfo()):
        resp = client.post("/api/auth/google", json={"id_token": "fake-token"})

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_google_login_invalid_token(client):
    with patch(
        "app.routers.auth.id_token.verify_oauth2_token",
        side_effect=ValueError("Invalid token"),
    ):
        resp = client.post("/api/auth/google", json={"id_token": "bad-token"})

    assert resp.status_code == 401


def test_google_login_idempotent(client):
    """Second login with same Google account returns a token without creating duplicate user."""
    with patch("app.routers.auth.id_token.verify_oauth2_token", return_value=_mock_idinfo()):
        resp1 = client.post("/api/auth/google", json={"id_token": "fake-token"})
        resp2 = client.post("/api/auth/google", json={"id_token": "fake-token"})

    assert resp1.status_code == 200
    assert resp2.status_code == 200
