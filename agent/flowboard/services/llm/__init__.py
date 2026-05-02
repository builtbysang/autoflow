"""LLM layer — routes through the local claude CLI (uses your Claude subscription)."""
from __future__ import annotations

from typing import Optional

from flowboard.services.claude_cli import ClaudeCliError, run_claude


class LLMError(RuntimeError):
    pass


async def run_llm(
    role: str,
    user_prompt: str,
    *,
    system_prompt: Optional[str] = None,
    attachments: Optional[list[str]] = None,
    timeout: float = 90.0,
) -> str:
    try:
        return await run_claude(
            user_prompt,
            system_prompt=system_prompt,
            attachments=attachments,
            timeout=timeout,
        )
    except ClaudeCliError as exc:
        raise LLMError(str(exc)) from exc
