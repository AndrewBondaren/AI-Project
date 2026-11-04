"""Public domain-implemented spatial read operation."""
from typing import Protocol

from app.dataModel.spatial.read.request import SpatialReadRequest
from app.dataModel.spatial.read.result import SpatialReadResult


class SpatialFieldReader[T](Protocol):
    async def read_window(self, request: SpatialReadRequest) -> SpatialReadResult[T]: ...
