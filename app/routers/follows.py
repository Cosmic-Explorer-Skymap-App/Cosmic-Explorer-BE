from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import User, UserProfile, Follow
from ..schemas import UserProfileResponse
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/users", tags=["Follows"])


def _is_following(current_user_id: int, target_user_id: int, db: Session) -> bool:
    return db.query(Follow).filter_by(
        follower_id=current_user_id,
        following_id=target_user_id
    ).first() is not None


def _profile_to_response(profile: UserProfile, current_user: User, db: Session) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=profile.user_id,
        username=profile.username,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        follower_count=profile.follower_count,
        following_count=profile.following_count,
        post_count=profile.post_count,
        is_following=_is_following(current_user.id, profile.user_id, db),
    )


@router.post("/{user_id}/follow", status_code=200)
def follow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself.")

    target = db.query(User).filter_by(id=user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    existing = db.query(Follow).filter_by(follower_id=current_user.id, following_id=user_id).first()
    if existing:
        return {"message": "Already following."}

    follow = Follow(follower_id=current_user.id, following_id=user_id)
    db.add(follow)

    # Update counters
    if current_user.profile:
        current_user.profile.following_count += 1
    if target.profile:
        target.profile.follower_count += 1

    db.commit()
    return {"message": "Followed."}


@router.delete("/{user_id}/follow", status_code=200)
def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follow = db.query(Follow).filter_by(follower_id=current_user.id, following_id=user_id).first()
    if not follow:
        raise HTTPException(status_code=404, detail="Not following this user.")

    target = db.query(User).filter_by(id=user_id).first()
    db.delete(follow)

    if current_user.profile and current_user.profile.following_count > 0:
        current_user.profile.following_count -= 1
    if target and target.profile and target.profile.follower_count > 0:
        target.profile.follower_count -= 1

    db.commit()
    return {"message": "Unfollowed."}


@router.get("/{user_id}/followers", response_model=List[UserProfileResponse])
def get_followers(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follows = db.query(Follow).filter_by(following_id=user_id).all()
    profiles = []
    for f in follows:
        profile = db.query(UserProfile).filter_by(user_id=f.follower_id).first()
        if profile:
            profiles.append(_profile_to_response(profile, current_user, db))
    return profiles


@router.get("/{user_id}/following", response_model=List[UserProfileResponse])
def get_following(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follows = db.query(Follow).filter_by(follower_id=user_id).all()
    profiles = []
    for f in follows:
        profile = db.query(UserProfile).filter_by(user_id=f.following_id).first()
        if profile:
            profiles.append(_profile_to_response(profile, current_user, db))
    return profiles
