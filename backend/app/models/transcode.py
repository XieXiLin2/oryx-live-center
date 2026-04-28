"""Transcode models for external transcoding service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TranscodeNode(Base):
    """Transcode node (worker server) that executes transcoding tasks."""

    __tablename__ = "transcode_nodes"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    region = Column(String(50), nullable=False)  # beijing/shanghai/guangzhou
    ip_address = Column(String(50))
    status = Column(String(50))  # online/offline/busy
    max_tasks = Column(Integer, default=4)
    current_tasks = Column(Integer, default=0)
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    gpu_usage = Column(Float)
    network_latency = Column(Integer)  # latency to SRS Origin in ms
    last_heartbeat = Column(DateTime)
    capabilities = Column(JSON)  # {protocols: [rtmp, webrtc, srt], codecs: [h264, h265], gpu: bool}

    tasks = relationship("TranscodeTask", back_populates="node")


class TranscodeProfile(Base):
    """Transcode configuration profile/template."""

    __tablename__ = "transcode_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    source_protocol = Column(String(50))  # rtmp/srt/whip
    outputs = Column(JSON)  # [{protocol, resolution, bitrate, fps, codec, audio_codec, audio_bitrate}]
    latency_mode = Column(String(50))  # ultra_low/low/normal
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("TranscodeTask", back_populates="profile")


class TranscodeTask(Base):
    """Transcode task instance."""

    __tablename__ = "transcode_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_name = Column(String(255), nullable=False)
    profile_id = Column(Integer, ForeignKey("transcode_profiles.id"), nullable=False)
    node_id = Column(String(255), ForeignKey("transcode_nodes.id"))
    source_protocol = Column(String(50))  # rtmp/srt/whip
    source_url = Column(String(512))
    outputs = Column(JSON)  # [{protocol, bitrate, resolution, url}]
    status = Column(String(50))  # pending/running/stopped/failed
    started_at = Column(DateTime)
    stopped_at = Column(DateTime)
    error_message = Column(Text)
    metrics = Column(JSON)  # {latency, fps, bitrate, packet_loss}

    profile = relationship("TranscodeProfile", back_populates="tasks")
    node = relationship("TranscodeNode", back_populates="tasks")
