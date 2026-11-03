from dataclasses import dataclass

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.invocation.inputWait import WaitInput
from app.application.engine.contracts.invocation.callTarget import CallTarget, TargetSignature
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import CallKey, CallKeyValue


@dataclass(frozen=True)
class Complete[O: BaseModel]:
    output: O


@dataclass(frozen=True)
class Dispatch:
    key: CallKey
    target: TargetSignature
    input: BaseModel

    def __post_init__(self) -> None:
        TypeAdapter(CallKeyValue).validate_python(self.key)
        if not isinstance(self.input, self.target.input_type):
            raise TypeError("call input does not match target")


@dataclass(frozen=True)
class CallRequest[I: BaseModel, O: BaseModel, E: NodeError](Dispatch):
    key: CallKey
    target: CallTarget[I, O, E]
    input: I


@dataclass(frozen=True)
class SuspendedCall[S: BaseModel](Dispatch):
    state: S


@dataclass(frozen=True)
class Call[I: BaseModel, O: BaseModel, E: NodeError, S: BaseModel](SuspendedCall[S]):
    target: CallTarget[I, O, E]
    input: I


@dataclass(frozen=True)
class CallGroup[S: BaseModel]:
    requests: tuple[Dispatch, ...]
    state: S

    def __post_init__(self) -> None:
        if type(self.requests) is not tuple:
            raise TypeError("requests must be an immutable tuple")
        if not self.requests or len({r.key for r in self.requests}) != len(self.requests):
            raise ValueError("call group requires nonempty requests with distinct keys")


type NodeStep[O: BaseModel, S: BaseModel] = Complete[O] | SuspendedCall[S] | CallGroup[S] | WaitInput[S, BaseModel, BaseModel]
