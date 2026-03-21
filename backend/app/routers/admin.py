"""Admin routes - Oryx management, user management, system config."""

import logging

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


def _oryx_headers() -> dict:
    """Build auth headers for Oryx API requests."""
    headers = {}
    if settings.oryx_api_secret:
        headers["Authorization"] = f"Bearer {settings.oryx_api_secret}"
    return headers


async def _oryx_request(method: str, path: str, **kwargs) -> dict:
    """Make a request to the Oryx API.

    Oryx uses /terraform/v1/ prefix for its management API,
    and /api/v1/ (proxied from SRS) for stream/client queries.
    Auth is via Bearer token in Authorization header.
    """
    url = f"{settings.oryx_api_url}{path}"
    headers = kwargs.pop("headers", {})
    headers.update(_oryx_headers())
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Oryx API HTTP error: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Oryx API connection error: {e}")
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
        query = query.where(User.username.ilike(f"%{search}%") | User.display_name.ilike(f"%{search}%"))
        count_query = count_query.where(User.username.ilike(f"%{search}%") | User.display_name.ilike(f"%{search}%"))

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    result = await db.execute(query.order_by(User.created_at.desc()).offset(offset).limit(limit))
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
    """Get Oryx system information (SRS summaries)."""
    return await _oryx_request("GET", "/api/v1/summaries")


@router.get("/oryx/versions")
async def get_oryx_versions(admin: User = Depends(require_admin)):
    """Get Oryx version info."""
    return await _oryx_request("GET", "/api/v1/versions")


@router.get("/oryx/status")
async def get_oryx_status(admin: User = Depends(require_admin)):
    """Get Oryx platform status."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/status")


@router.get("/oryx/check")
async def get_oryx_check(admin: User = Depends(require_admin)):
    """Check if Oryx system is healthy."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/check")


# ============================================================
# Oryx Streams Management
# ============================================================


@router.get("/oryx/streams")
async def get_oryx_streams(admin: User = Depends(require_admin)):
    """Get all streams from Oryx (via SRS API)."""
    return await _oryx_request("GET", "/api/v1/streams/")


@router.post("/oryx/streams/query")
async def query_oryx_streams(admin: User = Depends(require_admin)):
    """Query active streams via Oryx management API."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/streams/query")


@router.post("/oryx/streams/kickoff")
async def kickoff_oryx_stream(
    body: dict,
    admin: User = Depends(require_admin),
):
    """Kick off a stream by name via Oryx management API."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/streams/kickoff", json=body)


@router.get("/oryx/clients")
async def get_oryx_clients(admin: User = Depends(require_admin)):
    """Get all connected clients (via SRS API)."""
    return await _oryx_request("GET", "/api/v1/clients/")


@router.delete("/oryx/clients/{client_id}")
async def kick_oryx_client(client_id: str, admin: User = Depends(require_admin)):
    """Kick a client from Oryx (via SRS API)."""
    return await _oryx_request("DELETE", f"/api/v1/clients/{client_id}")


# ============================================================
# Oryx Publish Secret (Stream Auth)
# ============================================================


@router.get("/oryx/secret")
async def get_oryx_secret(admin: User = Depends(require_admin)):
    """Get publish secret for stream authentication."""
    return await _oryx_request("POST", "/terraform/v1/hooks/srs/secret/query")


@router.post("/oryx/secret")
async def update_oryx_secret(config: dict, admin: User = Depends(require_admin)):
    """Update publish secret for stream authentication."""
    return await _oryx_request("POST", "/terraform/v1/hooks/srs/secret/update", json=config)


# ============================================================
# Oryx Virtual Live
# ============================================================


@router.get("/oryx/vlive")
async def get_oryx_vlive(admin: User = Depends(require_admin)):
    """Get virtual live streaming list."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/vlive/streams")


@router.post("/oryx/vlive")
async def update_oryx_vlive(config: dict, admin: User = Depends(require_admin)):
    """Update virtual live streaming configuration."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/vlive/secret", json=config)


# ============================================================
# Oryx Camera (IP Camera)
# ============================================================


@router.get("/oryx/camera")
async def get_oryx_camera(admin: User = Depends(require_admin)):
    """Get IP camera streaming list."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/camera/streams")


@router.post("/oryx/camera")
async def update_oryx_camera(config: dict, admin: User = Depends(require_admin)):
    """Update IP camera configuration."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/camera/secret", json=config)


# ============================================================
# Oryx Live Room
# ============================================================


@router.get("/oryx/rooms")
async def list_oryx_rooms(admin: User = Depends(require_admin)):
    """List all live rooms."""
    return await _oryx_request("POST", "/terraform/v1/live/room/list")


