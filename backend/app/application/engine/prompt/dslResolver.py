from app.application.llm.models import ValidationResult


class DSLResolver:

    def update(self, dsl_keys, validation: ValidationResult):

        if validation.dsl_patch:
            dsl_keys = list(set(dsl_keys + validation.dsl_patch))

        return dsl_keys