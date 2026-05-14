class TaskRuleHandler:

    def compile(self, params):

        def fn(node, state):
            return state.task_type in node.supported_tasks

        return fn