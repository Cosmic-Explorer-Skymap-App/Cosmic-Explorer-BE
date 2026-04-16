import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from ..database import get_db
from ..models import User, UserProfile, Conversation, Message
from ..schemas import MessageSend, MessageResponse, ConversationResponse, ConversationParticipant
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/messages", tags=["Messages"])

BASE_URL = os.getenv("BASE_URL", "")


def _resolve_url(path: Optional[str]) -> Optional[str]:
    if path and path.startswith("/"):
        return f"{BASE_URL}{path}"
    return path


def _get_or_create_conversation(me: User, other_user: User, db: Session) -> Conversation:
    u1, u2 = (me.id, other_user.id) if me.id < other_user.id else (other_user.id, me.id)
    conv = db.query(Conversation).filter_by(user1_id=u1, user2_id=u2).first()
    if not conv:
        conv = Conversation(user1_id=u1, user2_id=u2)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _build_conversation_response(conv: Conversation, me_id: int, db: Session) -> ConversationResponse:
    other = conv.user2 if conv.user1_id == me_id else conv.user1
    other_profile: Optional[UserProfile] = other.profile
    unread = conv.unread_count_1 if conv.user1_id == me_id else conv.unread_count_2

    last_msg = (
        db.query(Message)
        .filter_by(conversation_id=conv.id)
        .order_by(Message.created_at.desc())
        .first()
    )

    return ConversationResponse(
        id=conv.id,
        other_user=ConversationParticipant(
            user_id=other.id,
            username=other_profile.username if other_profile else str(other.id),
            display_name=other_profile.display_name if other_profile else None,
            avatar_url=_resolve_url(other_profile.avatar_url) if other_profile else None,
        ),
        last_message=MessageResponse(
            id=last_msg.id,
            conversation_id=last_msg.conversation_id,
            sender_id=last_msg.sender_id,
            content=last_msg.content,
            is_read=last_msg.is_read,
            created_at=last_msg.created_at,
        ) if last_msg else None,
        unread_count=unread,
        last_message_at=conv.last_message_at,
    )


# ── List conversations (inbox) ───────────────────────────────────────────────

@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = (
        db.query(Conversation)
        .filter(or_(
            Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id,
        ))
        .order_by(Conversation.last_message_at.desc())
        .all()
    )
    return [_build_conversation_response(c, current_user.id, db) for c in convs]


# ── Get or create conversation with a user ──────────────────────────────────

@router.post("/conversations/{user_id}", response_model=ConversationResponse)
def get_or_create_conversation(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself.")
    other = db.query(User).filter_by(id=user_id).first()
    if not other:
        raise HTTPException(status_code=404, detail="User not found.")
    conv = _get_or_create_conversation(current_user, other, db)
    return _build_conversation_response(conv, current_user.id, db)


# ── Get messages in a conversation ──────────────────────────────────────────

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(
    conversation_id: int,
    before_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if not conv or current_user.id not in (conv.user1_id, conv.user2_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")

    q = db.query(Message).filter_by(conversation_id=conversation_id)
    if before_id:
        q = q.filter(Message.id < before_id)
    msgs = q.order_by(Message.created_at.desc()).limit(limit).all()
    msgs.reverse()

    # Mark unread messages as read
    db.query(Message).filter(
        and_(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user.id,
            Message.is_read == False,
        )
    ).update({"is_read": True}, synchronize_session=False)

    # Reset my unread counter
    if conv.user1_id == current_user.id:
        conv.unread_count_1 = 0
    else:
        conv.unread_count_2 = 0
    db.commit()

    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            sender_id=m.sender_id,
            content=m.content,
            is_read=m.is_read,
            created_at=m.created_at,
        )
        for m in msgs
    ]


# ── Send a message ───────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
def send_message(
    conversation_id: int,
    body: MessageSend,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if not conv or current_user.id not in (conv.user1_id, conv.user2_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")

    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")
    if len(content) > 1000:
        raise HTTPException(status_code=422, detail="Message too long (max 1000 chars).")

    msg = Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=content,
    )
    db.add(msg)

    # Increment receiver's unread counter and update last_message_at
    import datetime
    conv.last_message_at = datetime.datetime.now(datetime.timezone.utc)
    if conv.user1_id == current_user.id:
        conv.unread_count_2 += 1
    else:
        conv.unread_count_1 += 1

    db.commit()
    db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


# ── Total unread count (for navbar badge) ───────────────────────────────────

@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = db.query(Conversation).filter(
        or_(
            Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id,
        )
    ).all()
    total = sum(
        c.unread_count_1 if c.user1_id == current_user.id else c.unread_count_2
        for c in convs
    )
    return {"unread_count": total}
