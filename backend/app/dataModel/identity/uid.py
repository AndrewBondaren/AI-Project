"""Shared entity UID value contract — GEO-1 PC-0U; no UID generation."""

from typing import Annotated

from pydantic import StrictStr, StringConstraints


type EntityUid = Annotated[StrictStr, StringConstraints(min_length=1, pattern=r"^\S(?:.*\S)?$")]
