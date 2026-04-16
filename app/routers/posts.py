import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserProfile, Post, Like, Follow
from ..schemas import PostResponse, FeedResponse
from ..dependencies import get_current_user, get_optional_current_user

router = APIRouter(prefix="/api/posts", tags=["Posts"])

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/app/media"))
BASE_URL = os.getenv("BASE_URL", "")
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
FEED_PAGE_SIZE = 20


def _save_image(file: UploadFile, user_id: int) -> str:
    """Save uploaded image to disk, return relative URL path."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Only JPEG, PNG or WebP images are allowed.")

    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    filename = f"{uuid.uuid4().hex}.{ext}"
    user_dir = MEDIA_DIR / "posts" / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / filename

    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image too large. Max 20 MB.")

    dest.write_bytes(contents)
    return f"/media/posts/{user_id}/{filename}"


def _resolve_url(path: Optional[str]) -> Optional[str]:
    if path and path.startswith("/"):
        return f"{BASE_URL}{path}"
    return path


def _build_post_response(post: Post, current_user_id: Optional[int], db: Session) -> PostResponse:
    profile: Optional[UserProfile] = post.user.profile
    is_liked = (
        current_user_id is not None
        and db.query(Like).filter_by(user_id=current_user_id, post_id=post.id).first() is not None
    )
    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        username=profile.username if profile else str(post.user_id),
        display_name=profile.display_name if profile else None,
        avatar_url=_resolve_url(profile.avatar_url) if profile else None,
        image_url=_resolve_url(post.image_url) or "",
        title=post.title,
        caption=post.caption,
        like_count=post.like_count,
        comment_count=post.comment_count,
        is_liked_by_me=is_liked,
        created_at=post.created_at,
    )


# ---------------------------------------------------------------------------
# Create Post
# ---------------------------------------------------------------------------

@router.post("/", response_model=PostResponse, status_code=201)
def create_post(
    title: str = Form(..., max_length=120),
    caption: Optional[str] = Form(None, max_length=1000),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.profile:
        raise HTTPException(status_code=403, detail="Set up your profile before posting.")

    if not title.strip():
        raise HTTPException(status_code=422, detail="Title cannot be empty.")

    image_url = _save_image(image, current_user.id)

    post = Post(
        user_id=current_user.id,
        image_url=image_url,
        title=title.strip(),
        caption=caption.strip() if caption else None,
    )
    db.add(post)
    db.query(UserProfile).filter(UserProfile.user_id == current_user.id).update(
        {"post_count": UserProfile.post_count + 1}, synchronize_session=False
    )
    db.commit()
    db.refresh(post)
    return _build_post_response(post, current_user.id, db)


# ---------------------------------------------------------------------------
# Feed (posts from followed users)
# ---------------------------------------------------------------------------

@router.get("/feed", response_model=FeedResponse)
def get_feed(
    cursor: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    following_ids = [
        f.following_id
        for f in db.query(Follow).filter_by(follower_id=current_user.id).all()
    ]

    # Include own posts in feed
    following_ids.append(current_user.id)

    query = db.query(Post).filter(Post.user_id.in_(following_ids))
    if cursor is not None:
        query = query.filter(Post.id < cursor)

    posts = query.order_by(Post.created_at.desc()).limit(FEED_PAGE_SIZE + 1).all()

    has_more = len(posts) > FEED_PAGE_SIZE
    posts = posts[:FEED_PAGE_SIZE]
    next_cursor = posts[-1].id if (posts and has_more) else None

    return FeedResponse(
        posts=[_build_post_response(p, current_user.id, db) for p in posts],
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ---------------------------------------------------------------------------
# Explore (global trending)
# ---------------------------------------------------------------------------

@router.get("/explore", response_model=FeedResponse)
def get_explore(
    cursor: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    offset = cursor or 0
    posts = (
        db.query(Post)
        .order_by(Post.like_count.desc(), Post.created_at.desc())
        .offset(offset)
        .limit(FEED_PAGE_SIZE + 1)
        .all()
    )
    has_more = len(posts) > FEED_PAGE_SIZE
    posts = posts[:FEED_PAGE_SIZE]
    next_cursor = offset + FEED_PAGE_SIZE if has_more else None
    uid = current_user.id if current_user else None
    return FeedResponse(
        posts=[_build_post_response(p, uid, db) for p in posts],
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ---------------------------------------------------------------------------
# Single Post
# ---------------------------------------------------------------------------

@router.get("/{post_id}", response_model=PostResponse)
def get_post(
    post_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    uid = current_user.id if current_user else None
    return _build_post_response(post, uid, db)


# ---------------------------------------------------------------------------
# User's own posts
# ---------------------------------------------------------------------------

@router.get("/user/{user_id}", response_model=FeedResponse)
def get_user_posts(
    user_id: int,
    cursor: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Post).filter(Post.user_id == user_id)
    if cursor is not None:
        query = query.filter(Post.id < cursor)

    posts = query.order_by(Post.created_at.desc()).limit(FEED_PAGE_SIZE + 1).all()
    has_more = len(posts) > FEED_PAGE_SIZE
    posts = posts[:FEED_PAGE_SIZE]
    next_cursor = posts[-1].id if (posts and has_more) else None

    uid = current_user.id if current_user else None
    return FeedResponse(
        posts=[_build_post_response(p, uid, db) for p in posts],
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ---------------------------------------------------------------------------
# Delete Post
# ---------------------------------------------------------------------------

@router.delete("/{post_id}", status_code=200)
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your post.")

    # Delete image file
    image_path = MEDIA_DIR / post.image_url.removeprefix("/media/")
    if image_path.exists():
        image_path.unlink(missing_ok=True)

    db.delete(post)
    db.query(UserProfile).filter(UserProfile.user_id == current_user.id).update(
        {"post_count": UserProfile.post_count - 1}, synchronize_session=False
    )
    db.commit()
    return {"message": "Deleted."}
