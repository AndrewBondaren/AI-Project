"""Shared patch scalar constraints; tz_patch_system, core contract freeze."""

from typing import Annotated

from pydantic import Field, StrictInt


type FormatVersion = Annotated[StrictInt, Field(gt=0)]
type PatchOrdinal = Annotated[StrictInt, Field(ge=0)]
