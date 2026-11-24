from enum import StrEnum


class LifecycleRefusalKind(StrEnum):
    FIELD_REFUSAL = "field_refusal"
    LOGIC_REFUSAL = "logic_refusal"
    SECTION_REFUSAL = "section_refusal"
