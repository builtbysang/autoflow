"""Describe an image using Claude CLI."""
from __future__ import annotations

import logging
from typing import Optional

from flowboard.services import media as media_service
from flowboard.services.claude_cli import ClaudeCliError, run_claude

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a visual asset annotator. Output one short factual sentence "
    "(max 200 characters) describing the image. Focus on attributes useful "
    "for image generation: colour, style, subject, composition. "
    "No marketing language, no opinions, no preamble."
)


class VisionError(RuntimeError):
    pass


async def describe_media(media_id: str) -> str:
    media_id = media_service.normalize_media_id(media_id)
    if not media_service.is_valid_media_id(media_id):
        raise VisionError("invalid media_id")

    cached = media_service.cached_path(media_id)
    if cached is None:
        result = await media_service.fetch_and_cache(media_id)
        if result is None:
            raise VisionError("media not cached and could not be fetched")
        _, _, cached = result

    try:
        text = await run_claude(
            "Describe this image.",
            system_prompt=_SYSTEM,
            attachments=[str(cached.resolve())],
            timeout=120.0,
        )
    except ClaudeCliError as exc:
        raise VisionError(f"claude CLI failed: {exc}") from exc

    text = (text or "").strip()
    if not text:
        raise VisionError("empty response from claude CLI")
    return text[:400]


async def describe_url(url: str) -> str:
    """Describe an image directly from a URL (downloads to temp, then describes)."""
    import tempfile
    import httpx
    from pathlib import Path

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise VisionError(f"failed to fetch image: HTTP {resp.status_code}")

    suffix = ".jpg"
    ct = resp.headers.get("content-type", "")
    if "png" in ct:
        suffix = ".png"
    elif "webp" in ct:
        suffix = ".webp"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(resp.content)
        tmp_path = f.name

    try:
        text = await run_claude(
            "Describe this image.",
            system_prompt=_SYSTEM,
            attachments=[tmp_path],
            timeout=120.0,
        )
    except ClaudeCliError as exc:
        raise VisionError(f"claude CLI failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return (text or "").strip()[:400]
