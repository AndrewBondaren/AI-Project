"""Input field metadata separating request execution policy from source state."""

from enum import StrEnum


class SourceFieldRole(StrEnum):
    EXECUTION_POLICY = "execution_policy"
