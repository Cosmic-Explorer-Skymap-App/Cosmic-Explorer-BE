import datetime
import os
import smtplib
import time
from collections import defaultdict
from email.message import EmailMessage
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_admin_user, get_optional_current_user
from ..models import (
    BugReport,
    Comment,
    Conversation,
    EmailCampaign,
    FinanceEntry,
    Like,
    Message,
    Post,
    SocialConnection,
    SocialContent,
    SupportMessage,
    User,
    UserDevice,
)
from ..schemas import (
    AdminOverviewResponse,
    AdminSupportBreakdown,
    BugReportCreate,
    BugReportResponse,
    BugReportStatusUpdate,
    EmailCampaignCreate,
    EmailCampaignResponse,
    FinanceDailyPoint,
    FinanceEntryCreate,
    FinanceEntryResponse,
    FinanceSummaryResponse,
    PlatformBreakdown,
    SocialAnalyticsSummary,
    SocialConnectionCreate,
    SocialConnectionResponse,
    SocialContentCreate,
    SocialContentResponse,
    SocialContentStatusUpdate,
    SupportResponse,
    SystemStatusResponse,
    TierBreakdown,
    UsersPanelResponse,
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


VALID_PLATFORMS = {"youtube", "tiktok", "instagram", "web", "android", "ios", "all", "unknown"}
VALID_SOCIAL_STATUSES = {"draft", "scheduled", "published", "failed"}
VALID_BUG_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_BUG_STATUSES = {"open", "triaged", "closed"}
VALID_TIERS = {"free", "premium", "all"}
VALID_FINANCE_TYPES = {"income", "expense"}


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _normalize(value: str) -> str:
    return (value or "").strip().lower()


def _check_http(url: str) -> tuple[bool, Optional[int], Optional[int]]:
    started = time.perf_counter()
    try:
        resp = requests.get(url, timeout=4)
        latency = int((time.perf_counter() - started) * 1000)
        return resp.ok, resp.status_code, latency
    except requests.RequestException:
        return False, None, None


def _select_email_targets(db: Session, target_platform: str, target_tier: str) -> list[str]:
    query = db.query(User.email)

    if target_tier == "premium":
        query = query.filter(User.is_premium.is_(True))
    elif target_tier == "free":
        query = query.filter(User.is_premium.is_(False))

    if target_platform in {"web", "android", "ios"}:
        platform_subquery = (
            db.query(UserDevice.user_id)
            .filter(UserDevice.platform == target_platform)
            .subquery()
        )
        query = query.filter(User.id.in_(platform_subquery))

    return [row[0] for row in query.all() if row[0]]


def _send_campaign_email(recipients: list[str], subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_user)
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not smtp_host or not smtp_from:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SMTP configuration is missing. Set SMTP_HOST and SMTP_FROM_EMAIL.",
        )

    if not recipients:
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        if smtp_use_tls:
            server.starttls()
        if smtp_user:
            server.login(smtp_user, smtp_password)

        for recipient in recipients:
            msg = EmailMessage()
            msg["From"] = smtp_from
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.set_content(body)
            server.send_message(msg)


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    premium_users = db.query(func.count(User.id)).filter(User.is_premium.is_(True)).scalar() or 0
    total_posts = db.query(func.count(Post.id)).scalar() or 0
    total_comments = db.query(func.count(Comment.id)).scalar() or 0
    total_likes = db.query(func.count(Like.id)).scalar() or 0
    total_conversations = db.query(func.count(Conversation.id)).scalar() or 0
    total_messages = db.query(func.count(Message.id)).scalar() or 0

    open_reports = (
        db.query(func.count(SupportMessage.id))
        .filter(SupportMessage.status.in_(["open", "pending"]))
        .scalar()
        or 0
    )

    support_open = db.query(func.count(SupportMessage.id)).filter(SupportMessage.status == "open").scalar() or 0
    support_pending = (
        db.query(func.count(SupportMessage.id)).filter(SupportMessage.status == "pending").scalar() or 0
    )
    support_closed = (
        db.query(func.count(SupportMessage.id)).filter(SupportMessage.status == "closed").scalar() or 0
    )

    return AdminOverviewResponse(
        total_users=total_users,
        premium_users=premium_users,
        total_posts=total_posts,
        total_comments=total_comments,
        total_likes=total_likes,
        total_conversations=total_conversations,
        total_messages=total_messages,
        open_reports=open_reports,
        support=AdminSupportBreakdown(
            open=support_open,
            pending=support_pending,
            closed=support_closed,
        ),
        generated_at=datetime.datetime.now(datetime.timezone.utc),
    )


