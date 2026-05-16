from app.application.engine.validation.validationStatus import ValidationResult


class DSLResolver:

    def __init__(self, dsl_registry):
        self.dsl_registry = dsl_registry

    def resolve_patches(self, node, validation: ValidationResult) -> list[str]:
        """
        Возвращает список dsl_patch ключей для всех ошибок validation.
        Одна ошибка → один патч (если объявлен на ноде).
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
    
    def resolve(self, keys: list[str]) -> str:
        parts = [self.dsl_registry.get(key) for key in keys]
        return "\n\n".join(parts)