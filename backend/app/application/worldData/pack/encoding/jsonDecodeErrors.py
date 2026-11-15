"""Typed preflight refusals, independent of read and preparation contexts."""

from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class JsonDecodeInputError(Exception):
    def __init__(self, issue: WireShapeIssue) -> None:
        self.issue = WireShapeIssue.model_validate(issue, strict=True)
        super().__init__(self.issue.message)


class JsonDecodeConfigurationError(Exception):
    def __init__(self, issues: tuple[WireShapeIssue, ...]) -> None:
        self.issues = tuple(WireShapeIssue.model_validate(issue, strict=True) for issue in issues)
        super().__init__("invalid JSON decode limits")
