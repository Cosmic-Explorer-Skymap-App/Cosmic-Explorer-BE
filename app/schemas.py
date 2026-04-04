import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr

# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

class GoogleLoginRequest(BaseModel):
    id_token: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# ---------------------------------------------------------------------------
# User Schemas
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_premium: bool
    premium_until: Optional[datetime.datetime] = None
    created_at: datetime.datetime

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
    next_cursor: Optional[int] = None  # last post id in this batch
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
