"""SRS HTTP hooks endpoints.

SRS posts to these URLs on live events so the backend can:
  * Authorize publishers (on_publish)
  * Authorize viewers (on_play) for private streams
  * Track live sessions and viewer statistics (on_publish/on_unpublish/on_play/on_stop)

SRS protocol:
  * Return HTTP 200 with JSON body {"code": 0}  → allowed
  * Return HTTP 200 with JSON body {"code": <non-zero>} or any non-200 → rejected

Callbacks configured in srs.conf:
  http_hooks {
      enabled         on;
      on_publish      http://app:8000/api/hooks/on_publish;
      on_unpublish    http://app:8000/api/hooks/on_unpublish;
      on_play         http://app:8000/api/hooks/on_play;
      on_stop         http://app:8000/api/hooks/on_stop;
  }
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_access_token
from app.config import settings
from app.database import get_db
from app.models import StreamConfig, StreamPublishSession, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hooks", tags=["srs-hooks"])


ALLOW = {"code": 0}
DENY_NOT_FOUND = {"code": 404, "msg": "stream not configured"}
DENY_UNAUTH = {"code": 401, "msg": "unauthorized"}
DENY_FORBIDDEN = {"code": 403, "msg": "forbidden"}
DENY_SECRET = {"code": 403, "msg": "invalid publish secret"}


def _parse_param(param: str) -> dict[str, str]:
    """Parse the SRS `param` field (e.g. "?secret=abc&token=xxx") into a dict."""
    if not param:
        return {}
    s = param.lstrip("?")
    parsed = parse_qs(s)
    # parse_qs returns list values; flatten to single-value dict.
    return {k: v[0] for k, v in parsed.items() if v}


async def _verify_hook_secret(request: Request) -> bool:
    """If a hook secret is configured, verify SRS included it in the URL."""
    if not settings.srs_hook_secret:
        return True
    qs_val = request.query_params.get("hook_secret") or request.query_params.get("secret")
    return qs_val == settings.srs_hook_secret


async def _resolve_user(token: str | None, db: AsyncSession) -> User | None:
    """Try decoding a JWT token and fetching the user."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        result = await db.execute(select(User).where(User.id == int(user_id)))
        return result.scalar_one_or_none()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# on_publish — publisher authorization + start of live
# ---------------------------------------------------------------------------


@router.post("/on_publish")
async def on_publish(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not await _verify_hook_secret(request):
        logger.warning("on_publish rejected: bad hook secret")
        return DENY_UNAUTH

    body = await request.json()
    stream_name = body.get("stream", "")
    client_id = str(body.get("client_id", ""))
    ip = body.get("ip", "")
    param = _parse_param(body.get("param", ""))

    logger.info("on_publish stream=%s ip=%s client=%s", stream_name, ip, client_id)

    # Look up room config; refuse publish if room is not configured.
    result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == stream_name))
    config = result.scalar_one_or_none()
    if config is None:
        logger.warning("on_publish rejected: stream %s not configured", stream_name)
        return DENY_NOT_FOUND

    # Verify publish secret (push key) — each room has its own key.
    supplied = param.get("secret") or param.get("key") or ""
    if not config.publish_secret or supplied != config.publish_secret:
        logger.warning("on_publish rejected: bad publish secret for %s", stream_name)
        return DENY_SECRET

    # Update live state.
    config.is_live = True
    config.viewer_count = 0
    config.last_publish_at = dt.datetime.now(dt.timezone.utc)

    db.add(StreamPublishSession(
        srs_client_id=client_id,
        stream_name=stream_name,
        client_ip=ip,
        started_at=dt.datetime.now(dt.timezone.utc),
    ))
    await db.flush()
    return ALLOW


# ---------------------------------------------------------------------------
# on_unpublish — publisher stopped streaming
# ---------------------------------------------------------------------------


