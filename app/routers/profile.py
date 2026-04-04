import os
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserProfile, Follow
from ..schemas import UserProfileResponse, UserProfileUpdate, UsernameSetup
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/users", tags=["Profile"])

BASE_URL = os.getenv("BASE_URL", "")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,50}$")


def _build_profile_response(profile: UserProfile, current_user: User, db: Session) -> UserProfileResponse:
    is_following = False
    if current_user.id != profile.user_id:
        is_following = db.query(Follow).filter_by(
            follower_id=current_user.id,
            following_id=profile.user_id
        ).first() is not None
    return UserProfileResponse(
        user_id=profile.user_id,
        username=profile.username,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        follower_count=profile.follower_count,
        following_count=profile.following_count,
        post_count=profile.post_count,
        is_following=is_following,
    )


@router.post("/me/profile/setup", response_model=UserProfileResponse)
def setup_profile(
    body: UsernameSetup,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """First-time profile setup — sets username and optional display_name."""
    if current_user.profile:
        raise HTTPException(status_code=400, detail="Profile already set up. Use PUT to update.")

    if not USERNAME_RE.match(body.username):
        raise HTTPException(
            status_code=422,
            detail="Username must be 3-50 characters and contain only letters, numbers, or underscores."
        )

    existing = db.query(UserProfile).filter_by(username=body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken.")

    profile = UserProfile(
        user_id=current_user.id,
        username=body.username,
        display_name=body.display_name or body.username,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _build_profile_response(profile, current_user, db)


@router.get("/me/profile", response_model=UserProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not set up yet.")
    return _build_profile_response(current_user.profile, current_user, db)


@router.put("/me/profile", response_model=UserProfileResponse)
def update_my_profile(
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not set up yet.")
    profile = current_user.profile
    if body.display_name is not None:
        profile.display_name = body.display_name
    if body.bio is not None:
        profile.bio = body.bio
    db.commit()
    db.refresh(profile)
    return _build_profile_response(profile, current_user, db)


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserProfile).filter_by(user_id=user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return _build_profile_response(profile, current_user, db)
