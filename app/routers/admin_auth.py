import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..admin_bootstrap import ensure_founder_admin
from ..audit import record_audit
from ..auth_utils import create_access_token, get_password_hash, verify_password
from ..database import get_db
from ..dependencies import (
    ADMIN_PERMISSION_ADMINS,
    ADMIN_PERMISSION_OVERVIEW,
    ADMIN_PERMISSION_PLANNING,
    ADMIN_PERMISSION_SYSTEM,
    get_admin_permissions,
    get_current_admin_user,
)
from ..models import AdminAccount, AdminPermissionAssignment, User
from ..schemas import (
    AdminAccountCreate,
    AdminAccountResponse,
    AdminLoginRequest,
    AdminPermissionsUpdate,
    Token,
)
from ..security import now_utc, require_rate_limit

router = APIRouter(prefix="/api/admin/auth", tags=["Admin Auth"])

VALID_ADMIN_PERMISSIONS = {
    ADMIN_PERMISSION_PLANNING,
    ADMIN_PERMISSION_OVERVIEW,
    ADMIN_PERMISSION_SYSTEM,
    ADMIN_PERMISSION_ADMINS,
}


def _require_founder(current_admin: AdminAccount) -> AdminAccount:
    if not getattr(current_admin, "is_founder", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Founder admin privileges required")
    return current_admin


def _require_admin_account(current_admin: User | AdminAccount) -> AdminAccount:
    if not isinstance(current_admin, AdminAccount):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account authentication required")
    return current_admin


def _normalize_permissions(values: list[str]) -> list[str]:
    cleaned = []
    for value in values:
        perm = (value or "").strip().lower()
        if not perm:
            continue
        if perm not in VALID_ADMIN_PERMISSIONS:
            raise HTTPException(status_code=422, detail=f"Invalid admin permission: {perm}")
        if perm not in cleaned:
            cleaned.append(perm)
    return cleaned


def _set_account_permissions(db: Session, account_id: int, permissions: list[str]) -> None:
    db.query(AdminPermissionAssignment).filter(
        AdminPermissionAssignment.admin_account_id == account_id
    ).delete(synchronize_session=False)
    for perm in permissions:
        db.add(AdminPermissionAssignment(admin_account_id=account_id, permission=perm))


def _serialize_account(db: Session, account: AdminAccount) -> AdminAccountResponse:
    permissions = sorted(get_admin_permissions(account, db))
    return AdminAccountResponse.model_validate(
        {
            "id": account.id,
            "username": account.username,
            "display_name": account.display_name,
            "is_admin": account.is_admin,
            "is_founder": account.is_founder,
            "is_active": account.is_active,
            "permissions": permissions,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
            "last_login_at": account.last_login_at,
        }
    )


@router.post("/login", response_model=Token)
def admin_login(payload: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Admin login endpoint - no authentication required for initial login"""
    require_rate_limit(request, scope="admin_login", limit=10, window_seconds=60)
    ensure_founder_admin(db)

    username = payload.username.strip()
    account = db.query(AdminAccount).filter(AdminAccount.username == username).first()
    if account is None or not account.is_active or not verify_password(payload.password, account.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

    account.last_login_at = now_utc()
    token = create_access_token({"sub": account.username, "scope": "admin", "jti": uuid.uuid4().hex})
    record_audit(
        db,
        action="admin.auth.login",
        actor_user=account,
        request=request,
        target_type="admin_account",
        target_id=str(account.id),
    )
    db.commit()
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=AdminAccountResponse)
def admin_me(current_admin: User | AdminAccount = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    admin_account = _require_admin_account(current_admin)
    return _serialize_account(db, admin_account)


@router.get("/accounts", response_model=list[AdminAccountResponse])
def list_accounts(current_admin: User | AdminAccount = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    _require_founder(_require_admin_account(current_admin))
    accounts = db.query(AdminAccount).order_by(AdminAccount.created_at.asc()).all()
    return [_serialize_account(db, account) for account in accounts]


@router.post("/accounts", response_model=AdminAccountResponse, status_code=201)
def create_account(
    payload: AdminAccountCreate,
    request: Request,
    current_admin: User | AdminAccount = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    admin_actor = _require_founder(_require_admin_account(current_admin))
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="username is required")
    existing = db.query(AdminAccount).filter(AdminAccount.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Admin username already exists")

    account = AdminAccount(
        username=username,
        password_hash=get_password_hash(payload.password),
        display_name=payload.display_name.strip() if payload.display_name else None,
        is_admin=True,
        is_founder=False,
        is_active=True,
    )
    db.add(account)
    db.flush()
    permissions = _normalize_permissions(payload.permissions or [ADMIN_PERMISSION_PLANNING])
    if account.is_founder and ADMIN_PERMISSION_ADMINS not in permissions:
        permissions.append(ADMIN_PERMISSION_ADMINS)
    _set_account_permissions(db, account.id, permissions)
    record_audit(
        db,
        action="admin.account.create",
        actor_user=admin_actor,
        request=request,
        target_type="admin_account",
        target_id=username,
    )
    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)


@router.patch("/accounts/{account_id}/block", response_model=AdminAccountResponse)
def block_account(
    account_id: int,
    request: Request,
    current_admin: User | AdminAccount = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    admin_actor = _require_founder(_require_admin_account(current_admin))
    account = db.query(AdminAccount).filter(AdminAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Admin account not found")
    if account.is_founder:
        raise HTTPException(status_code=403, detail="Founder account cannot be blocked")
    account.is_active = False
    record_audit(
        db,
        action="admin.account.block",
        actor_user=admin_actor,
        request=request,
        target_type="admin_account",
        target_id=str(account.id),
    )
    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)


@router.patch("/accounts/{account_id}/unblock", response_model=AdminAccountResponse)
def unblock_account(
    account_id: int,
    request: Request,
    current_admin: User | AdminAccount = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    admin_actor = _require_founder(_require_admin_account(current_admin))
    account = db.query(AdminAccount).filter(AdminAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Admin account not found")
    account.is_active = True
    record_audit(
        db,
        action="admin.account.unblock",
        actor_user=admin_actor,
        request=request,
        target_type="admin_account",
        target_id=str(account.id),
    )
    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)


@router.patch("/accounts/{account_id}/permissions", response_model=AdminAccountResponse)
def update_account_permissions(
    account_id: int,
    payload: AdminPermissionsUpdate,
    request: Request,
    current_admin: User | AdminAccount = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    admin_actor = _require_founder(_require_admin_account(current_admin))
    account = db.query(AdminAccount).filter(AdminAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Admin account not found")

    permissions = _normalize_permissions(payload.permissions)
    if not account.is_founder and not permissions:
        raise HTTPException(status_code=422, detail="At least one permission is required for non-founder admins")
    if account.is_founder and ADMIN_PERMISSION_ADMINS not in permissions:
        permissions.append(ADMIN_PERMISSION_ADMINS)

    _set_account_permissions(db, account.id, permissions)
    record_audit(
        db,
        action="admin.account.permissions.update",
        actor_user=admin_actor,
        request=request,
        target_type="admin_account",
        target_id=str(account.id),
        metadata={"permissions": permissions},
    )
    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)