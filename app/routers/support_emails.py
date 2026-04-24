import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ExternalEmail, User, AdminAccount
from ..schemas import ExternalEmailResponse, ExternalEmailSend
from ..dependencies import get_current_admin_identity
from ..email_utils import send_external_email

router = APIRouter(prefix="/api/support/emails", tags=["Support Emails"])

@router.post("/webhook/cloudflare")
async def cloudflare_email_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    raw_data = data.get("raw")
    if not raw_data:
        # Fallback if raw is not sent
        sender = data.get("from")
        recipient = data.get("to")
        subject = data.get("subject")
        body = data.get("text")
        html_body = data.get("html")
    else:
        import email
        from email import policy
        msg = email.message_from_string(raw_data, policy=policy.default)
        sender = msg.get("From")
        recipient = msg.get("To")
        subject = msg.get("Subject")
        
        body = ""
        html_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    html_body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
        else:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")

    new_email = ExternalEmail(
        sender=str(sender),
        recipient=str(recipient),
        subject=str(subject),
        body=body,
        html_body=html_body,
        direction="inbound",
        metadata_json=json.dumps(data)
    )
    db.add(new_email)
    db.commit()
    return {"status": "ok", "id": new_email.id}


@router.get("/", response_model=List[ExternalEmailResponse])
def list_emails(
    current_admin: User | AdminAccount = Depends(get_current_admin_identity),
    db: Session = Depends(get_db)
):
    return db.query(ExternalEmail).order_by(ExternalEmail.created_at.desc()).all()


@router.post("/send", response_model=ExternalEmailResponse)
def send_email(
    payload: ExternalEmailSend,
    current_admin: User | AdminAccount = Depends(get_current_admin_identity),
    db: Session = Depends(get_db)
):
    success = send_external_email(
        to_email=payload.recipient,
        subject=payload.subject,
        body=payload.body
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email via SMTP")

    # Log the outbound email
    new_email = ExternalEmail(
        sender="support@cosmicexplorer.uk", # Fixed for now
        recipient=payload.recipient,
        subject=payload.subject,
        body=payload.body,
        direction="outbound",
        reply_to_id=payload.reply_to_id
    )
    
    if payload.reply_to_id:
        original = db.query(ExternalEmail).filter(ExternalEmail.id == payload.reply_to_id).first()
        if original:
            original.is_replied = True

    db.add(new_email)
    db.commit()
    db.refresh(new_email)
    return new_email


@router.patch("/{email_id}/read")
def mark_as_read(
    email_id: int,
    current_admin: User | AdminAccount = Depends(get_current_admin_identity),
    db: Session = Depends(get_db)
):
    email = db.query(ExternalEmail).filter(ExternalEmail.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    email.is_read = True
    db.commit()
    return {"status": "ok"}
