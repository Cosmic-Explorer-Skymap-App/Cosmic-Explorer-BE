import datetime
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests

from ..audit import record_audit, record_security_event
from ..database import get_db
from ..models import LoginAttempt, User, UserSession
from ..schemas import GoogleLoginRequest, SessionStatusResponse, Token
from ..auth_utils import create_access_token
from ..security import client_ip, now_utc, require_rate_limit, user_agent
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_web_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
_server_client_id = os.getenv("GOOGLE_SERVER_CLIENT_ID", "")
ALLOWED_GOOGLE_CLIENT_IDS = [cid for cid in [_web_client_id, _server_client_id] if cid]


def _cookie_domain() -> str | None:
    domain = os.getenv("COOKIE_DOMAIN", "").strip()
    return domain or None


def _cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "true").lower() == "true"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="ce_token",
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=60 * 60 * 12,
        domain=_cookie_domain(),
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie("ce_token", domain=_cookie_domain(), path="/")

@router.post("/google", response_model=Token)
def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    require_rate_limit(request, scope="auth_google", limit=10, window_seconds=60)

    login_email = None
    login_user = None
    failure_reason = None

    # Verify Google ID Token against all registered client IDs (web + mobile)
    idinfo = None
    last_error = None
    for client_id in ALLOWED_GOOGLE_CLIENT_IDS:
        try:
            idinfo = id_token.verify_oauth2_token(payload.id_token, requests.Request(), client_id)
            break
        except ValueError as e:
            last_error = e

    if idinfo is None:
        failure_reason = f"invalid_google_token:{last_error}"
        db.add(
            LoginAttempt(
                email=None,
                user_id=None,
                ip_address=client_ip(request),
                user_agent=user_agent(request),
                success=False,
                failure_reason=failure_reason[:200],
                created_at=now_utc(),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID Token: {str(last_error)}"
        )

    userid = idinfo['sub']
    email = idinfo['email']
    login_email = email

    # Check if user exists in DB
    user = db.query(User).filter(User.email == email).first()

    google_picture = idinfo.get("picture")

    if not user:
        # Create new user
        user = User(
            email=email,
            google_id=userid,
            is_premium=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_id:
        # Link google_id if email matches but Google login wasn't used before
        user.google_id = userid
        db.commit()

    login_user = user

    # Sync Google profile picture to UserProfile if not already set
    if google_picture and user.profile and not user.profile.avatar_url:
        user.profile.avatar_url = google_picture
        db.commit()

    # Create JWT Access Token
    jti = uuid.uuid4().hex
    access_token = create_access_token(data={"sub": user.email, "jti": jti})

    previous_session = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id, UserSession.is_active.is_(True))
        .order_by(UserSession.created_at.desc())
        .first()
    )

    session = UserSession(
        user_id=user.id,
        token_jti=jti,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        platform=(request.headers.get("x-client-platform") or "web")[:30].lower(),
        is_active=True,
        created_at=now_utc(),
        last_seen_at=now_utc(),
    )
    db.add(session)

    if previous_session and previous_session.ip_address != session.ip_address:
        record_security_event(
            db,
            event_type="new_login_location",
            user=user,
            severity="warning",
            details=f"Previous IP: {previous_session.ip_address}, new IP: {session.ip_address}",
            request=request,
        )

    db.add(
        LoginAttempt(
            email=login_email,
            user_id=login_user.id if login_user else None,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            success=True,
            failure_reason=None,
            created_at=now_utc(),
        )
    )
    record_audit(
        db,
        action="auth.google_login",
        actor_user=user,
        request=request,
        target_type="user",
        target_id=str(user.id),
    )
    db.commit()

    _set_auth_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = request.cookies.get("ce_token")
    if token:
        from jose import jwt
        from ..auth_utils import ALGORITHM, SECRET_KEY

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            if jti:
                row = db.query(UserSession).filter(UserSession.token_jti == jti).first()
                if row and row.is_active:
                    row.is_active = False
                    row.revoked_at = now_utc()
        except Exception:
            pass

    record_audit(
        db,
        action="auth.logout",
        actor_user=current_user,
        request=request,
        target_type="user",
        target_id=str(current_user.id),
    )
    db.commit()
    _clear_auth_cookie(response)


@router.get("/session", response_model=SessionStatusResponse)
def session_status(current_user: User = Depends(get_current_user)):
    return {"authenticated": bool(current_user)}
