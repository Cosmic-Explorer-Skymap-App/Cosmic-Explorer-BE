import os
import re
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserProfile, Follow
from ..schemas import UserProfileResponse, UserProfileUpdate, UsernameSetup
from ..dependencies import get_current_user, get_optional_current_user

router = APIRouter(prefix="/api/users", tags=["Profile"])

BASE_URL = os.getenv("BASE_URL", "")
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/app/media"))
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,50}$")


def _resolve_url(path: str | None) -> str | None:
    """Prepend BASE_URL to local /media/ paths; leave external URLs (Google etc.) as-is."""
    if path and path.startswith("/"):
        return f"{BASE_URL}{path}"
    return path


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
        avatar_url=_resolve_url(profile.avatar_url),
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


@router.post("/me/profile/avatar", response_model=UserProfileResponse)
def upload_avatar(
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not set up yet.")

    content_type = avatar.content_type or ""
    if content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=422, detail="Only JPEG, PNG or WebP images are allowed.")

    contents = avatar.file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=413, detail="Avatar too large. Max 5 MB.")

    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    filename = f"{uuid.uuid4().hex}.{ext}"
    avatar_dir = MEDIA_DIR / "avatars" / str(current_user.id)
    avatar_dir.mkdir(parents=True, exist_ok=True)
    dest = avatar_dir / filename
    dest.write_bytes(contents)

    # Delete old avatar file if it was a local upload (not a Google URL).
    # Since fix #1, local avatars are stored as relative paths starting with "/media/avatars/".
    # Legacy records may still contain an absolute URL with BASE_URL baked in — both cases
    # are handled by checking whether "/media/avatars/" appears anywhere in the stored value.
    old_url = current_user.profile.avatar_url or ""
    if "/media/avatars/" in old_url:
        local_rel = old_url[old_url.find("/media/avatars/"):].removeprefix("/media/")
        old_path = MEDIA_DIR / local_rel
        old_path.unlink(missing_ok=True)

    # Store as relative path — BASE_URL is prepended at response time by _resolve_url().
    current_user.profile.avatar_url = f"/media/avatars/{current_user.id}/{filename}"
    db.commit()
    db.refresh(current_user.profile)
    return _build_profile_response(current_user.profile, current_user, db)


@router.get("/search", response_model=List[UserProfileResponse])
def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    current_user: User = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Search users by username or display_name (case-insensitive, partial match)."""
    term = f"%{q.strip().lower()}%"
    profiles = (
        db.query(UserProfile)
        .filter(
            UserProfile.username.ilike(term) | UserProfile.display_name.ilike(term)
        )
        .limit(20)
        .all()
    )
    dummy = current_user or User(id=-1)
    return [_build_profile_response(p, dummy, db) for p in profiles]


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
