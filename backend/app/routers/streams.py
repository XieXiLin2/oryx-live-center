"""Stream routes - list live streams, get play URLs."""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.config import settings
from app.database import get_db
from app.models import StreamConfig, User
from app.schemas import (
    StreamConfigRequest,
    StreamConfigResponse,
    StreamInfo,
    StreamListResponse,
    StreamPlayRequest,
    StreamPlayResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/streams", tags=["streams"])


async def _get_oryx_streams() -> list[dict]:
    """Fetch live streams from Oryx/SRS API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.oryx_api_url}/api/v1/streams/")
            response.raise_for_status()
            data = response.json()
            return data.get("streams", [])
    except Exception as e:
        logger.error(f"Failed to fetch streams from Oryx: {e}")
        return []


def _get_stream_formats(stream: dict) -> list[str]:
    """Determine available formats for a stream."""
    formats = ["flv", "hls"]
    # SRS supports these by default
    if stream.get("video"):
        formats.append("webrtc")
    return formats


def _build_stream_url(stream_name: str, app: str, fmt: str) -> str:
    """Build a stream play URL based on format."""
    base = settings.cdn_base_url or settings.oryx_http_url
    if fmt == "flv":
        return f"{base}/{app}/{stream_name}.flv"
    elif fmt == "hls":
        return f"{base}/{app}/{stream_name}.m3u8"
    elif fmt == "webrtc":
        return f"{base}/rtc/v1/whep/?app={app}&stream={stream_name}"
    elif fmt == "rtmp":
        return f"rtmp://{base.replace('http://', '').replace('https://', '')}/{app}/{stream_name}"
    else:
        return f"{base}/{app}/{stream_name}.flv"


@router.get("/", response_model=StreamListResponse)
async def list_streams(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    """List all online live streams."""
    oryx_streams = await _get_oryx_streams()

    streams = []
    for s in oryx_streams:
        name = s.get("name", "")
        app = s.get("app", "live")

        # Check stream config
        result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == name))
        config = result.scalar_one_or_none()

        display_name = name
        is_encrypted = False
        require_auth = False

        if config:
            display_name = config.display_name or name
            is_encrypted = config.is_encrypted
            require_auth = config.require_auth

        video = s.get("video", {})
        audio = s.get("audio", {})

        streams.append(
            StreamInfo(
                name=name,
                display_name=display_name,
                app=app,
                video_codec=video.get("codec") if video else None,
                audio_codec=audio.get("codec") if audio else None,
                clients=s.get("clients", 0),
                is_encrypted=is_encrypted,
                require_auth=require_auth,
                formats=_get_stream_formats(s),
            )
        )

    return StreamListResponse(streams=streams)


@router.post("/play", response_model=StreamPlayResponse)
async def get_play_url(
    request: StreamPlayRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    """Get play URL for a stream. Handles authentication and encryption."""
    # Check stream config
    result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == request.stream_name))
    config = result.scalar_one_or_none()

    if config:
        # Check if auth required
        if config.require_auth and user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to watch this stream",
            )

        # Check encryption key
        if config.is_encrypted and config.encryption_key:
            if request.key != config.encryption_key:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid stream key",
                )

    # Determine app name from oryx
    oryx_streams = await _get_oryx_streams()
    app = "live"
    for s in oryx_streams:
        if s.get("name") == request.stream_name:
            app = s.get("app", "live")
            break

    url = _build_stream_url(request.stream_name, app, request.format)

    return StreamPlayResponse(
        url=url,
        stream_name=request.stream_name,
        format=request.format,
    )


# ---- Admin: Stream Config ----


@router.get("/config", response_model=list[StreamConfigResponse])
async def list_stream_configs(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all stream configurations (admin only)."""
    result = await db.execute(select(StreamConfig).order_by(StreamConfig.stream_name))
    configs = result.scalars().all()
    return [StreamConfigResponse.model_validate(c) for c in configs]


@router.put("/config/{stream_name}", response_model=StreamConfigResponse)
async def update_stream_config(
    stream_name: str,
    request: StreamConfigRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create or update stream configuration (admin only)."""
    result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == stream_name))
    config = result.scalar_one_or_none()

    if config is None:
        config = StreamConfig(stream_name=stream_name)
        db.add(config)

    if request.display_name is not None:
        config.display_name = request.display_name
    if request.is_encrypted is not None:
        config.is_encrypted = request.is_encrypted
    if request.encryption_key is not None:
        config.encryption_key = request.encryption_key
    if request.require_auth is not None:
        config.require_auth = request.require_auth

    await db.flush()
    await db.refresh(config)
    return StreamConfigResponse.model_validate(config)


@router.delete("/config/{stream_name}")
async def delete_stream_config(
    stream_name: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete stream configuration (admin only)."""
    result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == stream_name))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Stream config not found")

    await db.delete(config)
    return {"message": "Stream config deleted"}
