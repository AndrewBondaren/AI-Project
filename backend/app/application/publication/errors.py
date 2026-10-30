"""Infrastructure/recovery errors are not domain apply outcomes."""


class PublicationInfrastructureError(RuntimeError):
    pass


class UnknownCommitOutcome(PublicationInfrastructureError):
    pass


class OperationBusyError(RuntimeError):
    pass
