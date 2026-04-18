from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import AdminAccount, AdminPermissionAssignment, User, UserSession
from .auth_utils import SECRET_KEY, ALGORITHM
from .security import now_utc

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


def _extract_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.cookies.get("ce_token")


def _validate_session(payload: dict, db: Session) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    session = db.query(UserSession).filter(UserSession.token_jti == jti).first()
    if not session or not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is no longer active",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session.last_seen_at = now_utc()
    db.flush()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        _validate_session(payload, db)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    token = _extract_token(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            return None
        _validate_session(payload, db)
        return db.query(User).filter(User.email == email).first()
    except JWTError:
        return None


def get_current_admin_identity(request: Request, db: Session = Depends(get_db)) -> User | AdminAccount:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception

    scope = (payload.get("scope") or "").strip().lower()
    if scope == "admin":
        username = payload.get("sub")
        if not username:
            raise credentials_exception
        admin = db.query(AdminAccount).filter(AdminAccount.username == username).first()
        if admin is None or not admin.is_active or not admin.is_admin:
            raise credentials_exception
        return admin

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    _validate_session(payload, db)
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def get_current_admin_user(current_admin: User | AdminAccount = Depends(get_current_admin_identity)) -> User | AdminAccount:
    return current_admin


ADMIN_PERMISSION_PLANNING = "planning"
ADMIN_PERMISSION_OVERVIEW = "overview"
ADMIN_PERMISSION_SYSTEM = "system"
ADMIN_PERMISSION_ADMINS = "admins"


def get_admin_permissions(admin: User | AdminAccount, db: Session) -> set[str]:
    if isinstance(admin, AdminAccount):
        if admin.is_founder:
            return {
                ADMIN_PERMISSION_PLANNING,
                ADMIN_PERMISSION_OVERVIEW,
                ADMIN_PERMISSION_SYSTEM,
                ADMIN_PERMISSION_ADMINS,
            }
        rows = (
            db.query(AdminPermissionAssignment.permission)
            .filter(AdminPermissionAssignment.admin_account_id == admin.id)
            .all()
        )
        permissions = {row[0] for row in rows if row and row[0]}
        if not permissions:
            permissions.add(ADMIN_PERMISSION_PLANNING)
        return permissions

    return {
        ADMIN_PERMISSION_PLANNING,
        ADMIN_PERMISSION_OVERVIEW,
        ADMIN_PERMISSION_SYSTEM,
        ADMIN_PERMISSION_ADMINS,
    }


def require_admin_permission(permission: str):
    def _dependency(
        current_admin: User | AdminAccount = Depends(get_current_admin_user),
        db: Session = Depends(get_db),
    ) -> User | AdminAccount:
        permissions = get_admin_permissions(current_admin, db)
        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Admin permission '{permission}' is required",
            )
        return current_admin

    return _dependency
