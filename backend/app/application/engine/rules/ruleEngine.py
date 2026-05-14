class RuleEngine:

    def evaluate(self, node, state):

        for fn in node.compiled_rules:
            if not fn(node, state):
                return False

        return True