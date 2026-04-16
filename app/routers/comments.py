import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import User, Post, Comment
from ..schemas import CommentCreate, CommentResponse
from ..dependencies import get_current_user, get_optional_current_user

router = APIRouter(tags=["Comments"])

BASE_URL = os.getenv("BASE_URL", "")


def _resolve_url(path: str | None) -> str | None:
    if path and path.startswith("/"):
        return f"{BASE_URL}{path}"
    return path


def _comment_to_response(comment: Comment) -> CommentResponse:
    profile = comment.user.profile
    return CommentResponse(
        id=comment.id,
        user_id=comment.user_id,
        post_id=comment.post_id,
        username=profile.username if profile else str(comment.user_id),
        display_name=profile.display_name if profile else None,
        avatar_url=_resolve_url(profile.avatar_url) if profile else None,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("/api/posts/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    comments = (
        db.query(Comment)
        .filter_by(post_id=post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return [_comment_to_response(c) for c in comments]


@router.post("/api/posts/{post_id}/comments", response_model=CommentResponse, status_code=201)
def add_comment(
    post_id: int,
    body: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.profile:
        raise HTTPException(status_code=403, detail="Set up your profile before commenting.")

    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Comment cannot be empty.")

    comment = Comment(user_id=current_user.id, post_id=post_id, content=content)
    db.add(comment)
    db.query(Post).filter(Post.id == post_id).update(
        {"comment_count": Post.comment_count + 1}, synchronize_session=False
    )
    db.commit()
    db.refresh(comment)
    return _comment_to_response(comment)


@router.delete("/api/comments/{comment_id}", status_code=200)
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.query(Comment).filter_by(id=comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your comment.")

    post_id_to_decrement = comment.post_id
    db.delete(comment)
    db.query(Post).filter(Post.id == post_id_to_decrement).update(
        {"comment_count": Post.comment_count - 1}, synchronize_session=False
    )
    db.commit()
    return {"message": "Deleted."}
