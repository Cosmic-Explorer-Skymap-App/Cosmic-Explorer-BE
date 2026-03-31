import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import auth, user, ai

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Cosmic Explorer API",
    description="Backend for Cosmic Explorer App with Google Auth and Astrology AI.",
    version="1.0.0"
)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(ai.router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Cosmic Explorer API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
