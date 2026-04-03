import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr

# Auth Schemas
class GoogleLoginRequest(BaseModel):
    id_token: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# User Schemas
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
