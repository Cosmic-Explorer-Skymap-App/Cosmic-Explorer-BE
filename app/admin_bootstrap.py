import os

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .auth_utils import get_password_hash
from .models import AdminAccount


def ensure_founder_admin(db: Session) -> None:
    username = os.getenv("ADMIN_FOUNDER_USERNAME", "Fathertkt").strip()
    password = os.getenv("ADMIN_FOUNDER_PASSWORD", "586363")
    display_name = os.getenv("ADMIN_FOUNDER_DISPLAY_NAME", "Founder Admin").strip()

    if not username or not password:
        return

    existing = db.query(AdminAccount).filter(AdminAccount.username == username).first()
    if existing:
        if not existing.is_founder:
            existing.is_founder = True
            existing.is_admin = True
            existing.is_active = True
            db.commit()
        return

    founder = AdminAccount(
        username=username,
        password_hash=get_password_hash(password),
        display_name=display_name,
        is_admin=True,
        is_founder=True,
        is_active=True,
    )
    db.add(founder)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()