"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from app.config import settings
from app.database import init_db
from app.routers import admin, auth, chat, hooks, streams

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info(f"Starting {settings.app_name}")
    await init_db()
    logger.info("Database initialized")
    logger.info("SRS HTTP:     %s", settings.srs_http_url)
    logger.info("SRS HTTP API: %s", settings.srs_api_url)
    yield
    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# CORS
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(streams.router)
app.include_router(admin.router)
app.include_router(hooks.router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


# ============================================================
# Static SPA
# ============================================================
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


async def _serve_spa_or_404(path: str) -> Response:
    from fastapi.responses import FileResponse

    if os.path.isdir(STATIC_DIR):
        file_path = os.path.join(STATIC_DIR, path.lstrip("/"))
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
    return Response(content="Not Found", status_code=404)


# ============================================================
# SRS Media Reverse Proxy (optional).
#
# In production we recommend putting Nginx in front of SRS so that /live/
# and /rtc/ are served directly by SRS via Nginx. When `public_base_url`
# is configured the frontend will point at Nginx and these in-app proxies
# are simply unused.
#
# The proxies below are kept for convenience (single-container dev mode),
# so that hitting the FastAPI port still yields working media URLs.
# Only FLV (not HLS) is proxied.
# ============================================================

# Matches "/<app>/<stream>.flv" only.
_STREAM_MEDIA_RE = re.compile(r"^/[^/]+/[^/]+\.flv$")


@app.api_route("/{app_name}/{stream_file:path}", methods=["GET"])
async def proxy_srs_flv(app_name: str, stream_file: str, request: Request):
    """Reverse proxy for SRS HTTP-FLV only."""
    full_path = f"/{app_name}/{stream_file}"

    if not _STREAM_MEDIA_RE.match(full_path):
        return await _serve_spa_or_404(full_path)

    srs_url = f"{settings.srs_http_url.rstrip('/')}{full_path}"
    qs = str(request.query_params)
    if qs:
        srs_url += f"?{qs}"

    client = httpx.AsyncClient(timeout=None)
    try:
        req = client.build_request("GET", srs_url)
        response = await client.send(req, stream=True)

        content_type = response.headers.get("content-type", "video/x-flv")

        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_generator(),
            status_code=response.status_code,
            media_type=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        await client.aclose()
        logger.error("FLV proxy error %s: %s", full_path, e)
        return Response(content=f"Proxy error: {e}", status_code=502)


# ============================================================
# WebRTC WHIP/WHEP signaling proxy to SRS
# Only the HTTP signaling is proxied; the actual media path uses UDP
# direct to SRS, so the client must still be able to reach SRS on its
# WebRTC UDP port (default 8000/udp).
# ============================================================


@app.api_route("/rtc/v1/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy_srs_rtc(path: str, request: Request):
    srs_url = f"{settings.srs_api_url.rstrip('/')}/rtc/v1/{path}"
    qs = str(request.query_params)
    if qs:
        srs_url += f"?{qs}"

    body = await request.body()
    headers: dict[str, str] = {}
    ct = request.headers.get("content-type")
    if ct:
        headers["Content-Type"] = ct

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.request(
            request.method,
            srs_url,
            content=body,
            headers=headers,
        )
        resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
        if "location" in response.headers:
            resp_headers["Location"] = response.headers["location"]

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type", "application/sdp"),
            headers=resp_headers,
        )


# ============================================================
# SPA fallback (must be last).
# ============================================================
if os.path.isdir(STATIC_DIR):
    from fastapi.responses import FileResponse  # noqa: F401

    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return await _serve_spa_or_404(full_path)
