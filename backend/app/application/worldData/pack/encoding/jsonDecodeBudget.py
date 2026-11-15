"""JSON preflight without a value tree, using per-operation structural counters."""

import re
from dataclasses import dataclass

from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.application.worldData.pack.encoding.jsonDecodeErrors import JsonDecodeInputError, JsonDecodeConfigurationError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from pydantic_core.core_schema import ErrorType


class JsonDecodeLimitError(ValueError):
    """A configured JSON resource limit was exceeded."""


def _input_error(message: str, kind: ErrorType = "json_invalid") -> JsonDecodeInputError:
    return JsonDecodeInputError(WireShapeIssue(code=JsonValidationCode.SCHEMA_VIOLATION,
        location=WireLocation(), pydantic_type=kind, message=message))


_NUMBER = re.compile(rb"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


@dataclass
class _Container:
    kind: int
    state: str
    items: int = 0


class JsonDecodeBudget:
    def __init__(self, limits: DecodeLimits) -> None:
        errors = ValidatorAggregationHelper[WireShapeIssue]((WireShapeIssue,))
        for name in ("max_bytes", "max_nodes", "max_depth", "max_items"):
            limit = getattr(limits, name)
            if type(limit) is not int or limit < 0:
                errors.add(WireShapeIssue(code=JsonValidationCode.SCHEMA_VIOLATION,
                    location=WireLocation(parts=(name,)),
                    pydantic_type="int_type" if type(limit) is not int else "greater_than_equal",
                    message="JSON limit must be a nonnegative integer"))
        errors.raise_if_any(JsonDecodeConfigurationError)
        self._limits = limits
        self._bytes = 0
        self._nodes = 0

    def check(self, payload: bytes) -> None:
        if type(payload) is not bytes:
            raise _input_error("JSON preflight requires bytes", "bytes_type")
        if self._bytes + len(payload) > self._limits.max_bytes:
            raise JsonDecodeLimitError("JSON byte limit exceeded")
        self._bytes += len(payload)
        stack: list[_Container] = []
        index = 0
        root_seen = False
        while True:
            while index < len(payload) and payload[index] in b" \t\r\n":
                index += 1
            if index == len(payload):
                if stack or not root_seen:
                    raise _input_error("incomplete JSON value")
                return
            token = payload[index]
            parent = stack[-1] if stack else None
            if parent is None and root_seen:
                raise _input_error("trailing JSON data")
            if parent is not None:
                closing = ord("}") if parent.kind == ord("{") else ord("]")
                if parent.state in ("first", "end") and token == closing:
                    stack.pop()
                    index += 1
                    continue
                if parent.state == "end":
                    if token != ord(","):
                        raise _input_error("expected JSON comma")
                    parent.state = "next"
                    index += 1
                    continue
                if parent.state == "colon":
                    if token != ord(":"):
                        raise _input_error("expected JSON colon")
                    parent.state = "value"
                    index += 1
                    continue
                if parent.state in ("first", "next"):
                    if parent.items >= self._limits.max_items:
                        raise JsonDecodeLimitError("JSON container item limit exceeded")
                    parent.items += 1
                    if parent.kind == ord("{"):
                        if token != ord('"'):
                            raise _input_error("expected JSON member name")
                        index = self._string_end(payload, index)
                        parent.state = "colon"
                        continue
                parent.state = "end"
            if self._nodes >= self._limits.max_nodes:
                raise JsonDecodeLimitError("JSON node limit exceeded")
            self._nodes += 1
            root_seen = True
            if token in b"[{":
                if len(stack) >= self._limits.max_depth:
                    raise JsonDecodeLimitError("JSON depth limit exceeded")
                stack.append(_Container(token, "first"))
                index += 1
            elif token == ord('"'):
                index = self._string_end(payload, index)
            elif payload.startswith(b"true", index):
                index += 4
            elif payload.startswith(b"false", index):
                index += 5
            elif payload.startswith(b"null", index):
                index += 4
            else:
                number = _NUMBER.match(payload, index)
                if number is None:
                    raise _input_error("invalid JSON value")
                index = number.end()

    @staticmethod
    def _string_end(payload: bytes, index: int) -> int:
        index += 1
        while index < len(payload):
            token = payload[index]
            if token == ord('"'):
                return index + 1
            if token < 32:
                raise _input_error("control character in JSON string")
            if token == ord("\\"):
                index += 1
                if index >= len(payload):
                    break
                escape = payload[index]
                if escape == ord("u"):
                    if index + 4 >= len(payload) or any(
                        payload[i] not in b"0123456789abcdefABCDEF" for i in range(index + 1, index + 5)
                    ):
                        raise _input_error("invalid JSON unicode escape")
                    index += 4
                elif escape not in b'"\\/bfnrt':
                    raise _input_error("invalid JSON escape")
            index += 1
        raise _input_error("unterminated JSON string")
