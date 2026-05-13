from app.application.llm.models import ChatMessage

class PromptCompiler:

    def __init__(self, dsl_registry, assembler):
        self.dsl_registry = dsl_registry
        self.assembler = assembler

    def compile(self, context):

        dsl_texts = [
            self.dsl_registry.get(key)
            for key in context.dsl_keys
        ]

        system = "\n\n".join(dsl_texts)

        return [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=self.assembler.build_user(context))
        ]