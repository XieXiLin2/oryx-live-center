"""Thin async client for SRS 6 HTTP API.

SRS exposes a JSON HTTP API at its API port (default 1985), documented at:
    https://ossrs.io/lts/en-us/docs/v6/doc/http-api

Endpoints used here:
    GET /api/v1/streams/     — list all streams currently active
    GET /api/v1/clients/     — list all connected clients
    DELETE /api/v1/clients/{id}  — disconnect a client
    GET /api/v1/summaries     — system summary
    GET /api/v1/versions      — SRS version info
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SRSAPIError(RuntimeError):
    """Raised when an SRS API call fails."""


async def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Perform a JSON HTTP request against the SRS API."""
    url = f"{settings.srs_api_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            # Some SRS API endpoints return empty body on DELETE.
            if not resp.content:
                return {}
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("SRS API %s %s failed: HTTP %s - %s", method, path, e.response.status_code, e.response.text)
        raise SRSAPIError(f"SRS HTTP {e.response.status_code}: {e.response.text}") from e
    except Exception as e:
        logger.error("SRS API %s %s error: %s", method, path, e)
        raise SRSAPIError(str(e)) from e


async def list_streams() -> list[dict[str, Any]]:
    """Return a list of currently active streams reported by SRS."""
    try:
        data = await _request("GET", "/api/v1/streams/")
    except SRSAPIError:
        return []
    return data.get("streams", [])


async def list_clients() -> list[dict[str, Any]]:
    try:
        data = await _request("GET", "/api/v1/clients/")
    except SRSAPIError:
        return []
    return data.get("clients", [])


async def kick_client(client_id: str) -> dict[str, Any]:
    return await _request("DELETE", f"/api/v1/clients/{client_id}")


async def get_summary() -> dict[str, Any]:
    try:
        return await _request("GET", "/api/v1/summaries")
    except SRSAPIError:
        return {}


async def get_versions() -> dict[str, Any]:
    try:
        return await _request("GET", "/api/v1/versions")
    except SRSAPIError:
        return {}


def stream_formats(stream_info: dict[str, Any]) -> list[str]:
    """Given an SRS stream entry, derive the list of frontend-playable formats.

    HLS is intentionally not exposed — this project only offers FLV + WebRTC.
    """
    formats: list[str] = ["flv"]
    if stream_info.get("video"):
        formats.append("webrtc")
    return formats
