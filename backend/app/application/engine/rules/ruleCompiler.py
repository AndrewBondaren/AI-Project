from app.application.engine.rules.rule import Rule


class RuleCompiler:

    def __init__(self, registry):
        self.registry = registry

    def compile(self, rules: list[Rule]):

        compiled = []

        for rule in rules:
            handler = self.registry.get(rule.type)

            fn = handler.compile(rule.params)
            compiled.append(fn)

        return compiled