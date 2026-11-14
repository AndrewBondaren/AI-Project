"""Semantic revision value; no hash calculation or sequence allocation."""

from typing import Annotated

from pydantic import Field, StrictInt

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class SourceRevision(SourceValue, frozen=True):
    seq: Annotated[StrictInt, Field(gt=0)]
    content_hash: RevisionHex
