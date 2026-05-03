"""Run Claude CLI as a subprocess (uses Claude subscription, no API cost)."""
from __future__ import annotations

import asyncio
import shutil
from typing import Optional


class ClaudeCliError(RuntimeError):
    pass


async def run_claude(
    prompt: str,
    *,
    system_prompt: Optional[str] = None,
    attachments: Optional[list[str]] = None,
    timeout: float = 90.0,
) -> str:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise ClaudeCliError("claude CLI not found in PATH")

    cmd = [claude_bin, "--print"]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    for path in attachments or []:
        cmd += ["--attachment", path]
    cmd.append(prompt)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        raise ClaudeCliError(f"claude CLI timed out after {timeout}s")
    except Exception as exc:
        raise ClaudeCliError(f"claude CLI error: {exc}") from exc

    if proc.returncode != 0:
        raise ClaudeCliError(stderr.decode(errors="replace").strip() or "claude CLI failed")

    return stdout.decode(errors="replace").strip()
