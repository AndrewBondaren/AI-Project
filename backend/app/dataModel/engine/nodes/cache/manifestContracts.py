"""Concrete manifest-byte lookup contracts for explicit DAG registration."""

from app.dataModel.engine.nodes.cache.contracts import (
    CreateCacheEntryInput, CreateCacheEntryOutput, ReadCacheEntryInput, ReadCacheEntryOutput,
    UpdateCacheEntryInput, UpdateCacheEntryOutput,
)


class ReadManifestCacheEntryInput(ReadCacheEntryInput[bytes]):
    pass


class ReadManifestCacheEntryOutput(ReadCacheEntryOutput[bytes]):
    pass


class CreateManifestCacheEntryInput(CreateCacheEntryInput[bytes]):
    pass


class CreateManifestCacheEntryOutput(CreateCacheEntryOutput):
    pass


class UpdateManifestCacheEntryInput(UpdateCacheEntryInput[bytes]):
    pass


class UpdateManifestCacheEntryOutput(UpdateCacheEntryOutput):
    pass
