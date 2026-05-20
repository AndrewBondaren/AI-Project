import asyncio
from dataclasses import dataclass, field


@dataclass
class CancellationToken:
    request_id: str
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()
