"""Database models."""

import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """User model - stores OAuth2 user info."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    oauth_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    avatar_url: Mapped[str] = mapped_column(String(1024), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    """Chat/Danmaku message model."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(index=True)
    username: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    stream_name: Mapped[str] = mapped_column(String(255), index=True, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StreamConfig(Base):
    """Live room configuration.

    Each row represents a single live room / channel. Multiple rooms can exist
    and be played concurrently. The `stream_name` is the unique stream key
    (e.g. path segment after /live/).
    """

    __tablename__ = "stream_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stream_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")

    # Privacy: when True the stream requires either a logged-in user OR a valid
    # watch token to play. When False it is freely accessible.
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)

    # Per-room publish (push) secret. SRS `on_publish` callback verifies
    # the publisher's URL query param against this value.
    publish_secret: Mapped[str] = mapped_column(String(255), default="")

    # Permanent watch token for private streams. Admins may rotate it manually.
    # Anyone holding this token can watch the private stream without logging in.
    watch_token: Mapped[str] = mapped_column(String(255), default="")

    # Chat / danmaku switch for this room.
    chat_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Per-room WebRTC (WHEP) playback toggle.
    # When False this room refuses WebRTC play requests even if the global
    # ``settings.webrtc_play_enabled`` is True. WHIP publish is unaffected.
    webrtc_play_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # ---- Live state / statistics (updated via SRS hooks) ----
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    viewer_count: Mapped[int] = mapped_column(Integer, default=0)
    total_play_count: Mapped[int] = mapped_column(Integer, default=0)
    last_publish_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_unpublish_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StreamPlaySession(Base):
    """A single viewer play session, tracked via SRS on_play/on_stop hooks."""

    __tablename__ = "stream_play_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # SRS client ID (from on_play payload) — used to correlate on_stop.
    srs_client_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    stream_name: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)


class StreamPublishSession(Base):
    """A single publish session (publisher goes online → offline)."""

    __tablename__ = "stream_publish_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    srs_client_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    stream_name: Mapped[str] = mapped_column(String(255), index=True)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)


class ViewerSession(Base):
    """A single **frontend**-driven viewer session.

    Unlike :class:`StreamPlaySession` (which is populated from SRS hooks and
    left untouched so it can evolve with the media layer), this table is fully
    owned by the backend and written exclusively from the `/ws/viewer/...`
    WebSocket lifecycle:

    * Row is inserted when the WS connection is accepted.
    * `last_heartbeat_at` is advanced on every client ping.
    * Row is closed (`ended_at`, `duration_seconds`) when the WS disconnects
      **or** when a background sweeper finds the heartbeat to be stale.

    Because it doesn't depend on SRS `on_play` / `on_stop`, it works even when
    those hooks are missed, reordered or intentionally disabled for a deploy.
    """

    __tablename__ = "viewer_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Opaque per-connection UUID minted by the backend on WS accept.
    session_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    stream_name: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_heartbeat_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)


class EdgeNode(Base):
    """A CDN / SRS-Edge node the end user can pick as a playback source.

    The backend never proxies traffic through these; it only advertises them
    to the player so the client can rewrite the FLV / WHEP host when the
    viewer changes the "source" dropdown. The Origin itself (``public_base_url``)
    is always implicitly available as the "Origin" source and is not stored
    here.
    """

    __tablename__ = "edge_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Short machine-readable identifier (unique). Used as the ``source`` query
    # value in play URLs so sessions can be attributed to a node.
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Human-readable name shown in the source dropdown.
    name: Mapped[str] = mapped_column(String(128))
    # Scheme + host [+ port] that should replace ``public_base_url`` in play
    # URLs. Example: ``https://edge-hk.example.com``. Path must NOT be
    # included; the player keeps the original path + query intact.
    base_url: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(String(512), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Sort order (ascending). Ties broken by id.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

