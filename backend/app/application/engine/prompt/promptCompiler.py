class PromptCompiler:

    def __init__(self, dsl_registry, assembler):
        self.dsl_registry = dsl_registry
        self.assembler = assembler

    def compile_system(self, context) -> str:
        dsl_texts = [
            self.dsl_registry.get(key)
            for key in context.dsl_keys
        ]
        return "\n\n".join(dsl_texts)