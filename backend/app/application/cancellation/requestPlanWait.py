"""Request-side cancellation/deadline adapter for the neutral planning protocol."""

from dataclasses import dataclass
import time
from typing import Self

from app.application.cancellation.cancellationToken import CancellationToken
from app.application.planning.service.planningService import PlanWaitCancelled


@dataclass(frozen=True)
class RequestPlanWait:
    token: CancellationToken | None
    deadline_monotonic: float | None

    @classmethod
    def unbounded(cls) -> Self:
        return cls(token=None, deadline_monotonic=None)

    def raise_if_cancelled(self) -> None:
        if self.token is not None and self.token.is_cancelled():
            raise PlanWaitCancelled("request cancelled")

    def remaining_seconds(self) -> float | None:
        if self.deadline_monotonic is None:
            return None
        return max(0.0, self.deadline_monotonic - time.monotonic())
