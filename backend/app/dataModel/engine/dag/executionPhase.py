"""Execution phases and the Python-node subset. SoT: node context §6.1."""

from enum import StrEnum
from typing import Literal

from pydantic import TypeAdapter


class ExecutionPhase(StrEnum):
    PRE_LLM = "pre_llm"
    LLM = "llm"
    POST_LLM = "post_llm"


type PythonExecutionPhase = Literal[ExecutionPhase.PRE_LLM, ExecutionPhase.POST_LLM]


def validate_python_phase(value: object) -> PythonExecutionPhase:
    # StrEnum compares equal to its wire string. Check enum membership before
    # Literal validation so the Python boundary cannot admit raw strings.
    if not isinstance(value, ExecutionPhase):
        raise TypeError("Python node phase must be an ExecutionPhase member")
    return TypeAdapter[PythonExecutionPhase](PythonExecutionPhase).validate_python(value)
