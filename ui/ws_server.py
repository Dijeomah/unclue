from __future__ import annotations

import asyncio
import json
import threading
from typing import Callable

import websockets

from .overlay import OverlaySignals

PORT = 8765


class WSServer:
    """Local-only WebSocket bridge so a browser extension's content script can
    mirror the overlay and trigger the same actions as the global hotkeys.

    The point: a content script renders as DOM content inside the browser's
    own page/window, so — unlike the native PyQt overlay, which is a separate
    OS window from another process — it can show up even while the browser
    itself is in native fullscreen (e.g. a fullscreen Google Meet tab)."""

    def __init__(
        self,
        signals: OverlaySignals,
        available_backends: list[str],
        on_trigger: Callable[[], None],
        on_toggle_pause: Callable[[], None] | None = None,
        port: int = PORT,
    ):
        self._signals = signals
        self._available = available_backends
        self._on_trigger = on_trigger
        self._on_toggle_pause = on_toggle_pause
        self._port = port
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None

        signals.update_transcript.connect(lambda t: self._broadcast({"type": "transcript", "text": t}))
        signals.update_response.connect(lambda t: self._broadcast({"type": "response", "text": t}))
        signals.set_status.connect(lambda t: self._broadcast({"type": "status", "text": t}))
        signals.switch_backend.connect(lambda name: self._broadcast({"type": "backend", "active": name}))

    def start(self) -> None:
        threading.Thread(target=self._run_loop, daemon=True).start()

    # ── Server loop (background thread) ─────────────────────────────────────

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        async with websockets.serve(self._handle_client, "localhost", self._port):
            print(f"[ws] Extension bridge listening on ws://localhost:{self._port}")
            await asyncio.Future()  # run forever

    async def _handle_client(self, ws) -> None:
        self._clients.add(ws)
        try:
            await ws.send(json.dumps({"type": "backends", "available": self._available}))
            async for raw in ws:
                await self._handle_message(raw)
        finally:
            self._clients.discard(ws)

    async def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        kind = msg.get("type")
        if kind == "trigger":
            self._on_trigger()
        elif kind == "toggle_pause" and self._on_toggle_pause:
            self._on_toggle_pause()
        elif kind == "switch_backend":
            self._signals.switch_backend.emit(msg.get("name", ""))

    # ── Broadcasting (called from the Qt main thread via signals) ───────────

    def _broadcast(self, payload: dict) -> None:
        if not self._loop or not self._clients:
            return
        data = json.dumps(payload)
        asyncio.run_coroutine_threadsafe(self._broadcast_async(data), self._loop)

    async def _broadcast_async(self, data: str) -> None:
        if self._clients:
            await asyncio.gather(*(c.send(data) for c in list(self._clients)), return_exceptions=True)
