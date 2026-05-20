from __future__ import annotations
import asyncio
from contextvars import ContextVar
from .sseEvents import SSEEvent

_bus: ContextVar[asyncio.Queue[SSEEvent | None] | None] = ContextVar("event_bus", default=None)


def init_bus() -> asyncio.Queue[SSEEvent | None]:
    q: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
    _bus.set(q)
    return q


async def emit(event: SSEEvent) -> None:
    bus = _bus.get()
    if bus is not None:
        await bus.put(event)


async def close_bus() -> None:
    bus = _bus.get()
    if bus is not None:
        await bus.put(None)  # sentinel — signals end of stream
