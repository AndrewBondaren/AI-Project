class RuleEngine:

    def evaluate(self, compiled_node, state) -> bool:

        for fn in compiled_node.compiled_rules:
            if not fn(compiled_node.node, state):
                return False

        return True