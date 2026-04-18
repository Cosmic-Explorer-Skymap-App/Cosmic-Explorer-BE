import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..dependencies import ADMIN_PERMISSION_PLANNING, require_admin_permission
from ..models import AdminAccount, PlanningItem
from ..schemas import PlanningItemCreate, PlanningItemResponse, PlanningItemUpdate

router = APIRouter(prefix="/api/admin/plans", tags=["Admin Plans"])


def _to_utc(value: datetime.datetime) -> datetime.datetime:
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def _normalize_range(start_at: datetime.datetime, end_at: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime]:
    start_at = _to_utc(start_at)
    end_at = _to_utc(end_at)
    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="end_at must be after start_at")
    return start_at, end_at


@router.get("", response_model=list[PlanningItemResponse])
def list_plans(
    current_admin: AdminAccount = Depends(require_admin_permission(ADMIN_PERMISSION_PLANNING)),
    db: Session = Depends(get_db),
):
    _ = current_admin
    return db.query(PlanningItem).order_by(PlanningItem.start_at.asc()).all()


@router.post("", response_model=PlanningItemResponse, status_code=201)
def create_plan(
    payload: PlanningItemCreate,
    request: Request,
    current_admin: AdminAccount = Depends(require_admin_permission(ADMIN_PERMISSION_PLANNING)),
    db: Session = Depends(get_db),
):
    start_at, end_at = _normalize_range(payload.start_at, payload.end_at)
    plan = PlanningItem(
        title=payload.title.strip(),
        details=payload.details.strip(),
        start_at=start_at,
        end_at=end_at,
        color=payload.color.strip() or "#7c5cff",
        status=payload.status.strip().lower() or "planned",
        created_by_admin_id=current_admin.id,
    )
    db.add(plan)
    record_audit(
        db,
        action="admin.plan.create",
        actor_user=current_admin,
        request=request,
        target_type="planning_item",
        target_id=plan.title,
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.put("/{plan_id}", response_model=PlanningItemResponse)
def update_plan(
    plan_id: int,
    payload: PlanningItemUpdate,
    request: Request,
    current_admin: AdminAccount = Depends(require_admin_permission(ADMIN_PERMISSION_PLANNING)),
    db: Session = Depends(get_db),
):
    plan = db.query(PlanningItem).filter(PlanningItem.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Planning item not found")
    if payload.title is not None:
        plan.title = payload.title.strip()
    if payload.details is not None:
        plan.details = payload.details.strip()
    if payload.start_at is not None:
        plan.start_at = _to_utc(payload.start_at)
    if payload.end_at is not None:
        plan.end_at = _to_utc(payload.end_at)
    if payload.color is not None:
        plan.color = payload.color.strip() or plan.color
    if payload.status is not None:
        plan.status = payload.status.strip().lower() or plan.status

    plan.start_at, plan.end_at = _normalize_range(plan.start_at, plan.end_at)
    record_audit(
        db,
        action="admin.plan.update",
        actor_user=current_admin,
        request=request,
        target_type="planning_item",
        target_id=str(plan.id),
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    request: Request,
    current_admin: AdminAccount = Depends(require_admin_permission(ADMIN_PERMISSION_PLANNING)),
    db: Session = Depends(get_db),
):
    plan = db.query(PlanningItem).filter(PlanningItem.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Planning item not found")
    record_audit(
        db,
        action="admin.plan.delete",
        actor_user=current_admin,
        request=request,
        target_type="planning_item",
        target_id=str(plan.id),
    )
    db.delete(plan)
    db.commit()