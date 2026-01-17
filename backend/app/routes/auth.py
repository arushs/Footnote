import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Session, User

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


@router.get("/google")
async def google_login():
    """Redirect to Google OAuth consent screen."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback")
async def google_callback(
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback, exchange code for tokens, create session."""
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")

        tokens = token_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token", "")
        expires_in = tokens.get("expires_in", 3600)

        # Get user info from Google
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        userinfo = userinfo_response.json()

    # Find or create user
    result = await db.execute(select(User).where(User.google_id == userinfo["id"]))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            google_id=userinfo["id"],
            email=userinfo["email"],
        )
        db.add(user)
        await db.flush()

    # Create session with tokens
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    session = Session(
        user_id=user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    # Set session cookie (using session ID as the cookie value)
    redirect = RedirectResponse(url=f"{settings.frontend_url}/chat", status_code=302)
    redirect.set_cookie(
        key="session_id",
        value=str(session.id),
        httponly=True,
        secure=settings.frontend_url.startswith("https"),
        samesite="lax",
        max_age=settings.session_expire_hours * 3600,
    )

    return redirect


@router.post("/logout")
async def logout(
    response: Response,
    session_id: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Clear session and logout user."""
    if session_id:
        try:
            session_uuid = uuid.UUID(session_id)
            result = await db.execute(select(Session).where(Session.id == session_uuid))
            session = result.scalar_one_or_none()
            if session:
                await db.delete(session)
        except ValueError:
            pass  # Invalid UUID, ignore

    response.delete_cookie(key="session_id")
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(
    session_id: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated user info."""
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session") from None

    result = await db.execute(select(Session).where(Session.id == session_uuid))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Session not found")

    # Check if session is expired
    if session.expires_at < datetime.now(UTC):
        # Try to refresh the token
        session = await refresh_access_token(session, db)
        if not session:
            raise HTTPException(status_code=401, detail="Session expired")

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": str(user.id),
        "email": user.email,
        "google_id": user.google_id,
    }


async def refresh_access_token(session: Session, db: AsyncSession) -> Session | None:
    """Refresh an expired access token using the refresh token."""
    if not session.refresh_token:
        return None

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": session.refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if token_response.status_code != 200:
            # Refresh token is invalid, delete the session
            await db.delete(session)
            return None

        tokens = token_response.json()
        session.access_token = tokens["access_token"]
        session.expires_at = datetime.now(UTC) + timedelta(seconds=tokens.get("expires_in", 3600))
        # Google sometimes returns a new refresh token
        if "refresh_token" in tokens:
            session.refresh_token = tokens["refresh_token"]

        return session


async def get_current_session(
    session_id: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> Session:
    """Dependency to get the current valid session with a valid access token."""
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session") from None

    result = await db.execute(select(Session).where(Session.id == session_uuid))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Session not found")

    # Check if session is expired and refresh if needed
    if session.expires_at < datetime.now(UTC):
        session = await refresh_access_token(session, db)
        if not session:
            raise HTTPException(status_code=401, detail="Session expired")

    return session