@router.get("/social/connections", response_model=list[SocialConnectionResponse])
def list_social_connections(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return db.query(SocialConnection).order_by(SocialConnection.updated_at.desc()).all()


@router.post("/social/connections", response_model=SocialConnectionResponse, status_code=201)
def create_social_connection(
    payload: SocialConnectionCreate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    platform = _normalize(payload.platform)
    if platform not in {"youtube", "tiktok", "instagram"}:
        raise HTTPException(status_code=422, detail="platform must be youtube, tiktok, or instagram")

    record = SocialConnection(
        platform=platform,
        account_name=payload.account_name.strip(),
        account_id=payload.account_id,
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        token_expires_at=payload.token_expires_at,
        is_active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/social/contents", response_model=list[SocialContentResponse])
def list_social_contents(
    platform: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(SocialContent)
    if platform:
        platform = _normalize(platform)
        query = query.filter(SocialContent.platform == platform)
    return query.order_by(SocialContent.created_at.desc()).limit(limit).all()


@router.post("/social/contents", response_model=SocialContentResponse, status_code=201)
def create_social_content(
    payload: SocialContentCreate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    platform = _normalize(payload.platform)
    if platform not in {"youtube", "tiktok", "instagram"}:
        raise HTTPException(status_code=422, detail="platform must be youtube, tiktok, or instagram")

    status_value = _normalize(payload.status)
    if status_value not in VALID_SOCIAL_STATUSES:
        raise HTTPException(status_code=422, detail="invalid social content status")

    row = SocialContent(
        platform=platform,
        connection_id=payload.connection_id,
        title=payload.title.strip(),
        body=payload.body,
        media_url=payload.media_url,
        status=status_value,
        scheduled_at=payload.scheduled_at,
        published_at=_now_utc() if status_value == "published" else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/social/contents/{content_id}/status", response_model=SocialContentResponse)
def update_social_content_status(
    content_id: int,
    payload: SocialContentStatusUpdate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(SocialContent).filter(SocialContent.id == content_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Social content not found")

    status_value = _normalize(payload.status)
    if status_value not in VALID_SOCIAL_STATUSES:
        raise HTTPException(status_code=422, detail="invalid social content status")

    row.status = status_value
    if status_value == "published":
        row.published_at = _now_utc()
    db.commit()
    db.refresh(row)
    return row


@router.get("/social/analytics/summary", response_model=SocialAnalyticsSummary)
def social_analytics_summary(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    total_contents = db.query(func.count(SocialContent.id)).scalar() or 0
    total_impressions = db.query(func.coalesce(func.sum(SocialContent.impressions), 0)).scalar() or 0
    total_clicks = db.query(func.coalesce(func.sum(SocialContent.clicks), 0)).scalar() or 0
    total_conversions = db.query(func.coalesce(func.sum(SocialContent.conversions), 0)).scalar() or 0
    total_spend = db.query(func.coalesce(func.sum(SocialContent.spend), 0)).scalar() or 0

    ctr = (total_clicks / total_impressions * 100) if total_impressions else 0.0
    conversion_rate = (total_conversions / total_clicks * 100) if total_clicks else 0.0
    return SocialAnalyticsSummary(
        total_contents=total_contents,
        total_impressions=total_impressions,
        total_clicks=total_clicks,
        total_conversions=total_conversions,
        total_spend=total_spend,
        ctr=round(ctr, 2),
        conversion_rate=round(conversion_rate, 2),
    )


@router.post("/system/bug-reports", response_model=BugReportResponse, status_code=201)
def create_bug_report(
    payload: BugReportCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    platform = _normalize(payload.source_platform)
    if platform not in {"web", "android", "ios", "unknown"}:
        raise HTTPException(status_code=422, detail="invalid bug report platform")

    severity = _normalize(payload.severity)
    if severity not in VALID_BUG_SEVERITIES:
        raise HTTPException(status_code=422, detail="invalid bug severity")

    row = BugReport(
        user_id=current_user.id if current_user else None,
        source_platform=platform,
        severity=severity,
        title=payload.title.strip(),
        description=payload.description.strip(),
        status="open",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/system/bug-reports", response_model=list[BugReportResponse])
def list_bug_reports(
    status_filter: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(BugReport)
    if status_filter:
        value = _normalize(status_filter)
        if value not in VALID_BUG_STATUSES:
            raise HTTPException(status_code=422, detail="invalid bug status")
        query = query.filter(BugReport.status == value)
    return query.order_by(BugReport.created_at.desc()).limit(limit).all()


@router.patch("/system/bug-reports/{report_id}", response_model=BugReportResponse)
def update_bug_report_status(
    report_id: int,
    payload: BugReportStatusUpdate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    report = db.query(BugReport).filter(BugReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Bug report not found")

    next_status = _normalize(payload.status)
    if next_status not in VALID_BUG_STATUSES:
        raise HTTPException(status_code=422, detail="invalid bug status")

    report.status = next_status
    db.commit()
    db.refresh(report)
    return report


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    backend_health_url = os.getenv("ADMIN_BACKEND_HEALTH_URL", "https://api.cosmic-explorer.example/health")
    web_health_url = os.getenv("ADMIN_WEB_HEALTH_URL", "https://cosmic-explorer.example")

    backend_ok, backend_status_code, backend_latency_ms = _check_http(backend_health_url)
    web_ok, web_status_code, web_latency_ms = _check_http(web_health_url)

    open_bug_reports = (
        db.query(func.count(BugReport.id))
        .filter(BugReport.status.in_(["open", "triaged"]))
        .scalar()
        or 0
    )
    open_support_tickets = (
        db.query(func.count(SupportMessage.id))
        .filter(SupportMessage.status.in_(["open", "pending"]))
        .scalar()
        or 0
    )

    return SystemStatusResponse(
        backend_ok=backend_ok,
        backend_status_code=backend_status_code,
        backend_latency_ms=backend_latency_ms,
        web_ok=web_ok,
        web_status_code=web_status_code,
        web_latency_ms=web_latency_ms,
        open_bug_reports=open_bug_reports,
        open_support_tickets=open_support_tickets,
        generated_at=_now_utc(),
    )


@router.get("/users/panel", response_model=UsersPanelResponse)
def users_panel(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    premium_users = db.query(func.count(User.id)).filter(User.is_premium.is_(True)).scalar() or 0
    free_users = max(total_users - premium_users, 0)

    latest_seen_subq = (
        db.query(
            UserDevice.user_id.label("user_id"),
            func.max(UserDevice.last_seen_at).label("last_seen_at"),
        )
        .group_by(UserDevice.user_id)
        .subquery()
    )
    latest_devices = (
        db.query(UserDevice.user_id, UserDevice.platform)
        .join(
            latest_seen_subq,
            and_(
                UserDevice.user_id == latest_seen_subq.c.user_id,
                UserDevice.last_seen_at == latest_seen_subq.c.last_seen_at,
            ),
        )
        .all()
    )

    platform_counts: dict[str, int] = defaultdict(int)
    for _, platform in latest_devices:
        key = _normalize(platform)
        if key in {"web", "android", "ios"}:
            platform_counts[key] += 1
        else:
            platform_counts["unknown"] += 1

    known_total = platform_counts["web"] + platform_counts["android"] + platform_counts["ios"] + platform_counts["unknown"]
    unknown_extra = max(total_users - known_total, 0)

    return UsersPanelResponse(
        total_users=total_users,
        by_platform=PlatformBreakdown(
            web=platform_counts["web"],
            android=platform_counts["android"],
            ios=platform_counts["ios"],
            unknown=platform_counts["unknown"] + unknown_extra,
        ),
        by_tier=TierBreakdown(
            free=free_users,
            premium=premium_users,
        ),
        generated_at=_now_utc(),
    )


@router.post("/email/campaigns", response_model=EmailCampaignResponse, status_code=201)
def create_email_campaign(
    payload: EmailCampaignCreate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    target_platform = _normalize(payload.target_platform)
    target_tier = _normalize(payload.target_tier)
    if target_platform not in {"all", "web", "android", "ios"}:
        raise HTTPException(status_code=422, detail="target_platform must be all, web, android, ios")
    if target_tier not in VALID_TIERS:
        raise HTTPException(status_code=422, detail="target_tier must be all, free, premium")

    campaign = EmailCampaign(
        name=payload.name.strip(),
        subject=payload.subject.strip(),
        body=payload.body,
        target_platform=target_platform,
        target_tier=target_tier,
        status="queued",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    recipients = _select_email_targets(db, target_platform, target_tier)
    try:
        _send_campaign_email(recipients, campaign.subject, campaign.body)
        campaign.status = "sent"
        campaign.sent_count = len(recipients)
        campaign.sent_at = _now_utc()
    except Exception as exc:
        campaign.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to send campaign: {exc}")

    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/email/campaigns", response_model=list[EmailCampaignResponse])
def list_email_campaigns(
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return db.query(EmailCampaign).order_by(EmailCampaign.created_at.desc()).limit(limit).all()


@router.post("/finance/entries", response_model=FinanceEntryResponse, status_code=201)
def create_finance_entry(
    payload: FinanceEntryCreate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    entry_type = _normalize(payload.entry_type)
    if entry_type not in VALID_FINANCE_TYPES:
        raise HTTPException(status_code=422, detail="entry_type must be income or expense")
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be greater than zero")

    row = FinanceEntry(
        entry_type=entry_type,
        category=payload.category.strip(),
        amount=payload.amount,
        note=payload.note,
        occurred_at=payload.occurred_at or _now_utc(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/finance/entries", response_model=list[FinanceEntryResponse])
def list_finance_entries(
    limit: int = Query(default=300, ge=1, le=2000),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return db.query(FinanceEntry).order_by(FinanceEntry.occurred_at.desc()).limit(limit).all()


@router.get("/finance/summary", response_model=FinanceSummaryResponse)
def finance_summary(
    days: int = Query(default=30, ge=7, le=365),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    since = _now_utc() - datetime.timedelta(days=days)
    rows = (
        db.query(FinanceEntry)
        .filter(FinanceEntry.occurred_at >= since)
        .order_by(FinanceEntry.occurred_at.asc())
        .all()
    )

    total_income = sum(r.amount for r in rows if r.entry_type == "income")
    total_expense = sum(r.amount for r in rows if r.entry_type == "expense")

    by_day: dict[str, dict[str, int]] = defaultdict(lambda: {"income": 0, "expense": 0})
    for row in rows:
        key = row.occurred_at.date().isoformat()
        by_day[key][row.entry_type] += row.amount

    points = [
        FinanceDailyPoint(day=day, income=vals["income"], expense=vals["expense"])
        for day, vals in sorted(by_day.items())
    ]

    return FinanceSummaryResponse(
        total_income=total_income,
        total_expense=total_expense,
        net=total_income - total_expense,
        points=points,
        generated_at=_now_utc(),
    )


@router.get("/support/recent", response_model=list[SupportResponse])
def recent_support_tickets(
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(SupportMessage)
        .order_by(SupportMessage.created_at.desc())
        .limit(limit)
        .all()
    )
