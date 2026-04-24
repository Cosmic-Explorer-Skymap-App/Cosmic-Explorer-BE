import os
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Body, Depends, HTTPException, Request, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MalwareScanJob, User, SupportMessage
from ..schemas import SupportResponse
from ..dependencies import get_current_user
from ..email_utils import send_external_email
from ..security import require_rate_limit

router = APIRouter(prefix="/api/support", tags=["Support"])

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/app/media"))
BASE_URL = os.getenv("BASE_URL", "")
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def _save_support_image(file: UploadFile) -> str:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Sadece JPEG, PNG veya WebP görselleri kabul edilir.")

    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    filename = f"{uuid.uuid4().hex}.{ext}"
    support_dir = MEDIA_DIR / "support"
    support_dir.mkdir(parents=True, exist_ok=True)
    dest = support_dir / filename

    written = 0
    with dest.open("wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_FILE_SIZE:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Görsel çok büyük. Maksimum 10 MB.")
            out.write(chunk)

    return f"/media/support/{filename}"

@router.post("/", response_model=SupportResponse, status_code=201)
def create_support_ticket(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    require_rate_limit(request, scope="support_create", limit=20, window_seconds=60)

    image_url = None
    if image:
        image_url = _save_support_image(image)

    new_ticket = SupportMessage(
        full_name=full_name,
        email=email,
        subject=subject,
        message=message,
        image_url=image_url,
        status="open"
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)

    # Forward to corporate email
    try:
        email_body = f"Yeni Destek Mesajı!\n\nKimden: {full_name} ({email})\nKonu: {subject}\nMesaj: {message}"
        if image_url:
            email_body += f"\nEk Görsel: {image_url}"
        
        send_external_email(
            to_email="support@cosmicexplorer.uk",
            subject=f"DESTEK: {subject}",
            body=email_body
        )
    except Exception as e:
        print(f"Failed to forward support message to email: {e}")

    if image_url:
        db.add(
            MalwareScanJob(
                support_message_id=new_ticket.id,
                file_url=image_url,
                status="queued",
                scanner="manual-review",
            )
        )
        db.commit()

    return new_ticket

@router.get("/", response_model=List[SupportResponse])
def list_support_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekiyor.")
    
    return db.query(SupportMessage).order_by(SupportMessage.created_at.desc()).all()

@router.get("/{ticket_id}", response_model=SupportResponse)
def get_support_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekiyor.")
    
    ticket = db.query(SupportMessage).filter_by(id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı.")
    return ticket

@router.patch("/{ticket_id}", response_model=SupportResponse)
def update_ticket_status(
    ticket_id: int,
    new_status: str = Body(..., embed=True, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekiyor.")

    ticket = db.query(SupportMessage).filter_by(id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı.")

    ticket.status = new_status
    db.commit()
    db.refresh(ticket)
    return ticket
