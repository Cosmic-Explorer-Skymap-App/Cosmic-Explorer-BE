import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests

from ..database import get_db
from ..models import User
from ..schemas import GoogleLoginRequest, Token
from ..auth_utils import create_access_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_web_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
_server_client_id = os.getenv("GOOGLE_SERVER_CLIENT_ID", "")
ALLOWED_GOOGLE_CLIENT_IDS = [cid for cid in [_web_client_id, _server_client_id] if cid]

@router.post("/google", response_model=Token)
def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    # Verify Google ID Token against all registered client IDs (web + mobile)
    idinfo = None
    last_error = None
    for client_id in ALLOWED_GOOGLE_CLIENT_IDS:
        try:
            idinfo = id_token.verify_oauth2_token(request.id_token, requests.Request(), client_id)
            break
        except ValueError as e:
            last_error = e

    if idinfo is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID Token: {str(last_error)}"
        )

    userid = idinfo['sub']
    email = idinfo['email']

    # Check if user exists in DB
    user = db.query(User).filter(User.email == email).first()

    google_picture = idinfo.get("picture")

    if not user:
        # Create new user
        user = User(
            email=email,
            google_id=userid,
            is_premium=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_id:
        # Link google_id if email matches but Google login wasn't used before
        user.google_id = userid
        db.commit()

    # Sync Google profile picture to UserProfile if not already set
    if google_picture and user.profile and not user.profile.avatar_url:
        user.profile.avatar_url = google_picture
        db.commit()

    # Create JWT Access Token
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
