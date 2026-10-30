"""Read port; published catalog implementation belongs to A2.1."""

from typing import Protocol

from pydantic import BaseModel

from app.application.engine.contracts.outputRef import OptionalOutput, RequiredOutput
from app.dataModel.engine.dag.identity import DomainRevision


class DAGReadView(Protocol):
    def require[O: BaseModel](self, req: RequiredOutput[O]) -> O: ...

    def optional[O: BaseModel](self, req: OptionalOutput[O]) -> O | None: ...

    def record_domain_read(self, domain: str, revision: DomainRevision | None) -> None: ...
