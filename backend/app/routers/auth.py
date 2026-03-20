"""Authentication routes - OAuth2 login/register via Authentik."""

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    exchange_oauth_token,
    get_oauth_userinfo,
    require_user,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import AuthURLResponse, OAuthCallbackRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory state store for CSRF protection
_oauth_states: dict[str, bool] = {}


@router.get("/login", response_model=AuthURLResponse)
async def get_login_url():
    """Get OAuth2 authorization URL to redirect user."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = True

    params = {
        "response_type": "code",
        "client_id": settings.oauth2_client_id,
        "redirect_uri": settings.oauth2_redirect_uri,
        "scope": settings.oauth2_scope,
        "state": state,
    }
    authorize_url = f"{settings.oauth2_authorize_url}?{urlencode(params)}"
    return AuthURLResponse(authorize_url=authorize_url)


@router.post("/callback", response_model=TokenResponse)
async def oauth_callback(
    request: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth2 callback - exchange code for token and create/update user."""
    # Verify state
    if request.state and request.state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )
    if request.state:
        _oauth_states.pop(request.state, None)

    # Exchange code for tokens
    try:
        token_data = await exchange_oauth_token(request.code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange OAuth token: {str(e)}",
        )

    # Get user info
    try:
        userinfo = await get_oauth_userinfo(token_data["access_token"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get user info: {str(e)}",
        )

    # Find or create user
    oauth_sub = userinfo.get("sub", "")
    if not oauth_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth provider did not return a subject identifier",
        )

    result = await db.execute(select(User).where(User.oauth_sub == oauth_sub))
    user = result.scalar_one_or_none()

    # Check if user is in admin group
    groups = userinfo.get("groups", [])
    is_admin = settings.oauth2_admin_group in groups

    if user is None:
        # Create new user
        user = User(
            oauth_sub=oauth_sub,
            username=userinfo.get("preferred_username", userinfo.get("name", "")),
            display_name=userinfo.get("name", userinfo.get("preferred_username", "")),
            email=userinfo.get("email", ""),
            avatar_url=userinfo.get("picture", ""),
            is_admin=is_admin,
        )
        db.add(user)
        await db.flush()
    else:
        # Update existing user
        user.username = userinfo.get("preferred_username", user.username)
        user.display_name = userinfo.get("name", user.display_name)
        user.email = userinfo.get("email", user.email)
        user.avatar_url = userinfo.get("picture", user.avatar_url)
        user.is_admin = is_admin
        await db.flush()

    # Create JWT
    access_token = create_access_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(require_user)):
    """Get current user info."""
    return UserResponse.model_validate(user)


@router.get("/logout")
async def logout():
    """Get OAuth2 logout URL."""
    if settings.oauth2_logout_url:
        return {"logout_url": settings.oauth2_logout_url}
    return {"logout_url": None}
