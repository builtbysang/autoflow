"""WebSocket bridge for the Chrome extension.

Two modes:
- Local (default): standalone websockets server on :9222 for backward compat.
- Cloud (Railway): FastAPI WebSocket at /ws/ext on the main HTTP port.
"""
from __future__ import annotations

import asyncio
import json
import logging

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from flowboard.config import EXTENSION_WS_PORT, WS_HOST
from flowboard.services.flow_client import flow_client

logger = logging.getLogger(__name__)


class _WSAdapter:
    """Wraps FastAPI WebSocket to expose the .send() interface flow_client uses."""
    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def send(self, data: str) -> None:
        await self._ws.send_text(data)


async def _handle_messages(ws_send, receive_iter) -> None:
    """Shared message loop used by both WS backends."""
    try:
        await ws_send(json.dumps({"type": "callback_secret", "secret": flow_client.callback_secret}))
    except Exception:  # noqa: BLE001
        logger.exception("failed to send callback_secret")

    async for raw in receive_iter:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("invalid JSON from extension")
            continue
        try:
            await flow_client.handle_message(data)
        except Exception:  # noqa: BLE001
            logger.exception("error handling extension message")


# ── FastAPI WebSocket handler (cloud path) ────────────────────────────────────

async def fastapi_ext_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    adapter = _WSAdapter(websocket)
    flow_client.set_extension(adapter)
    logger.info("extension connected (FastAPI WS)")

    async def _iter():
        try:
            while True:
                yield await websocket.receive_text()
        except WebSocketDisconnect:
            return

    try:
        await _handle_messages(adapter.send, _iter())
    finally:
        flow_client.clear_extension()
        logger.info("extension disconnected (FastAPI WS)")


# ── Standalone websockets server (local path) ─────────────────────────────────

async def _legacy_handler(websocket) -> None:
    flow_client.set_extension(websocket)
    logger.info("extension connected from %s", getattr(websocket, "remote_address", "?"))

    async def _iter():
        try:
            async for raw in websocket:
                yield raw
        except websockets.ConnectionClosed:
            return

    try:
        await _handle_messages(websocket.send, _iter())
    finally:
        flow_client.clear_extension()
        logger.info("extension disconnected")


async def run_ws_server() -> None:
    async with websockets.serve(_legacy_handler, WS_HOST, EXTENSION_WS_PORT):
        logger.info("WebSocket server listening on ws://%s:%d", WS_HOST, EXTENSION_WS_PORT)
        await asyncio.Future()  # run forever
