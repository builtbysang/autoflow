"""No-op activity stub — activity logging removed."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Optional


class _Activity:
    def set_result(self, data: Any) -> None:
        pass


@asynccontextmanager
async def record_activity(action: str, *, params: Any = None, node_id: Optional[int] = None):
    yield _Activity()
