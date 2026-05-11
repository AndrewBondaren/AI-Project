class ExecutionContext:
    def __init__(self, session, router, executors, prompt_builder_registry):
        self.session = session
        self.router = router
        self.executors = executors
        self.prompt_builder_registry = prompt_builder_registry