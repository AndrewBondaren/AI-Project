"""Explicit content/backend binding; type erasure stays private to this registry."""

from collections.abc import Awaitable, Callable
from typing import cast
from pydantic import BaseModel

from app.application.artifacts.contracts.formatBackend import ArtifactBackend, ArtifactFormatContract
from app.dataModel.artifacts.references import ArtifactFormatKey, ArtifactFormatMetadata, ArtifactRef
from app.dataModel.patch.values import FormatVersion


class ArtifactFormatRegistryBinding:
    def __init__(self) -> None:
        self._bindings: dict[ArtifactFormatKey, tuple[object, object]] = {}
        self._verify: dict[ArtifactFormatKey, Callable[[ArtifactRef], Awaitable[None]]] = {}
        self._delete: dict[ArtifactFormatKey, Callable[[ArtifactRef], Awaitable[None]]] = {}
        self._metadata: dict[ArtifactFormatKey, ArtifactFormatMetadata] = {}

    def register[C: bytes | BaseModel](self, contract: ArtifactFormatContract[C], backend: ArtifactBackend[C]) -> None:
        contract.__post_init__()
        if contract.key in self._bindings:
            raise ValueError("duplicate artifact format key")
        if not isinstance(backend, ArtifactBackend):
            raise TypeError("backend must implement ArtifactBackend")
        if backend.contract is not contract:
            raise ValueError("backend must declare the registered contract instance")

        def check(ref: ArtifactRef) -> None:
            ArtifactRef.model_validate(ref)
            if (ref.format_key != contract.key or ref.kind is not contract.kind
                    or ref.format_version not in contract.supported_versions):
                raise ValueError("artifact does not match the registered format")

        async def verify(ref: ArtifactRef) -> None:
            check(ref)
            await backend.verify(ref)

        async def delete(ref: ArtifactRef) -> None:
            check(ref)
            await backend.delete(ref)

        self._bindings[contract.key] = (contract, backend)
        self._verify[contract.key] = verify
        self._delete[contract.key] = delete
        self._metadata[contract.key] = ArtifactFormatMetadata(key=contract.key, supported_versions=contract.supported_versions)

    def resolve[C: bytes | BaseModel](self, contract: ArtifactFormatContract[C]) -> ArtifactBackend[C]:
        binding = self._bindings.get(contract.key)
        if binding is None:
            raise ValueError("unknown artifact format key")
        if binding[0] is not contract:
            raise TypeError("artifact contract is not the registered content binding")
        # Identity was checked against the immutable contract that fixed C at registration.
        return cast(ArtifactBackend[C], binding[1])

    def metadata(self, key: ArtifactFormatKey) -> ArtifactFormatMetadata:
        try:
            return self._metadata[key]
        except KeyError as exc:
            raise ValueError("unknown artifact format key") from exc

    def encode[C: bytes | BaseModel](self, contract: ArtifactFormatContract[C], content: C) -> bytes:
        self.resolve(contract)
        if type(content) is not contract.content_model:
            raise TypeError("content does not have the exact registered model")
        if isinstance(content, BaseModel):
            content = cast(C, type(content).model_validate(content, strict=True))
        payload = contract.encode(content)
        if type(payload) is not bytes:
            raise TypeError("artifact encoder must return bytes")
        return payload

    def decode[C: bytes | BaseModel](self, contract: ArtifactFormatContract[C], payload: bytes, version: FormatVersion) -> C:
        self.resolve(contract)
        if type(payload) is not bytes or type(version) is not int or version not in contract.supported_versions:
            raise ValueError("unsupported artifact bytes or version")
        content = contract.decode(payload, version)
        if type(content) is not contract.content_model:
            raise TypeError("decoded content does not have the registered model")
        if isinstance(content, BaseModel):
            content = cast(C, type(content).model_validate(content, strict=True))
        return content

    async def verify(self, ref: ArtifactRef) -> None:
        self.metadata(ref.format_key)
        await self._verify[ref.format_key](ref)

    async def delete(self, ref: ArtifactRef) -> None:
        self.metadata(ref.format_key)
        await self._delete[ref.format_key](ref)
