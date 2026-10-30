"""Exception transport only; retain its immutable POJO, never the traceback."""

from typing import Generic, TypeVar

from app.dataModel.engine.dag.errors.nodeError import NodeError

E = TypeVar("E", bound=NodeError)


class PythonNodeError(Exception, Generic[E]):
    def __init__(self, error: E) -> None:
        super().__init__(type(error).__name__)
        self.error = error
