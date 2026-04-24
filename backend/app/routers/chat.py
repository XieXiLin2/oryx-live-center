"""Chat/Danmaku routes with WebSocket support."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_access_token
from app.database import async_session, get_db
from app.models import ChatMessage, StreamConfig, User
from app.schemas import ChatHistoryResponse, ChatMessageResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ConnectionManager:
    """Manage WebSocket connections for chat rooms."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[tuple[WebSocket, Optional[User]]]] = {}

    async def connect(self, websocket: WebSocket, stream_name: str, user: Optional[User] = None) -> None:
        await websocket.accept()
        self.active_connections.setdefault(stream_name, []).append((websocket, user))
        logger.info("User %s connected to stream %s", user.username if user else "anonymous", stream_name)

    def disconnect(self, websocket: WebSocket, stream_name: str) -> None:
        if stream_name in self.active_connections:
            self.active_connections[stream_name] = [
                (ws, u) for ws, u in self.active_connections[stream_name] if ws != websocket
            ]
            if not self.active_connections[stream_name]:
                del self.active_connections[stream_name]

    async def broadcast(self, stream_name: str, message: dict) -> None:
        if stream_name not in self.active_connections:
            return
        dead: list[WebSocket] = []
        for websocket, _user in self.active_connections[stream_name]:
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for ws in dead:
            self.disconnect(ws, stream_name)

    def get_online_count(self, stream_name: str) -> int:
        return len(self.active_connections.get(stream_name, []))


manager = ConnectionManager()


async def _chat_enabled(stream_name: str) -> bool:
    """Look up whether chat is enabled for this stream."""
    async with async_session() as db:
        result = await db.execute(select(StreamConfig).where(StreamConfig.stream_name == stream_name))
        config = result.scalar_one_or_none()
        # Default: enabled when no config row yet.
        return True if config is None else bool(config.chat_enabled)


@router.websocket("/ws/{stream_name}")
async def websocket_chat(
    websocket: WebSocket,
    stream_name: str,
    token: Optional[str] = Query(None),
):
    """WebSocket endpoint for real-time chat/danmaku."""
    # Reject early when chat is disabled for this room.
    if not await _chat_enabled(stream_name):
        await websocket.accept()
        await websocket.send_json({"type": "error", "content": "Chat is disabled for this room"})
        await websocket.close(code=4403)
        return

    user: Optional[User] = None
    if token:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id:
                async with async_session() as db:
                    result = await db.execute(select(User).where(User.id == int(user_id)))
                    user = result.scalar_one_or_none()
        except Exception:
            user = None

    await manager.connect(websocket, stream_name, user)

    await websocket.send_json(
        {
            "type": "system",
            "content": f"Connected to stream: {stream_name}",
            "online_count": manager.get_online_count(stream_name),
        }
    )

    if user:
        await manager.broadcast(
            stream_name,
            {
                "type": "system",
                "content": f"{user.display_name or user.username} joined",
                "online_count": manager.get_online_count(stream_name),
            },
        )

    try:
        while True:
            data = await websocket.receive_text()

            if not user:
                await websocket.send_json({"type": "error", "content": "Authentication required to send messages"})
                continue

            if user.is_banned:
                await websocket.send_json({"type": "error", "content": "You are banned from chatting"})
                continue

            # Re-check chat_enabled each message so admins can toggle live.
            if not await _chat_enabled(stream_name):
                await websocket.send_json({"type": "error", "content": "Chat is disabled for this room"})
                continue

            try:
                msg_data = json.loads(data)
                content = str(msg_data.get("content", "")).strip()
            except json.JSONDecodeError:
                content = data.strip()

            if not content or len(content) > 500:
                continue

            async with async_session() as db:
                chat_msg = ChatMessage(
                    user_id=user.id,
                    username=user.username,
                    display_name=user.display_name,
                    content=content,
                    stream_name=stream_name,
                )
                db.add(chat_msg)
                await db.commit()
                await db.refresh(chat_msg)

                await manager.broadcast(
                    stream_name,
                    {
                        "type": "message",
                        "id": chat_msg.id,
                        "user_id": user.id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "avatar_url": user.avatar_url,
                        "email": user.email,
                        "content": content,
                        "created_at": chat_msg.created_at.isoformat() if chat_msg.created_at else None,
                        "is_admin": user.is_admin,
                    },
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, stream_name)
        if user:
            await manager.broadcast(
                stream_name,
                {
                    "type": "system",
                    "content": f"{user.display_name or user.username} left",
                    "online_count": manager.get_online_count(stream_name),
                },
            )


@router.get("/history/{stream_name}", response_model=ChatHistoryResponse)
async def get_chat_history(
    stream_name: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    count_result = await db.execute(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.stream_name == stream_name)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.stream_name == stream_name)
        .order_by(ChatMessage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    messages = result.scalars().all()

    return ChatHistoryResponse(
        messages=[ChatMessageResponse.model_validate(m) for m in reversed(messages)],
        total=total,
    )


@router.get("/online/{stream_name}")
async def get_online_count(stream_name: str) -> dict[str, int]:
    return {"online_count": manager.get_online_count(stream_name)}
