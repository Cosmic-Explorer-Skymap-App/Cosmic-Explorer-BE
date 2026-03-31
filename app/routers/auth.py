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

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your_google_client_id")

@router.post("/google", response_model=Token)
def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    # Verify Google ID Token
    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(request.id_token, requests.Request(), GOOGLE_CLIENT_ID)

        # Or, if multiple clients access the backend:
        # idinfo = id_token.verify_oauth2_token(request.id_token, requests.Request())
        # if idinfo['aud'] not in [CLIENT_ID_1, CLIENT_ID_2]:
        #     raise ValueError('Could not verify audience.')

        # If auth request is from a G Suite domain:
        # if idinfo['hd'] != 'example.com':
        #     raise ValueError('Wrong domain.')

        # ID token is valid. Get the user's Google Account ID from the decoded token.
        userid = idinfo['sub']
        email = idinfo['email']

    except ValueError as e:
        # Invalid token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID Token: {str(e)}"
        )

    # Check if user exists in DB
    user = db.query(User).filter(User.email == email).first()

    if not user:
        # Create new user
        user = User(
            email=email,
            google_id=userid,
            is_premium=False # Default
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_id:
        # Link google_id if email matches but Google login wasn't used before
        user.google_id = userid
        db.commit()

    # Create JWT Access Token
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
