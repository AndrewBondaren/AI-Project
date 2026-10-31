"""Delegate typed response policy; no task/node mapping or domain fallback."""

from typing import Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.executionBindings import ResolveResult, ResponseBinding
from app.application.engine.runtime.validation.contractValidator import ContractValidator

O = TypeVar("O", bound=BaseModel)


def _require_result(value: object) -> None:
    if not isinstance(value, ResolveResult):
        raise TypeError("response binding must return ResolveResult")


class ResponseResolver(Generic[O]):
    def __init__(self, response_type: type[O]) -> None:
        TypeAdapter(type[BaseModel]).validate_python(response_type)
        self._type = response_type

    def resolve(self, binding: ResponseBinding[O], view: DAGReadView) -> ResolveResult[O]:
        result = binding.resolve(view)
        _require_result(result)
        TypeAdapter(bool).validate_python(result.ok, strict=True)
        TypeAdapter(str | None).validate_python(result.error, strict=True)
        if result.data is not None:
            admitted, validation = ContractValidator().validate(result.data, self._type)
            if admitted is None or not validation.ok:
                raise TypeError("response does not satisfy its declared POJO contract")
        return result
