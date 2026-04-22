"""Edge-node routes — CRUD for admins + public source list for viewers.

Edge nodes are optional CDN / SRS-Edge hosts the backend advertises to the
player so an end viewer can switch between the origin and one of several
edges. The backend never proxies media through these — it only hands the
player a ``{scheme}://{host[:port]}`` prefix that replaces ``public_base_url``
in the play URL. The path + query (including auth tokens) are preserved as
originally minted by ``/api/streams/play``.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.config import settings
from app.database import get_db
from app.models import EdgeNode, User
from app.schemas import (
    EdgeNodeCreateRequest,
    EdgeNodePublicResponse,
    EdgeNodeResponse,
    EdgeNodeUpdateRequest,
    PlaybackSourcesResponse,
)

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")


router = APIRouter(tags=["edge"])


def _normalize_base_url(raw: str) -> str:
    """Strip trailing slashes and ensure a scheme is present."""
    value = (raw or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="base_url is required")
    if "://" not in value:
        value = "https://" + value
    return value.rstrip("/")


# ---------------------------------------------------------------------------
# Public endpoint: used by the player source dropdown.
# ---------------------------------------------------------------------------


@router.get("/api/playback-sources", response_model=PlaybackSourcesResponse)
async def list_playback_sources(
    db: AsyncSession = Depends(get_db),
    _user: Optional[User] = Depends(get_current_user),
) -> PlaybackSourcesResponse:
    """Return the origin + enabled edges the player should offer."""
    origin_url = settings.public_base_url.rstrip("/") if settings.public_base_url else ""
    origin = EdgeNodePublicResponse(
        slug="origin",
        name="Origin",
        base_url=origin_url,
        description="Default origin server (public_base_url).",
    )

    result = await db.execute(
        select(EdgeNode)
        .where(EdgeNode.enabled.is_(True))
        .order_by(EdgeNode.sort_order, EdgeNode.id)
    )
    edges = [
        EdgeNodePublicResponse.model_validate(e) for e in result.scalars().all()
    ]
    return PlaybackSourcesResponse(origin=origin, edges=edges)


# ---------------------------------------------------------------------------
# Admin CRUD.
# ---------------------------------------------------------------------------


admin_router = APIRouter(prefix="/api/admin/edge-nodes", tags=["edge-admin"])


@admin_router.get("", response_model=list[EdgeNodeResponse])
async def list_edge_nodes(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[EdgeNodeResponse]:
    result = await db.execute(
        select(EdgeNode).order_by(EdgeNode.sort_order, EdgeNode.id)
    )
    return [EdgeNodeResponse.model_validate(e) for e in result.scalars().all()]


@admin_router.post("", response_model=EdgeNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_edge_node(
    request: EdgeNodeCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> EdgeNodeResponse:
    slug = request.slug.strip()
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    if slug == "origin":
        raise HTTPException(status_code=400, detail="'origin' is a reserved slug")

    # Uniqueness check.
    existing = await db.execute(select(EdgeNode).where(EdgeNode.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already exists"
        )

    node = EdgeNode(
        slug=slug,
        name=request.name.strip() or slug,
        base_url=_normalize_base_url(request.base_url),
        description=request.description,
        enabled=request.enabled,
        sort_order=request.sort_order,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return EdgeNodeResponse.model_validate(node)


@admin_router.put("/{node_id}", response_model=EdgeNodeResponse)
async def update_edge_node(
    node_id: int,
    request: EdgeNodeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> EdgeNodeResponse:
    result = await db.execute(select(EdgeNode).where(EdgeNode.id == node_id))
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Edge node not found")

    if request.name is not None:
        node.name = request.name.strip() or node.slug
    if request.base_url is not None:
        node.base_url = _normalize_base_url(request.base_url)
    if request.description is not None:
        node.description = request.description
    if request.enabled is not None:
        node.enabled = request.enabled
    if request.sort_order is not None:
        node.sort_order = request.sort_order

    await db.flush()
    await db.refresh(node)
    return EdgeNodeResponse.model_validate(node)


@admin_router.delete("/{node_id}")
async def delete_edge_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, str]:
    result = await db.execute(select(EdgeNode).where(EdgeNode.id == node_id))
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Edge node not found")
    await db.delete(node)
    return {"message": "Edge node deleted"}
