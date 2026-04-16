import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserDevice
from ..schemas import DeviceHeartbeatRequest, UserStatusResponse
from ..dependencies import get_current_user

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
