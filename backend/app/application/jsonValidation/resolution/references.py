"""Check nominal registry references in resolved models."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, RootModel

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.resolution.wireIssues import field_issue
from app.application.jsonValidation.types import ImportIssue
from app.dataModel.registryKey import registry_key_target
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode

if TYPE_CHECKING:
    from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex


def reference_issues(value: Any, ctx: ResolveContext, references: WorldRegistryIndex,
                      root: type[BaseModel] | None = None,
                      loc: tuple[str | int, ...] = ()) -> list[ImportIssue]:
    """Membership over validated POJOs, reusing nominal RegistryKey metadata."""
    issues: list[ImportIssue] = []
    if isinstance(value, BaseModel):
        root = root if root is not None else type(value)
        for name, info in type(value).model_fields.items():
            item = getattr(value, name)
            field_loc = loc if isinstance(value, RootModel) else (*loc, info.alias if isinstance(info.alias, str) else name)
            target = registry_key_target(info.annotation)
            if target is not None and item is not None:
                keys = references.keys_for_registry(target)
                tokens = list(enumerate(item)) if isinstance(item, (list, tuple)) else [(None, item)]
                for index, token in tokens:
                    if token is None:
                        continue  # A validated optional list member is not a reference.
                    if keys is None or str(token) not in keys:
                        issues.append(field_issue(ctx, root,
                            field_loc if index is None else (*field_loc, index),
                            "reference index unavailable" if keys is None else f"unknown reference: {token!r}",
                            JsonValidationCode.REF_W_UNAVAILABLE if keys is None else JsonValidationCode.REF_W_UNKNOWN))
            else:
                issues.extend(reference_issues(item, ctx, references, root, field_loc))
    elif isinstance(value, (list, tuple, dict)):
        for index, item in (enumerate(value) if isinstance(value, (list, tuple)) else value.items()):
            issues.extend(reference_issues(item, ctx, references, root, (*loc, index)))
    return issues
