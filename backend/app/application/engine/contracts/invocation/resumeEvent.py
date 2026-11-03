from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel

from app.application.engine.contracts.invocation.callTarget import CallTarget, TargetSignature
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import CallKey, ExecutionIdentity


@dataclass(frozen=True)
class CallSuccess[O: BaseModel]:
    output: O


@dataclass(frozen=True)
class CallFailure[E: NodeError]:
    error: E


@dataclass(frozen=True)
class CallCancelled:
    pass


@dataclass(frozen=True)
class CallRuntimeFailure:
    diagnostic_ref: ExecutionIdentity


type CallResult[O: BaseModel, E: NodeError] = CallSuccess[O] | CallFailure[E] | CallCancelled | CallRuntimeFailure


@dataclass(frozen=True)
class ReturnedCall:
    key: CallKey
    target: TargetSignature
    result: CallResult[BaseModel, NodeError]


@dataclass(frozen=True)
class CallResults:
    _entries: tuple[ReturnedCall, ...]

    def get[I: BaseModel, O: BaseModel, E: NodeError](
        self, key: CallKey, target: CallTarget[I, O, E],
    ) -> CallResult[O, E]:
        for entry in self._entries:
            if entry.key == key:
                result = entry.result
                if entry.target != target:
                    raise TypeError("return target differs from dispatch")
                if isinstance(result, CallSuccess) and not isinstance(result.output, target.output_type):
                    raise TypeError("return output differs from target")
                if isinstance(result, CallFailure) and not isinstance(result.error, target.error_types):
                    raise TypeError("undeclared return error")
                return cast(CallResult[O, E], result)
        raise KeyError(key)


type ResumeEvent = CallResults
