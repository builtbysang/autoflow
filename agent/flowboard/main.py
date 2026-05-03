from __future__ import annotations

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request as FastAPIRequest, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from flowboard.db import get_session, init_db
from flowboard.db.models import Request
from flowboard.routes import boards, edges, media, nodes, projects, prompt, upload, vision
from flowboard.routes import requests as requests_route
from flowboard.services.flow_client import flow_client
from flowboard.services.ws_server import fastapi_ext_ws, run_ws_server

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# True when running on Railway (or any cloud env that sets DATABASE_URL).
_CLOUD = bool(os.getenv("DATABASE_URL") or os.getenv("RAILWAY_ENVIRONMENT"))


def _recover_orphan_running_requests() -> int:
    from datetime import datetime, timezone
    from sqlmodel import select as _select

    touched = 0
    with get_session() as s:
        rows = s.exec(_select(Request).where(Request.status == "running")).all()
        for r in rows:
            r.status = "failed"
            r.error = "agent_restart_lost"
            r.finished_at = datetime.now(timezone.utc)
            s.add(r)
            touched += 1
        if touched:
            s.commit()
    return touched


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    recovered = _recover_orphan_running_requests()
    if recovered:
        logger.info("recovered %d orphan running request(s) → failed", recovered)

    from flowboard.worker.processor import get_worker
    worker = get_worker()
    tasks = [asyncio.create_task(worker.start(), name="request-worker")]

    if _CLOUD:
        logger.info("cloud mode — extension WS served at /ws/ext")
    else:
        tasks.append(asyncio.create_task(run_ws_server(), name="ext-ws-server"))
        logger.info("local mode — extension WS on :9222 + worker")

    try:
        yield
    finally:
        worker.request_shutdown()
        try:
            await asyncio.wait_for(worker.drain(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("worker drain timed out")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("flowboard agent stopped")


app = FastAPI(title="Flowboard Agent", version="0.0.2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(boards.router)
app.include_router(nodes.router)
app.include_router(edges.router)
app.include_router(projects.router)
app.include_router(requests_route.router)
app.include_router(media.bytes_router)
app.include_router(media.api_router)
app.include_router(upload.router)
app.include_router(vision.router)
app.include_router(prompt.router)


@app.websocket("/ws/ext")
async def ext_ws(websocket: WebSocket):
    """Extension WebSocket endpoint — used in cloud mode (Railway)."""
    await fastapi_ext_ws(websocket)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "extension_connected": flow_client.connected,
        "ws_stats": flow_client.ws_stats,
    }


@app.post("/api/ext/callback")
async def ext_callback(
    body: FastAPIRequest,
    x_callback_secret: Optional[str] = Header(default=None, alias="X-Callback-Secret"),
) -> dict:
    if not x_callback_secret or not hmac.compare_digest(
        x_callback_secret, flow_client.callback_secret
    ):
        raise HTTPException(status_code=401, detail="invalid callback secret")

    try:
        payload = await body.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json body")

    if not isinstance(payload, dict) or "id" not in payload:
        raise HTTPException(status_code=400, detail="missing id")

    matched = flow_client.resolve_callback(payload)
    return {"ok": matched}
