"""Pydantic schemas for request/response models."""

import datetime
from typing import Optional

from pydantic import BaseModel


# ---- Auth ----
class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class AuthURLResponse(BaseModel):
    authorize_url: str


# ---- User ----
class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    avatar_url: str
    is_admin: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class UserBanRequest(BaseModel):
    is_banned: bool


# ---- Chat ----
class ChatMessageRequest(BaseModel):
    content: str
    stream_name: str = ""


class ChatMessageResponse(BaseModel):
    id: int
    user_id: int
    username: str
    display_name: str
    content: str
    stream_name: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]
    total: int


# ---- Stream ----
class StreamInfo(BaseModel):
    name: str
    display_name: str
    app: str
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    clients: int = 0
    is_encrypted: bool = False
    require_auth: bool = False
    formats: list[str] = []


class StreamListResponse(BaseModel):
    streams: list[StreamInfo]


class StreamPlayRequest(BaseModel):
    stream_name: str
    format: str = "flv"
    key: Optional[str] = None


class StreamPlayResponse(BaseModel):
    url: str
    stream_name: str
    format: str


class StreamConfigRequest(BaseModel):
    display_name: Optional[str] = None
    is_encrypted: Optional[bool] = None
    encryption_key: Optional[str] = None
    require_auth: Optional[bool] = None


class StreamConfigResponse(BaseModel):
    id: int
    stream_name: str
    display_name: str
    is_encrypted: bool
    require_auth: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


# ---- Oryx Admin ----
class OryxSystemInfo(BaseModel):
    version: str = ""
    pid: int = 0
    ppid: int = 0
    argv: str = ""
    cwd: str = ""
    mem_kbyte: int = 0
    mem_percent: float = 0.0
    cpu_percent: float = 0.0
    sample_time: int = 0
    recv_bytes: int = 0
    send_bytes: int = 0
    conn_sys: int = 0
    conn_sys_et: int = 0
    conn_sys_tw: int = 0
    conn_sys_udp: int = 0
    conn_srs: int = 0


class OryxClientInfo(BaseModel):
    id: str = ""
    vhost: str = ""
    stream: str = ""
    ip: str = ""
    page_url: str = ""
    swf_url: str = ""
    tc_url: str = ""
    url: str = ""
    type: str = ""
    publish: bool = False
    alive: float = 0.0
    kbps_realtime: float = 0.0
    kbps_30s: float = 0.0
    kbps_5m: float = 0.0


class OryxVhostConfig(BaseModel):
    """Generic vhost configuration."""

    config: dict = {}


class OryxDVRConfig(BaseModel):
    enabled: bool = False
    path: str = ""
    plan: str = ""


class OryxHLSConfig(BaseModel):
    enabled: bool = False
    hls_fragment: float = 10.0
    hls_window: float = 60.0
    hls_path: str = ""


class OryxTranscodeConfig(BaseModel):
    enabled: bool = False
    engine: str = ""
    vcodec: str = ""
    acodec: str = ""
    vbitrate: int = 0
    abitrate: int = 0
    vfps: int = 0
    width: int = 0
    height: int = 0


class OryxForwardConfig(BaseModel):
    enabled: bool = False
    target: str = ""
    stream: str = ""


class OryxCallbackConfig(BaseModel):
    enabled: bool = False
    on_connect: str = ""
    on_close: str = ""
    on_publish: str = ""
    on_unpublish: str = ""
    on_play: str = ""
    on_stop: str = ""


# ---- CDN ----
class CDNConfig(BaseModel):
    cdn_base_url: str = ""
    cdn_pull_secret: str = ""


class CDNStreamURL(BaseModel):
    original_url: str
    cdn_url: str
    stream_name: str
    format: str
