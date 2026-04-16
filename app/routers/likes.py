from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Post, Like
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/posts", tags=["Likes"])


@router.post("/{post_id}/like", status_code=200)
def like_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    existing = db.query(Like).filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        return {"liked": True, "like_count": post.like_count}

    like = Like(user_id=current_user.id, post_id=post_id)
    db.add(like)
    db.query(Post).filter(Post.id == post_id).update(
        {"like_count": Post.like_count + 1}, synchronize_session=False
    )
    db.commit()
    db.refresh(post)
    return {"liked": True, "like_count": post.like_count}


@router.delete("/{post_id}/like", status_code=200)
def unlike_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    like = db.query(Like).filter_by(user_id=current_user.id, post_id=post_id).first()
    if not like:
        return {"liked": False, "like_count": post.like_count}

    db.delete(like)
    db.query(Post).filter(Post.id == post_id).update(
        {"like_count": Post.like_count - 1}, synchronize_session=False
    )
    db.commit()
    db.refresh(post)
    return {"liked": False, "like_count": post.like_count}
