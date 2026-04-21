"""Background reconciler that keeps DB-owned play/publish statistics accurate.

Why this exists
===============
SRS's HTTP hooks (`on_play` / `on_stop` / `on_publish` / `on_unpublish`) are
our **primary source of truth** for "who is watching" and "how long did they
watch". That already lives in the `stream_play_sessions` and
`stream_publish_sessions` tables, so the backend doesn't need SRS's own
`clients` counter for business metrics.

But hooks can be **missed** in several failure modes:

* The publisher crashes / network dies → SRS may or may not fire `on_unpublish`
* The viewer closes their tab and the stream dies before `on_stop` reaches us
* Our app container restarts mid-session
* SRS was restarted (all its sessions are gone but we still have open rows)

So we periodically reconcile our DB against SRS's ground truth for **liveness**:

* "Does SRS actually have an active publisher for stream X right now?"
  If **no** and we still think the stream is live → close the publish
  session, mark the room offline, and close any lingering play sessions.

* "Do we have play sessions whose SRS client_id is no longer in SRS's client
  list?"  → close them (on_stop was lost).

The result is that:

* `StreamConfig.is_live`        ← derived from SRS stream list (authoritative)
* `StreamConfig.viewer_count`   ← recomputed from open `stream_play_sessions`
* session `duration_seconds`    ← filled in whether ended via hook or reconciler
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import srs_client
from app.database import async_session
from app.models import (
    StreamConfig,
    StreamPlaySession,
    StreamPublishSession,
    ViewerSession,
)

logger = logging.getLogger(__name__)

# How often to reconcile SRS-driven publish/play sessions. Short enough that
# "ghost counts" only linger briefly after hook loss; long enough not to
# hammer the SRS API.
RECONCILE_INTERVAL_SECONDS = 30

# How often to sweep viewer-websocket sessions for stale heartbeats.
# Frontends ping every ~15s; anything older than HEARTBEAT_TIMEOUT is
# considered dead and closed by the sweeper.
VIEWER_SWEEP_INTERVAL_SECONDS = 10
VIEWER_HEARTBEAT_TIMEOUT_SECONDS = 40



async def _reconcile_once(db: AsyncSession) -> None:
    now = dt.datetime.now(dt.timezone.utc)

    # -------- SRS ground truth --------
    try:
        srs_streams = await srs_client.list_streams()
        srs_clients = await srs_client.list_clients()
    except Exception as e:
        logger.warning("Stats reconciler: SRS API unreachable: %s", e)
        return

    # Map of stream_name → publisher info (if publishing).
    publishing_streams: set[str] = {
        s.get("name", "") for s in srs_streams
        if s.get("name") and s.get("publish", {}).get("active")
    }
    # If publish field missing, fall back to "stream is listed" = live.
    if not publishing_streams:
        publishing_streams = {s.get("name", "") for s in srs_streams if s.get("name")}

    # Set of all active SRS client IDs (both publishers & players).
    live_client_ids: set[str] = {str(c.get("id", "")) for c in srs_clients if c.get("id")}

    # -------- 1. Close orphan publish sessions --------
    result = await db.execute(
        select(StreamPublishSession).where(StreamPublishSession.ended_at.is_(None))
    )
    for sess in result.scalars().all():
        still_alive = (
            sess.stream_name in publishing_streams
            and (not sess.srs_client_id or sess.srs_client_id in live_client_ids)
        )
        if still_alive:
            continue
        sess.ended_at = now
        if sess.started_at:
            sess.duration_seconds = max(0, int((now - sess.started_at).total_seconds()))
        logger.info(
            "Reconciler: closed orphan publish session stream=%s client=%s dur=%ss",
            sess.stream_name, sess.srs_client_id, sess.duration_seconds,
        )

    # -------- 2. Close orphan play sessions --------
    result = await db.execute(
        select(StreamPlaySession).where(StreamPlaySession.ended_at.is_(None))
    )
    open_plays = list(result.scalars().all())
    for sess in open_plays:
        # A viewer session is orphan if its stream isn't publishing anymore
        # OR its SRS client_id has disappeared from the SRS client list.
        stream_alive = sess.stream_name in publishing_streams
        client_alive = (
            not sess.srs_client_id  # no tracking id → trust it
            or sess.srs_client_id in live_client_ids
        )
        if stream_alive and client_alive:
            continue
        sess.ended_at = now
        if sess.started_at:
            sess.duration_seconds = max(0, int((now - sess.started_at).total_seconds()))
        logger.info(
            "Reconciler: closed orphan play session stream=%s client=%s dur=%ss",
            sess.stream_name, sess.srs_client_id, sess.duration_seconds,
        )

    await db.flush()

    # -------- 3. Re-derive per-room fields --------
    result = await db.execute(select(StreamConfig))
    configs = list(result.scalars().all())

    # Fresh count of still-open play sessions per stream.
    count_result = await db.execute(
        select(StreamPlaySession.stream_name, func.count(StreamPlaySession.id))
        .where(StreamPlaySession.ended_at.is_(None))
        .group_by(StreamPlaySession.stream_name)
    )
    live_viewer_map: dict[str, int] = {name: cnt for name, cnt in count_result.all()}

    for cfg in configs:
        # Authoritative is_live comes from SRS — our DB just mirrors it.
        new_live = cfg.stream_name in publishing_streams
        if cfg.is_live and not new_live:
            cfg.last_unpublish_at = now
        cfg.is_live = new_live

        # Viewer count: from our own session table; zero if stream went offline.
        cfg.viewer_count = live_viewer_map.get(cfg.stream_name, 0) if new_live else 0

    await db.flush()

    # -------- 4. Reset in-memory peak for rooms that went offline --------
    # Importing here avoids a circular import at module load time.
    try:
        from app.routers.viewer import manager as _viewer_manager

        for cfg in configs:
            if not cfg.is_live:
                _viewer_manager.reset_peak(cfg.stream_name)
    except Exception:  # pragma: no cover — defensive
        pass


# ---------------------------------------------------------------------------
# Viewer-WebSocket heartbeat sweeper
# ---------------------------------------------------------------------------


async def _sweep_viewer_sessions_once(db: AsyncSession) -> set[str]:
    """Close ViewerSession rows whose heartbeat has gone stale.

    Returns the set of stream names that had at least one session closed, so
    the caller can broadcast fresh stats on those rooms.
    """
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(seconds=VIEWER_HEARTBEAT_TIMEOUT_SECONDS)

    result = await db.execute(
        select(ViewerSession)
        .where(ViewerSession.ended_at.is_(None))
        .where(ViewerSession.last_heartbeat_at < cutoff)
    )

    touched: set[str] = set()
    for row in result.scalars().all():
        row.ended_at = now
        started = row.started_at
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=dt.timezone.utc)
        if started is not None:
            row.duration_seconds = max(0, int((now - started).total_seconds()))
        touched.add(row.stream_name)
        logger.info(
            "Reconciler: swept stale viewer session key=%s stream=%s dur=%ss",
            row.session_key, row.stream_name, row.duration_seconds,
        )
    await db.flush()
    return touched


async def _viewer_sweep_loop() -> None:
    """Background task: periodically close zombie ViewerSession rows."""
    await asyncio.sleep(5)  # stagger from main reconciler startup
    while True:
        touched: set[str] = set()
        try:
            async with async_session() as db:
                try:
                    touched = await _sweep_viewer_sessions_once(db)
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    logger.exception("Viewer sweeper error: %s", e)
        except Exception as e:  # pragma: no cover — defensive
            logger.exception("Viewer sweeper outer error: %s", e)

        # Fan-out fresh stats for each affected room.
        if touched:
            try:
                from app.routers.viewer import _broadcast_stats

                for name in touched:
                    try:
                        await _broadcast_stats(name)
                    except Exception:
                        pass
            except Exception:
                pass

        await asyncio.sleep(VIEWER_SWEEP_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Main loop — runs both reconcilers concurrently
# ---------------------------------------------------------------------------


async def _publish_play_loop() -> None:
    await asyncio.sleep(5)
    while True:
        try:
            async with async_session() as db:
                try:
                    await _reconcile_once(db)
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    logger.exception("Reconciler error: %s", e)
        except Exception as e:  # pragma: no cover — defensive
            logger.exception("Reconciler outer error: %s", e)
        await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)


async def reconciler_loop() -> None:
    """Run both reconcilers forever. Intended to be started as a lifespan task."""
    await asyncio.gather(
        _publish_play_loop(),
        _viewer_sweep_loop(),
    )
