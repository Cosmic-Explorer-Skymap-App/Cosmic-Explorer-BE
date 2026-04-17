import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

class GoogleLoginRequest(BaseModel):
    id_token: str

class Token(BaseModel):
    access_token: str
    token_type: str


class SessionStatusResponse(BaseModel):
    authenticated: bool

class TokenData(BaseModel):
    email: Optional[str] = None

# ---------------------------------------------------------------------------
# User Schemas
# ---------------------------------------------------------------------------

class UserStatusResponse(BaseModel):
    is_premium: bool = False
    is_trial_active: bool = False
    show_ads: bool = True
    premium_until: Optional[datetime.datetime] = None
    trial_ends_at: Optional[datetime.datetime] = None

# ---------------------------------------------------------------------------
# UserProfile Schemas
# ---------------------------------------------------------------------------

class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    follower_count: int
    following_count: int
    post_count: int
    is_following: bool = False  # computed: does current user follow this profile?

class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None

class UsernameSetup(BaseModel):
    username: str
    display_name: Optional[str] = None

# ---------------------------------------------------------------------------
# Post Schemas
# ---------------------------------------------------------------------------

class PostCreate(BaseModel):
    title: str
    caption: Optional[str] = None

class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    image_url: str
    title: str
    caption: Optional[str] = None
    like_count: int
    comment_count: int
    is_liked_by_me: bool = False
    created_at: datetime.datetime

class FeedResponse(BaseModel):
    posts: List[PostResponse]
    # IMPORTANT: cursor semantics differ per endpoint.
    # /feed and /user/{id}  → next_cursor is the last Post.id (keyset pagination).
    # /explore              → next_cursor is a numeric offset (offset-based pagination,
    #                         because the sort key is like_count which is not unique).
    # Always pass next_cursor back as the `cursor` query param for the *same* endpoint only.
    next_cursor: Optional[int] = None
    has_more: bool

# ---------------------------------------------------------------------------
# Comment Schemas
# ---------------------------------------------------------------------------

class CommentCreate(BaseModel):
    content: str

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    post_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    content: str
    created_at: datetime.datetime

# ---------------------------------------------------------------------------
# Message / DM Schemas
# ---------------------------------------------------------------------------

class MessageSend(BaseModel):
    content: str

class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int
    content: str
    is_read: bool
    created_at: datetime.datetime

class ConversationParticipant(BaseModel):
    user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

class ConversationResponse(BaseModel):
    id: int
    other_user: ConversationParticipant
    last_message: Optional[MessageResponse] = None
    unread_count: int
    last_message_at: datetime.datetime

# ---------------------------------------------------------------------------
# Support Schemas
# ---------------------------------------------------------------------------

class SupportCreate(BaseModel):
    full_name: str
    email: str
    subject: str
    message: str

class SupportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    full_name: str
    email: str
    subject: str
    message: str
    image_url: Optional[str] = None
    status: str
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Admin Schemas
# ---------------------------------------------------------------------------

class AdminSupportBreakdown(BaseModel):
    open: int
    pending: int
    closed: int


class AdminOverviewResponse(BaseModel):
    total_users: int
    premium_users: int
    total_posts: int
    total_comments: int
    total_likes: int
    total_conversations: int
    total_messages: int
    open_reports: int
    support: AdminSupportBreakdown
    generated_at: datetime.datetime


class DeviceHeartbeatRequest(BaseModel):
    platform: str
    app_version: Optional[str] = None


class SocialConnectionCreate(BaseModel):
    platform: str
    account_name: str
    account_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime.datetime] = None


class SocialConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    account_name: str
    account_id: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SocialContentCreate(BaseModel):
    platform: str
    connection_id: Optional[int] = None
    title: str
    body: Optional[str] = None
    media_url: Optional[str] = None
    status: str = "draft"
    scheduled_at: Optional[datetime.datetime] = None


class SocialContentStatusUpdate(BaseModel):
    status: str


class SocialContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    connection_id: Optional[int] = None
    title: str
    body: Optional[str] = None
    media_url: Optional[str] = None
    status: str
    scheduled_at: Optional[datetime.datetime] = None
    published_at: Optional[datetime.datetime] = None
    impressions: int
    clicks: int
    conversions: int
    spend: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SocialAnalyticsSummary(BaseModel):
    total_contents: int
    total_impressions: int
    total_clicks: int
    total_conversions: int
    total_spend: int
    ctr: float
    conversion_rate: float


class BugReportCreate(BaseModel):
    source_platform: str
    severity: str
    title: str
    description: str


class BugReportStatusUpdate(BaseModel):
    status: str


class BugReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    source_platform: str
    severity: str
    title: str
    description: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SystemStatusResponse(BaseModel):
    backend_ok: bool
    backend_status_code: Optional[int] = None
    backend_latency_ms: Optional[int] = None
    web_ok: bool
    web_status_code: Optional[int] = None
    web_latency_ms: Optional[int] = None
    open_bug_reports: int
    open_support_tickets: int
    generated_at: datetime.datetime


class PlatformBreakdown(BaseModel):
    web: int
    android: int
    ios: int
    unknown: int


class TierBreakdown(BaseModel):
    free: int
    premium: int


class UsersPanelResponse(BaseModel):
    total_users: int
    by_platform: PlatformBreakdown
    by_tier: TierBreakdown
    generated_at: datetime.datetime


class EmailCampaignCreate(BaseModel):
    name: str
    subject: str
    body: str
    target_platform: str = "all"
    target_tier: str = "all"


class EmailCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject: str
    body: str
    target_platform: Optional[str] = None
    target_tier: Optional[str] = None
    status: str
    sent_count: int
    created_at: datetime.datetime
    sent_at: Optional[datetime.datetime] = None


class FinanceEntryCreate(BaseModel):
    entry_type: str
    category: str
    amount: int
    note: Optional[str] = None
    occurred_at: Optional[datetime.datetime] = None


class FinanceEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_type: str
    category: str
    amount: int
    note: Optional[str] = None
    occurred_at: datetime.datetime
    created_at: datetime.datetime


class FinanceDailyPoint(BaseModel):
    day: str
    income: int
    expense: int


class FinanceSummaryResponse(BaseModel):
    total_income: int
    total_expense: int
    net: int
    points: List[FinanceDailyPoint]
    generated_at: datetime.datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: Optional[int] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime.datetime


class UserSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_jti: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    platform: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime
    last_seen_at: datetime.datetime
    revoked_at: Optional[datetime.datetime] = None


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    event_type: str
    severity: str
    ip_address: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime.datetime


class LoginAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    ip_address: Optional[str] = None
    success: bool
    failure_reason: Optional[str] = None
    created_at: datetime.datetime


class LoginAbuseSummaryResponse(BaseModel):
    last_24h_total: int
    last_24h_success: int
    last_24h_failed: int
    top_failed_ips: List[str]
    generated_at: datetime.datetime


class SecuritySettingsUpdate(BaseModel):
    two_factor_enabled: bool


class SecuritySettingsResponse(BaseModel):
    two_factor_enabled: bool
    sessions: List[UserSessionResponse]
    recent_events: List[SecurityEventResponse]


class MalwareScanJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    support_message_id: int
    file_url: str
    status: str
    scanner: str
    notes: Optional[str] = None
    reviewed_by_user_id: Optional[int] = None
    created_at: datetime.datetime
    reviewed_at: Optional[datetime.datetime] = None


class MalwareScanReviewRequest(BaseModel):
    status: str
    notes: Optional[str] = None
