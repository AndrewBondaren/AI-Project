from app.application.llm.engine.prompt.promptContext import PromptContext
 
class PromptCompiler:

    def __init__(self, dsl_registry, assembler):
        self.dsl_registry = dsl_registry
        self.assembler = assembler

    def compile(self, context: PromptContext):

        dsl_key = self._resolve_dsl(context)

        dsl = self.dsl_registry.get(dsl_key)

        system = self.assembler.build_system(dsl, context)
        user = self.assembler.build_user(context)

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    
    def _resolve_dsl(self, context):

        if not context.dsl:
            raise ValueError("PromptContext missing DSL")

        return context.dsl