@router.post("/on_unpublish")
async def on_unpublish(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not await _verify_hook_secret(request):
        return ALLOW  # don't block cleanup

    body = await request.json()
    stream_name = body.get("stream", "")
    client_id = str(body.get("client_id", ""))

    logger.info("on_unpublish stream=%s client=%s", stream_name, client_id)

    now = dt.datetime.now(dt.timezone.utc)

    # Update room state.
    result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == stream_name))
    config = result.scalar_one_or_none()
    if config is not None:
        config.is_live = False
        config.viewer_count = 0
        config.last_unpublish_at = now

    # Close publish session.
    if client_id:
        result = await db.execute(
            select(StreamPublishSession)
            .where(StreamPublishSession.srs_client_id == client_id)
            .where(StreamPublishSession.ended_at.is_(None))
            .order_by(StreamPublishSession.id.desc())
        )
        sess = result.scalars().first()
        if sess is not None:
            sess.ended_at = now
            if sess.started_at:
                sess.duration_seconds = int((now - sess.started_at).total_seconds())

    await db.flush()
    return ALLOW


# ---------------------------------------------------------------------------
# on_play — viewer authorization + viewer counter increment
# ---------------------------------------------------------------------------


@router.post("/on_play")
async def on_play(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not await _verify_hook_secret(request):
        return DENY_UNAUTH

    body = await request.json()
    stream_name = body.get("stream", "")
    client_id = str(body.get("client_id", ""))
    ip = body.get("ip", "")
    param = _parse_param(body.get("param", ""))

    # Look up room config. If not configured at all, we still allow play
    # (treating it as a public / ad-hoc stream) but we won't statistically track it.
    result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == stream_name))
    config = result.scalar_one_or_none()

    user: User | None = None
    if config is not None and config.is_private:
        # Private stream: need a valid watch_token OR a logged-in user's JWT.
        token = param.get("token") or ""
        jwt_token = param.get("jwt") or ""

        if config.watch_token and token and token == config.watch_token:
            authorized = True
        else:
            user = await _resolve_user(jwt_token, db)
            authorized = user is not None and not user.is_banned

        if not authorized:
            logger.warning("on_play rejected: unauthorized viewer for private stream %s", stream_name)
            return DENY_FORBIDDEN

    # Authorization passed. Viewer count tracking is now handled by the
    # WebSocket-driven ViewerSession (see routers/viewer.py), not by hooks.
    logger.info("on_play stream=%s ip=%s client=%s user=%s", stream_name, ip, client_id, user.id if user else None)
    return ALLOW


# ---------------------------------------------------------------------------
# on_stop — viewer disconnected
# ---------------------------------------------------------------------------


@router.post("/on_stop")
async def on_stop(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not await _verify_hook_secret(request):
        return ALLOW

    body = await request.json()
    stream_name = body.get("stream", "")
    client_id = str(body.get("client_id", ""))

    # Viewer disconnected. Viewer count tracking is now handled by the
    # WebSocket-driven ViewerSession (see routers/viewer.py), not by hooks.
    logger.info("on_stop stream=%s client=%s", stream_name, client_id)
    return ALLOW


# ---------------------------------------------------------------------------
# Optional: on_connect / on_close / on_dvr / on_hls can be added later.
# ---------------------------------------------------------------------------


@router.post("/on_connect")
async def on_connect(request: Request) -> dict[str, Any]:
    """SRS on_connect — allow all; the actual ACL happens on on_play/on_publish."""
    if not await _verify_hook_secret(request):
        return DENY_UNAUTH
    return ALLOW


@router.post("/on_close")
async def on_close(request: Request) -> dict[str, Any]:
    return ALLOW


# ---------------------------------------------------------------------------
# Debug: query-string based ping for SRS config testing.
# ---------------------------------------------------------------------------


@router.get("/ping")
async def ping(secret: str = Query(default="")) -> dict[str, Any]:
    ok = (not settings.srs_hook_secret) or (secret == settings.srs_hook_secret)
    return {"code": 0 if ok else 401, "ok": ok}
