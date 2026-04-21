"""Viewer statistics via WebSocket — backend-driven, independent of SRS hooks.

Design
======
Playback statistics (concurrent viewers, total plays, watch seconds, peak
viewers, ...) used to be derived from SRS ``on_play`` / ``on_stop`` hooks.
Those hooks are kept intact for other purposes (legacy compatibility,
SRS-client-id bookkeeping), but **playback analytics are no longer derived
from them**. Instead, every player that actually *displays* the stream opens
a dedicated WebSocket to this endpoint, and the backend owns the full
session lifecycle:

* WS connected      → INSERT :class:`ViewerSession`
* every 15s ping    → UPDATE last_heartbeat_at
* WS disconnected   → close the session (ended_at + duration_seconds)
* heartbeat stale   → sweeper closes it (see stats_reconciler.py)

Each message the backend broadcasts on the connection carries the current
room statistics, so the frontend does not need to poll ``/stats`` anymore.

Authorization mirrors the chat endpoint:

* Public room            — anonymous allowed; JWT if supplied is honored.
* Private room, logged in — always allowed.
* Private room, token    — ``?token=`` must equal the room's ``watch_token``.
* Private room, neither  — WS closed with 4401.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.auth import decode_access_token
from app.database import async_session
from app.models import (
    StreamConfig,
    StreamPublishSession,
    User,
    ViewerSession,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/viewer", tags=["viewer"])


# ---------------------------------------------------------------------------
# In-memory connection registry
# ---------------------------------------------------------------------------


class ViewerConnectionManager:
    """Tracks active viewer WebSockets grouped by stream name.

    The DB-backed :class:`ViewerSession` is the *durable* record; this in-memory
    map is only used for fan-out (broadcasting stats updates to all viewers of
    the same room) and for tracking live-session peak concurrency.
    """

    def __init__(self) -> None:
        # stream_name → list of (WebSocket, session_key)
        self.active: dict[str, list[tuple[WebSocket, str]]] = {}
        # stream_name → highest concurrent count seen during the *current* live
        # session. Reset to 0 when the stream goes offline (handled by the
        # reconciler).
        self.peak: dict[str, int] = {}

    def add(self, stream_name: str, ws: WebSocket, session_key: str) -> int:
        bucket = self.active.setdefault(stream_name, [])
        bucket.append((ws, session_key))
        n = len(bucket)
        if n > self.peak.get(stream_name, 0):
            self.peak[stream_name] = n
        return n

    def remove(self, stream_name: str, ws: WebSocket) -> int:
        bucket = self.active.get(stream_name)
        if not bucket:
            return 0
        self.active[stream_name] = [(w, k) for (w, k) in bucket if w is not ws]
        if not self.active[stream_name]:
            del self.active[stream_name]
        return len(self.active.get(stream_name, []))

    def current_viewers(self, stream_name: str) -> int:
        return len(self.active.get(stream_name, []))

    def peak_viewers(self, stream_name: str) -> int:
        return self.peak.get(stream_name, 0)

    def reset_peak(self, stream_name: str) -> None:
        """Called by the reconciler when a stream goes offline."""
        self.peak.pop(stream_name, None)

    async def broadcast(self, stream_name: str, message: dict) -> None:
        bucket = list(self.active.get(stream_name, []))
        dead: list[WebSocket] = []
        for ws, _key in bucket:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(stream_name, ws)


manager = ViewerConnectionManager()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_user(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        uid = int(sub)
    except (TypeError, ValueError):
        return None
    async with async_session() as db:
        res = await db.execute(select(User).where(User.id == uid))
        return res.scalar_one_or_none()


async def _compute_stats(stream_name: str) -> dict:
    """Recompute stats for one room directly from the DB (+ in-memory peak).

    This is the payload the backend pushes over the WS channel; it matches
    the REST ``/api/streams/{name}/stats`` shape so the frontend can reuse
    the same ``StreamStats`` interface.
    """
    async with async_session() as db:
        cfg_res = await db.execute(
            select(StreamConfig).where(StreamConfig.stream_name == stream_name)
        )
        cfg = cfg_res.scalar_one_or_none()

        current_q = await db.execute(
            select(func.count(ViewerSession.id))
            .where(ViewerSession.stream_name == stream_name)
            .where(ViewerSession.ended_at.is_(None))
        )
        current_viewers = int(current_q.scalar() or 0)

        total_plays_q = await db.execute(
            select(func.count(ViewerSession.id)).where(
                ViewerSession.stream_name == stream_name
            )
        )
        total_plays = int(total_plays_q.scalar() or 0)

        # total watch seconds = sum of completed durations + live "now - started"
        closed_sum_q = await db.execute(
            select(func.coalesce(func.sum(ViewerSession.duration_seconds), 0))
            .where(ViewerSession.stream_name == stream_name)
            .where(ViewerSession.ended_at.is_not(None))
        )
        closed_watch = int(closed_sum_q.scalar() or 0)

        now = dt.datetime.now(dt.timezone.utc)
        open_q = await db.execute(
            select(ViewerSession.started_at)
            .where(ViewerSession.stream_name == stream_name)
            .where(ViewerSession.ended_at.is_(None))
        )
        live_watch = 0
        for (started,) in open_q.all():
            if started is None:
                continue
            if started.tzinfo is None:
                started = started.replace(tzinfo=dt.timezone.utc)
            live_watch += max(0, int((now - started).total_seconds()))
        total_watch_seconds = closed_watch + live_watch

        unique_q = await db.execute(
            select(func.count(func.distinct(ViewerSession.user_id)))
            .where(ViewerSession.stream_name == stream_name)
            .where(ViewerSession.user_id.is_not(None))
        )
        unique_logged_in_viewers = int(unique_q.scalar() or 0)

        pub_q = await db.execute(
            select(StreamPublishSession)
            .where(StreamPublishSession.stream_name == stream_name)
            .where(StreamPublishSession.ended_at.is_(None))
            .order_by(StreamPublishSession.started_at.desc())
        )
        active_pub = pub_q.scalars().first()

        current_live_duration_seconds = 0
        current_session_started_at: Optional[str] = None
        if active_pub is not None and active_pub.started_at is not None:
            started = active_pub.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=dt.timezone.utc)
            current_live_duration_seconds = max(
                0, int((now - started).total_seconds())
            )
            current_session_started_at = active_pub.started_at.isoformat()

        total_live_q = await db.execute(
            select(func.coalesce(func.sum(StreamPublishSession.duration_seconds), 0))
            .where(StreamPublishSession.stream_name == stream_name)
        )
        total_live_seconds = (
            int(total_live_q.scalar() or 0) + current_live_duration_seconds
        )

        # Peak concurrent viewers for the *current* live session: take the max
        # of (in-memory current-session peak, current viewers). In-memory value
        # is cleared when the stream goes offline (reconciler resets it).
        peak_session_viewers = max(
            manager.peak_viewers(stream_name), current_viewers
        )

        return {
            "stream_name": stream_name,
            "display_name": (cfg.display_name if cfg else stream_name) or stream_name,
            "is_live": active_pub is not None,
            "current_viewers": current_viewers,
            "total_plays": total_plays,
            "total_watch_seconds": total_watch_seconds,
            "unique_logged_in_viewers": unique_logged_in_viewers,
            "peak_session_viewers": peak_session_viewers,
            "current_live_duration_seconds": current_live_duration_seconds,
            "total_live_seconds": total_live_seconds,
            "last_publish_at": cfg.last_publish_at.isoformat()
            if cfg and cfg.last_publish_at
            else None,
            "last_unpublish_at": cfg.last_unpublish_at.isoformat()
            if cfg and cfg.last_unpublish_at
            else None,
            "current_session_started_at": current_session_started_at,
        }


async def _broadcast_stats(stream_name: str) -> None:
    """Compute and push the latest stats to every viewer of a room."""
    try:
        payload = {"type": "stats", **(await _compute_stats(stream_name))}
    except Exception as e:
        logger.exception("viewer: failed to compute stats for %s: %s", stream_name, e)
        return
    await manager.broadcast(stream_name, payload)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


# Sent every 15s from the frontend; backend closes sessions whose last_heartbeat
# has not been touched in ~40s (see stats_reconciler.sweep_viewer_sessions).
HEARTBEAT_INTERVAL_HINT_SECONDS = 15


@router.websocket("/ws/{stream_name}")
async def websocket_viewer(
    websocket: WebSocket,
    stream_name: str,
    token: Optional[str] = Query(None),
):
    """WebSocket: one connection per actively-watching player."""
    # Resolve room config + effective user.
    async with async_session() as db:
        cfg_res = await db.execute(
            select(StreamConfig).where(StreamConfig.stream_name == stream_name)
        )
        cfg = cfg_res.scalar_one_or_none()

    user = await _load_user(token)

    # Private-room access check.
    if cfg is not None and cfg.is_private:
        ok = False
        if user is not None and not user.is_banned:
            ok = True
        elif token and cfg.watch_token and token == cfg.watch_token:
            ok = True
        if not ok:
            # Accept-then-close so browsers see a clean 4401 code rather than
            # a generic HTTP 403 handshake failure.
            await websocket.accept()
            await websocket.close(code=4401)
            return

    await websocket.accept()

    session_key = uuid.uuid4().hex
    client_ip = ""
    try:
        # X-Forwarded-For first, else peer address.
        xff = websocket.headers.get("x-forwarded-for")
        if xff:
            client_ip = xff.split(",")[0].strip()
        elif websocket.client:
            client_ip = websocket.client.host or ""
    except Exception:
        client_ip = ""
    user_agent = (websocket.headers.get("user-agent") or "")[:512]

    # Insert the ViewerSession row.
    async with async_session() as db:
        row = ViewerSession(
            session_key=session_key,
            stream_name=stream_name,
            user_id=user.id if user else None,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        db.add(row)
        await db.commit()

    manager.add(stream_name, websocket, session_key)

    # Tell the client its session id and the expected ping interval.
    try:
        await websocket.send_json(
            {
                "type": "hello",
                "session_key": session_key,
                "heartbeat_interval_seconds": HEARTBEAT_INTERVAL_HINT_SECONDS,
            }
        )
    except Exception:
        pass

    # Initial stats snapshot + broadcast (so everyone sees the new viewer).
    await _broadcast_stats(stream_name)

    try:
        while True:
            msg = await websocket.receive_text()
            # Any inbound message is treated as a heartbeat. We still special-case
            # "ping" for clarity and reply with "pong" for client-side RTT metrics.
            is_ping = False
            try:
                import json

                data = json.loads(msg)
                if isinstance(data, dict) and data.get("type") == "ping":
                    is_ping = True
            except Exception:
                if msg.strip().lower() in ("ping", '"ping"'):
                    is_ping = True

            now = dt.datetime.now(dt.timezone.utc)
            async with async_session() as db:
                await db.execute(
                    ViewerSession.__table__.update()
                    .where(ViewerSession.session_key == session_key)
                    .values(last_heartbeat_at=now)
                )
                await db.commit()

            if is_ping:
                try:
                    await websocket.send_json({"type": "pong"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("viewer ws loop error stream=%s: %s", stream_name, e)
    finally:
        manager.remove(stream_name, websocket)
        # Close the DB session row.
        now = dt.datetime.now(dt.timezone.utc)
        try:
            async with async_session() as db:
                res = await db.execute(
                    select(ViewerSession).where(ViewerSession.session_key == session_key)
                )
                row = res.scalar_one_or_none()
                if row is not None and row.ended_at is None:
                    row.ended_at = now
                    started = row.started_at
                    if started is not None and started.tzinfo is None:
                        started = started.replace(tzinfo=dt.timezone.utc)
                    if started is not None:
                        row.duration_seconds = max(
                            0, int((now - started).total_seconds())
                        )
                    await db.commit()
        except Exception as e:
            logger.warning("viewer ws close-session failed key=%s: %s", session_key, e)

        # Fan-out the updated viewer count.
        try:
            await asyncio.shield(_broadcast_stats(stream_name))
        except Exception:
            pass
