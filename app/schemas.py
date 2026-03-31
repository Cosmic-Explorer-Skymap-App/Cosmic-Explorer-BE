import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator

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
    id: int
    is_premium: bool
    premium_until: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class UserStatusResponse(BaseModel):
    is_premium: bool = False
    is_trial_active: bool = False
    show_ads: bool = True
    premium_until: Optional[datetime.datetime] = None
    trial_ends_at: Optional[datetime.datetime] = None

# AI Schemas
class AstrologyAIRequest(BaseModel):
    sign: str
    birth_date: Optional[str] = None
    question: Optional[str] = None

    @field_validator("sign")
    @classmethod
    def sign_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("sign cannot be empty")
        if len(v) > 50:
            raise ValueError("sign is too long")
        return v

    @field_validator("question")
    @classmethod
    def question_max_length(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            raise ValueError("question must be 500 characters or fewer")
        return v

class AstrologyAIResponse(BaseModel):
    prediction: str
    success: bool
    message: Optional[str] = None
