import re
from enum import Enum

from app.application.engine.validation.validationStatus import ValidationResult

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _fmt_value(v) -> str:
    if isinstance(v, list):
        items = [i.value if isinstance(i, Enum) else str(i) for i in v]
        return "[" + ", ".join(items) + "]"
    if isinstance(v, Enum):
        return v.value
    return str(v)


class DSLResolver:

    def __init__(self, dsl_registry):
        self.dsl_registry = dsl_registry

    def resolve_patches(self, node, validation: ValidationResult) -> list[str]:
        """
        Возвращает список dsl_patch ключей для всех ошибок validation.
        Одна ошибка -> один патч (если объявлен на ноде).
        """
        patches = []
        for error in validation.errors:
            patch_key = node.dsl_patches.get(error.code)
            if patch_key and patch_key not in patches:
                patches.append(patch_key)
        return patches

    def update(self, dsl_keys: list[str], patch_keys: list[str]) -> list[str]:
        result = list(dsl_keys)
        for key in patch_keys:
            if key not in result:
                result.append(key)
        return result
    
    def resolve(self, keys: list[str], context: dict | None = None) -> str:
        parts = [self.dsl_registry.get(key) for key in keys]
        text = "\n\n".join(parts)
        if context:
            text = _PLACEHOLDER_RE.sub(lambda m: _fmt_value(context.get(m.group(1), m.group(0))), text)
        return text