import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_audit, record_security_event
from ..database import get_db
from ..models import SecurityEvent, User, UserDevice, UserSession
from ..schemas import (
    DeviceHeartbeatRequest,
    SecuritySettingsResponse,
    SecuritySettingsUpdate,
    UserSessionResponse,
    UserStatusResponse,
)
from ..dependencies import get_current_user
from ..security import now_utc

router = APIRouter(prefix="/api/user", tags=["User"])


@router.get("/status", response_model=UserStatusResponse)
def get_user_status(current_user: User = Depends(get_current_user)):
    # Premium system removed — ads are mandatory for all users.
    return UserStatusResponse(
        is_premium=False,
        is_trial_active=False,
        show_ads=True,
        premium_until=None,
        trial_ends_at=None,
    )


@router.post("/device-heartbeat", status_code=204)
def device_heartbeat(
    payload: DeviceHeartbeatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    platform = (payload.platform or "").strip().lower()
    if platform not in {"web", "android", "ios"}:
        raise HTTPException(status_code=422, detail="platform must be web, android or ios")

    row = (
        db.query(UserDevice)
        .filter(UserDevice.user_id == current_user.id, UserDevice.platform == platform)
        .first()
    )
    now = datetime.datetime.now(datetime.timezone.utc)

    if not row:
        row = UserDevice(
            user_id=current_user.id,
            platform=platform,
            app_version=payload.app_version,
            last_seen_at=now,
        )
        db.add(row)
    else:
        row.last_seen_at = now
        row.app_version = payload.app_version

    db.commit()


@router.get("/security/settings", response_model=SecuritySettingsResponse)
def get_security_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == current_user.id)
        .order_by(UserSession.created_at.desc())
        .limit(20)
        .all()
    )
    events = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.user_id == current_user.id)
        .order_by(SecurityEvent.created_at.desc())
        .limit(20)
        .all()
    )
    return SecuritySettingsResponse(
        two_factor_enabled=bool(current_user.two_factor_enabled),
        sessions=[UserSessionResponse.model_validate(s) for s in sessions],
        recent_events=events,
    )


@router.put("/security/settings", response_model=SecuritySettingsResponse)
def update_security_settings(
    payload: SecuritySettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.two_factor_enabled = payload.two_factor_enabled
    record_audit(
        db,
        action="user.security_settings_update",
        actor_user=current_user,
        target_type="user",
        target_id=str(current_user.id),
        metadata={"two_factor_enabled": payload.two_factor_enabled},
    )
    db.commit()
    return get_security_settings(current_user=current_user, db=db)


@router.post("/security/sessions/{session_id}/revoke", status_code=204)
def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    row.is_active = False
    row.revoked_at = now_utc()
    record_audit(
        db,
        action="user.session_revoke",
        actor_user=current_user,
        target_type="session",
        target_id=str(session_id),
    )
    db.commit()


@router.post("/security/sessions/revoke-all", status_code=204)
def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = now_utc()
    affected = (
        db.query(UserSession)
        .filter(UserSession.user_id == current_user.id, UserSession.is_active.is_(True))
        .update(
            {
                UserSession.is_active: False,
                UserSession.revoked_at: now,
            },
            synchronize_session=False,
        )
    )

    record_audit(
        db,
        action="user.session_revoke_all",
        actor_user=current_user,
        target_type="user",
        target_id=str(current_user.id),
        metadata={"affected_sessions": affected},
    )
    record_security_event(
        db,
        event_type="sessions_revoked_all",
        user=current_user,
        severity="warning",
        details=f"Revoked active sessions: {affected}",
    )
    db.commit()
