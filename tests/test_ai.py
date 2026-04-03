import datetime
from unittest.mock import MagicMock, patch

from app.models import User
from app.auth_utils import create_access_token


def _auth_headers(email="test@example.com"):
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _create_user(db, email="test@example.com"):
    user = User(email=email, google_id="uid-123", is_premium=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_astrology_requires_auth(client):
    resp = client.post("/api/ai/astrology", json={"sign": "Koç"})
    assert resp.status_code == 401


def test_astrology_invalid_sign(client, db):
    _create_user(db)
    with patch("app.routers.ai.genai"):
        resp = client.post(
            "/api/ai/astrology",
            json={"sign": "InvalidSign"},
            headers=_auth_headers(),
        )
    assert resp.status_code == 422


def test_astrology_success(client, db):
    _create_user(db)
    mock_response = MagicMock()
    mock_response.text = "Bugün enerjin yüksek olacak..."

    with patch("app.routers.ai.genai") as mock_genai:
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response
        resp = client.post(
            "/api/ai/astrology",
            json={"sign": "Koç"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "Bugün" in data["prediction"]


def test_astrology_daily_rate_limit(client, db):
    user = _create_user(db)
    user.last_ai_query_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    resp = client.post(
        "/api/ai/astrology",
        json={"sign": "Koç"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 429


def test_astrology_question_too_long(client, db):
    _create_user(db)
    resp = client.post(
        "/api/ai/astrology",
        json={"sign": "Koç", "question": "x" * 501},
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
