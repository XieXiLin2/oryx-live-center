"""Admin routes - Oryx management, user management, system config."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import settings
from app.database import get_db
from app.models import ChatMessage, User
from app.schemas import (
    UserBanRequest,
    UserListResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================
# Oryx API Proxy Helper
# ============================================================

async def _oryx_request(method: str, path: str, **kwargs) -> dict:
    """Make a request to the Oryx/SRS API."""
    url = f"{settings.oryx_api_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Oryx API error: {str(e)}")


# ============================================================
# User Management
# ============================================================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str = Query(""),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all users (admin only)."""
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if search:
        query = query.where(
            User.username.ilike(f"%{search}%") | User.display_name.ilike(f"%{search}%")
        )
        count_query = count_query.where(
            User.username.ilike(f"%{search}%") | User.display_name.ilike(f"%{search}%")
        )

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    result = await db.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    users = result.scalars().all()

    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


@router.put("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    request: UserBanRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Ban or unban a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot ban yourself")

    user.is_banned = request.is_banned
    await db.flush()
    return {"message": f"User {'banned' if request.is_banned else 'unbanned'}"}


@router.delete("/chat/messages/{message_id}")
async def delete_chat_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a chat message (admin only)."""
    result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    msg = result.scalar_one_or_none()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    await db.delete(msg)
    return {"message": "Chat message deleted"}


# ============================================================
# Oryx System Info
# ============================================================

@router.get("/oryx/system")
async def get_oryx_system_info(admin: User = Depends(require_admin)):
    """Get Oryx system information."""
    return await _oryx_request("GET", "/api/v1/summaries")


@router.get("/oryx/versions")
async def get_oryx_versions(admin: User = Depends(require_admin)):
    """Get Oryx version info."""
    return await _oryx_request("GET", "/api/v1/versions")


# ============================================================
# Oryx Streams Management
# ============================================================

@router.get("/oryx/streams")
async def get_oryx_streams(admin: User = Depends(require_admin)):
    """Get all streams from Oryx."""
    return await _oryx_request("GET", "/api/v1/streams/")


@router.get("/oryx/clients")
async def get_oryx_clients(admin: User = Depends(require_admin)):
    """Get all connected clients."""
    return await _oryx_request("GET", "/api/v1/clients/")


@router.delete("/oryx/clients/{client_id}")
async def kick_oryx_client(client_id: str, admin: User = Depends(require_admin)):
    """Kick a client from Oryx."""
    return await _oryx_request("DELETE", f"/api/v1/clients/{client_id}")


# ============================================================
# Oryx VHost Configuration
# ============================================================

@router.get("/oryx/vhosts")
async def get_oryx_vhosts(admin: User = Depends(require_admin)):
    """Get all vhosts."""
    return await _oryx_request("GET", "/api/v1/vhosts/")


@router.get("/oryx/vhosts/{vhost_id}")
async def get_oryx_vhost(vhost_id: str, admin: User = Depends(require_admin)):
    """Get a specific vhost."""
    return await _oryx_request("GET", f"/api/v1/vhosts/{vhost_id}")


# ============================================================
# Oryx DVR (Recording)
# ============================================================

@router.get("/oryx/dvr")
async def get_oryx_dvr(admin: User = Depends(require_admin)):
    """Get DVR configuration."""
    return await _oryx_request("GET", "/api/v1/dvrs/")


@router.post("/oryx/dvr")
async def update_oryx_dvr(config: dict, admin: User = Depends(require_admin)):
    """Update DVR configuration."""
    return await _oryx_request("POST", "/api/v1/dvrs/", json=config)


# ============================================================
# Oryx HLS Configuration
# ============================================================

@router.get("/oryx/hls")
async def get_oryx_hls(admin: User = Depends(require_admin)):
    """Get HLS configuration."""
    return await _oryx_request("GET", "/api/v1/hls/")


@router.post("/oryx/hls")
async def update_oryx_hls(config: dict, admin: User = Depends(require_admin)):
    """Update HLS configuration."""
    return await _oryx_request("POST", "/api/v1/hls/", json=config)


# ============================================================
# Oryx Forward (Relay/Restream)
# ============================================================

@router.get("/oryx/forward")
async def get_oryx_forwards(admin: User = Depends(require_admin)):
    """Get forward/relay configurations."""
    return await _oryx_request("GET", "/api/v1/forwards/")


@router.post("/oryx/forward")
async def create_oryx_forward(config: dict, admin: User = Depends(require_admin)):
    """Create a forward/relay configuration."""
    return await _oryx_request("POST", "/api/v1/forwards/", json=config)


@router.delete("/oryx/forward/{forward_id}")
async def delete_oryx_forward(forward_id: str, admin: User = Depends(require_admin)):
    """Delete a forward/relay configuration."""
    return await _oryx_request("DELETE", f"/api/v1/forwards/{forward_id}")


# ============================================================
# Oryx Transcode
# ============================================================

@router.get("/oryx/transcode")
async def get_oryx_transcodes(admin: User = Depends(require_admin)):
    """Get transcode configurations."""
    return await _oryx_request("GET", "/api/v1/transcodes/")


@router.post("/oryx/transcode")
async def create_oryx_transcode(config: dict, admin: User = Depends(require_admin)):
    """Create a transcode configuration."""
    return await _oryx_request("POST", "/api/v1/transcodes/", json=config)


@router.delete("/oryx/transcode/{transcode_id}")
async def delete_oryx_transcode(transcode_id: str, admin: User = Depends(require_admin)):
    """Delete a transcode configuration."""
    return await _oryx_request("DELETE", f"/api/v1/transcodes/{transcode_id}")


# ============================================================
# Oryx Callback (HTTP Hooks)
# ============================================================

@router.get("/oryx/hooks")
async def get_oryx_hooks(admin: User = Depends(require_admin)):
    """Get HTTP callback/hook configurations."""
    return await _oryx_request("GET", "/api/v1/hooks/")


@router.post("/oryx/hooks")
async def update_oryx_hooks(config: dict, admin: User = Depends(require_admin)):
    """Update HTTP callback/hook configurations."""
    return await _oryx_request("POST", "/api/v1/hooks/", json=config)


# ============================================================
# Oryx Raw Config (for advanced usage)
# ============================================================

@router.get("/oryx/raw")
async def get_oryx_raw_config(admin: User = Depends(require_admin)):
    """Get raw SRS config."""
    return await _oryx_request("GET", "/api/v1/raw")


@router.post("/oryx/raw")
async def update_oryx_raw_config(config: dict, admin: User = Depends(require_admin)):
    """Update raw SRS config. Use with caution."""
    return await _oryx_request("POST", "/api/v1/raw", json=config)


# ============================================================
# CDN Configuration
# ============================================================

@router.get("/cdn/config")
async def get_cdn_config(admin: User = Depends(require_admin)):
    """Get CDN configuration."""
    return {
        "cdn_base_url": settings.cdn_base_url,
        "cdn_pull_secret": "***" if settings.cdn_pull_secret else "",
    }


@router.get("/settings")
async def get_app_settings(admin: User = Depends(require_admin)):
    """Get application settings (non-sensitive)."""
    return {
        "app_name": settings.app_name,
        "oryx_api_url": settings.oryx_api_url,
        "oryx_http_url": settings.oryx_http_url,
        "cdn_base_url": settings.cdn_base_url,
        "oauth2_admin_group": settings.oauth2_admin_group,
    }
