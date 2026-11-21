"""Negative static fixture: each marked assignment must be rejected."""
from typing import Never
from app.application.engine.contracts.nodeContract import NodeContract
from app.dataModel.engine.dag.errors.nodeError import NodeError
from tests.lifecycle.support import nodeContracts as c, mixedContracts as m


def wrong_kind(request: m.CreateRequestB, prepared: m.CreateB) -> None:
    c.CreateNodeInputA(request=request)  # EXPECT: B request cannot enter A
    c.CreateNodeOutputA(value=prepared)  # EXPECT: B prepared cannot leave A


def wrong_contract() -> NodeContract[c.CreateNodeInputB, c.CreateNodeOutputB, Never]:
    return c.CREATEA_CONTRACT  # EXPECT: invariant concrete I/O binding


def invented_error(error: NodeError) -> Never:
    return error  # EXPECT: no declared Lifecycle NodeError
