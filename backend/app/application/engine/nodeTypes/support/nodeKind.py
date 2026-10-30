from enum import Enum


class NodeKind(str, Enum):
    PYTHON = "python"
    LLM = "llm"
