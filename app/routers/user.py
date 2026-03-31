from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserStatusResponse
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/user", tags=["User"])

@router.get("/status", response_model=UserStatusResponse)
def get_user_status(current_user: User = Depends(get_current_user)):
    # Premium system is removed, ads are mandatory for everyone.
    return UserStatusResponse(
        is_premium=False,
        is_trial_active=False,
        show_ads=True,
        premium_until=None,
        trial_ends_at=None
    )

@router.post("/upgrade")
def upgrade_user(current_user: User = Depends(get_current_user)):
    return {"message": "Premium system is currently disabled.", "success": False}
