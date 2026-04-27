from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class WsHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(websocket)

    async def broadcast(self, kind: str, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        async with self._lock:
            targets = list(self.clients)
        for client in targets:
            try:
                await client.send_json({"kind": kind, "payload": payload})
            except Exception:
                stale.append(client)
        if stale:
            async with self._lock:
                for client in stale:
                    self.clients.discard(client)
