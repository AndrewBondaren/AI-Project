class RuleHandlerRegistry:

    def __init__(self):
        self._handlers = {}

    def register(self, rule_type: str, handler):
        self._handlers[rule_type] = handler

    def get(self, rule_type: str):
        return self._handlers[rule_type]
    

#registry = RuleHandlerRegistry()

#registry.register("task", TaskRuleHandler())
#registry.register("deps_ready", DepsReadyHandler())
#registry.register("state_flag", StateFlagHandler())
#registry.register("expression", ExpressionHandler())