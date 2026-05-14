#class ExecutionContractRegistry:
#
#    def __init__(self):
#        self._contracts = {}

#    def register(self, node_cls, contract):
#        self._contracts[node_cls] = contract
#
#    def get(self, node):
#        node_type = type(node)
#
        # прямое совпадение
#        if node_type in self._contracts:
#            return self._contracts[node_type]
#
#        # fallback через inheritance (MRO)
#        for cls in node_type.__mro__[1:]:
#            if cls in self._contracts:
#                return self._contracts[cls]
#
#        raise ValueError(
#            f"No execution contract registered for node type: {node_type.__name__}"
#        )