@router.post("/oryx/rooms/create")
async def create_oryx_room(config: dict, admin: User = Depends(require_admin)):
    """Create a new live room."""
    return await _oryx_request("POST", "/terraform/v1/live/room/create", json=config)


@router.post("/oryx/rooms/update")
async def update_oryx_room(config: dict, admin: User = Depends(require_admin)):
    """Update a live room."""
    return await _oryx_request("POST", "/terraform/v1/live/room/update", json=config)


@router.post("/oryx/rooms/remove")
async def remove_oryx_room(config: dict, admin: User = Depends(require_admin)):
    """Remove a live room."""
    return await _oryx_request("POST", "/terraform/v1/live/room/remove", json=config)


# ============================================================
# Oryx SRS Vhosts (via SRS API)
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
# Oryx DVR (Recording) - uses /terraform/v1/hooks/record/
# ============================================================


@router.get("/oryx/dvr")
async def get_oryx_dvr(admin: User = Depends(require_admin)):
    """Get record/DVR configuration."""
    return await _oryx_request("POST", "/terraform/v1/hooks/record/query")


@router.post("/oryx/dvr")
async def update_oryx_dvr(config: dict, admin: User = Depends(require_admin)):
    """Update record/DVR configuration."""
    return await _oryx_request("POST", "/terraform/v1/hooks/record/apply", json=config)


@router.get("/oryx/dvr/files")
async def list_oryx_dvr_files(admin: User = Depends(require_admin)):
    """List recorded files."""
    return await _oryx_request("POST", "/terraform/v1/hooks/record/files")


# ============================================================
# Oryx HLS Configuration
# ============================================================


@router.get("/oryx/hls")
async def get_oryx_hls(admin: User = Depends(require_admin)):
    """Get HLS delivery configuration."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/hphls/query")


@router.post("/oryx/hls")
async def update_oryx_hls(config: dict, admin: User = Depends(require_admin)):
    """Update HLS delivery configuration (high performance mode)."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/hphls/update", json=config)


@router.get("/oryx/hls/ll")
async def get_oryx_hls_ll(admin: User = Depends(require_admin)):
    """Get HLS low latency configuration."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/hlsll/query")


@router.post("/oryx/hls/ll")
async def update_oryx_hls_ll(config: dict, admin: User = Depends(require_admin)):
    """Update HLS low latency configuration."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/hlsll/update", json=config)


# ============================================================
# Oryx Forward (Relay/Restream)
# ============================================================


@router.get("/oryx/forward")
async def get_oryx_forwards(admin: User = Depends(require_admin)):
    """Get forward/relay stream list."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/forward/streams")


@router.post("/oryx/forward")
async def create_oryx_forward(config: dict, admin: User = Depends(require_admin)):
    """Create/update a forward/relay configuration."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/forward/secret", json=config)


# ============================================================
# Oryx Transcode
# ============================================================


@router.get("/oryx/transcode")
async def get_oryx_transcodes(admin: User = Depends(require_admin)):
    """Get transcode configuration."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/transcode/query")


@router.post("/oryx/transcode")
async def update_oryx_transcode(config: dict, admin: User = Depends(require_admin)):
    """Apply transcode configuration."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/transcode/apply", json=config)


@router.get("/oryx/transcode/task")
async def get_oryx_transcode_task(admin: User = Depends(require_admin)):
    """Query transcode task status."""
    return await _oryx_request("POST", "/terraform/v1/ffmpeg/transcode/task")


# ============================================================
# Oryx Callback (HTTP Hooks)
# ============================================================


@router.get("/oryx/hooks")
async def get_oryx_hooks(admin: User = Depends(require_admin)):
    """Get HTTP callback/hook configurations."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/hooks/query")


@router.post("/oryx/hooks")
async def update_oryx_hooks(config: dict, admin: User = Depends(require_admin)):
    """Update HTTP callback/hook configurations."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/hooks/apply", json=config)


# ============================================================
# Oryx Limits Configuration
# ============================================================


@router.get("/oryx/limits")
async def get_oryx_limits(admin: User = Depends(require_admin)):
    """Get system limits configuration."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/limits/query")


@router.post("/oryx/limits")
async def update_oryx_limits(config: dict, admin: User = Depends(require_admin)):
    """Update system limits configuration."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/limits/update", json=config)


# ============================================================
# Oryx SSL / HTTPS
# ============================================================


@router.get("/oryx/cert")
async def get_oryx_cert(admin: User = Depends(require_admin)):
    """Query SSL certificate status."""
    return await _oryx_request("POST", "/terraform/v1/mgmt/cert/query")


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
