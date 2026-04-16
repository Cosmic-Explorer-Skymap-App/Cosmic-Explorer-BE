import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import admin, auth, user, posts, follows, likes, comments, profile, support, messages

logger = logging.getLogger(__name__)


def _get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        logger.warning(
            "ALLOWED_ORIGINS is not set — defaulting to ['*']. "
            "Set this variable before going to production."
        )
        return ["*"]
    return origins


def _validate_startup_config() -> None:
    missing = []
    if not os.getenv("SECRET_KEY"):
        missing.append("SECRET_KEY")
    if not os.getenv("GOOGLE_CLIENT_ID") and not os.getenv("GOOGLE_SERVER_CLIENT_ID"):
        missing.append("GOOGLE_CLIENT_ID or GOOGLE_SERVER_CLIENT_ID")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_startup_config()
    # Ensure media directory exists
    media_dir = Path(os.getenv("MEDIA_DIR", "/app/media"))
    media_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Cosmic Explorer API",
    description="Backend for Cosmic Explorer App with Google Auth and Astrology AI.",
    version="1.0.2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Serve uploaded media files
_media_dir = Path(os.getenv("MEDIA_DIR", "/app/media"))
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(posts.router)
app.include_router(follows.router)
app.include_router(likes.router)
app.include_router(comments.router)
app.include_router(profile.router)
app.include_router(support.router)
app.include_router(messages.router)
app.include_router(admin.router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Cosmic Explorer API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
