class LLMValidator:

    def __init__(self, contract_validator, node_validator):
        self.contract_validator = contract_validator
        self.node_validator = node_validator

    def validate(self, node, output, contract, state):

        # 1. hard gate
        result = self.contract_validator.validate(output, contract)

        if not result.ok:
            return result

        # 2. logic gate
        return self.node_validator.validate(node, output, state)