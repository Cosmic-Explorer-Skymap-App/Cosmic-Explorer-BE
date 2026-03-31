import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    google_id = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True) # For traditional login fallback
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    last_ai_query_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

    @property
    def has_active_trial(self) -> bool:
        trial_duration = datetime.timedelta(days=5)
        now = datetime.datetime.now(datetime.timezone.utc)
        # Ensure created_at is aware
        created_at = self.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
        return now <= created_at + trial_duration

    @property
    def trial_ends_at(self) -> datetime.datetime:
        trial_duration = datetime.timedelta(days=5)
        created_at = self.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
        return created_at + trial_duration

    @property
    def is_premium_active(self) -> bool:
        if self.is_premium:
            now = datetime.datetime.now(datetime.timezone.utc)
            premium_until = self.premium_until
            if premium_until:
                if premium_until.tzinfo is None:
                    premium_until = premium_until.replace(tzinfo=datetime.timezone.utc)
                if premium_until < now:
                    return False
            return True
        return False

    @property
    def can_access_premium(self) -> bool:
        return True
