class PromptCompiler:

    def compile_system(self, context) -> str:
        dsl_texts = [
            self.dsl_registry.get(key)
            for key in context.dsl_keys
        ]

        return "\n\n".join(dsl_texts)