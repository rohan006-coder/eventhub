"""WebSocket connection manager. Services call `publish` from worker threads; it is a no-op without a running loop."""
import asyncio
import logging
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket

log = logging.getLogger("eventhub.ws")


class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.connections[user_id].add(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        self.connections[user_id].discard(ws)
        if not self.connections[user_id]:
            self.connections.pop(user_id, None)

    async def _send(self, user_ids, payload):
        for uid in set(user_ids):
            for ws in list(self.connections.get(uid, ())):
                try:
                    await ws.send_json(payload)
                except Exception:
                    self.disconnect(uid, ws)

    def publish(self, user_ids, payload: dict):
        """Thread-safe fire-and-forget push."""
        if self.loop is None or not self.loop.is_running() or not user_ids:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._send(list(user_ids), payload), self.loop)
        except Exception:  # pragma: no cover
            log.exception("ws publish failed")


manager = ConnectionManager()
