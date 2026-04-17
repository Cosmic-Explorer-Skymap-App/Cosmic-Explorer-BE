import json
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog, SecurityEvent, User
from .security import client_ip, now_utc, user_agent


def record_audit(
    db: Session,
    *,
    action: str,
    actor_user: Optional[User],
    request: Optional[Request] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    row = AuditLog(
        actor_user_id=actor_user.id if actor_user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=client_ip(request) if request else None,
        user_agent=user_agent(request) if request else None,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=True),
        created_at=now_utc(),
    )
    db.add(row)


def record_security_event(
    db: Session,
    *,
    event_type: str,
    user: Optional[User],
    severity: str = "info",
    details: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    row = SecurityEvent(
        user_id=user.id if user else None,
        event_type=event_type,
        severity=severity,
        ip_address=client_ip(request) if request else None,
        user_agent=user_agent(request) if request else None,
        details=details,
        created_at=now_utc(),
    )
    db.add(row)