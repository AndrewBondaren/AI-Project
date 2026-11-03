"""Durable, immutable bytes under a DI-owned database artifact root."""

import asyncio
import ctypes
import hashlib
import os
from pathlib import Path
import tempfile
from collections.abc import Callable

from app.application.artifacts.contracts.blobRead import ReadableBlobBackend
from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.storage.artifactLeases import IArtifactLeases
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.lifecycle.lease import StagingReservation
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.storage.artifacts.blobRead import read_verified_file


class ContentAddressedBlobBackend(ReadableBlobBackend):
    def __init__(self, root: Path, contract: ArtifactFormatContract[bytes], leases: IArtifactLeases) -> None:
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("artifact root must be an absolute, non-symlink directory")
        if contract.kind is not ArtifactKind.BLOB or contract.content_model is not bytes:
            raise TypeError("blob backend requires a bytes BLOB contract")
        self._root = root.resolve()
        self._contract, self._leases = contract, leases

    @property
    def contract(self) -> ArtifactFormatContract[bytes]:
        return self._contract

    def _ref(self, ref: ArtifactRef) -> ArtifactRef:
        ref = ArtifactRef.model_validate(ref, strict=True)
        if (ref.kind is not ArtifactKind.BLOB or ref.format_key != self.contract.key
                or ref.format_version not in self.contract.supported_versions):
            raise ValueError("artifact does not belong to this backend contract")
        return ref

    def _contained(self, path: Path) -> Path:
        if not path.resolve().is_relative_to(self._root):
            raise PublicationInfrastructureError("artifact path escapes storage root")
        for component in (path, *path.parents):
            if component.is_symlink() or component.is_junction():
                raise PublicationInfrastructureError("artifact path contains a redirected component")
            if component == self._root:
                break
        return path

    def _path(self, ref: ArtifactRef) -> Path:
        # Neither format keys nor operation UIDs become path components.
        identity = hashlib.sha256(f"{ref.format_key}:{ref.format_version}".encode()).hexdigest()
        return self._contained(self._root / identity / ref.content_hash)

    @staticmethod
    async def _io[T](call: Callable[[], T]) -> T:
        # A cancelled caller must retain its writer claim until the worker stops.
        task = asyncio.create_task(asyncio.to_thread(call))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()
            raise

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        if os.name != "nt":
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def _verify(self, path: Path, ref: ArtifactRef) -> None:
        self._contained(path)
        digest, size = hashlib.sha256(), 0
        # Windows _commit/fsync requires a writable descriptor, without truncation.
        with path.open("r+b" if os.name == "nt" else "rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
            if size != ref.nbytes or digest.hexdigest() != ref.content_hash:
                raise PublicationInfrastructureError("missing or corrupt artifact content")
            os.fsync(stream.fileno())
        self._sync_directory(path.parent)

    def _temp(self, reservation: StagingReservation, data: bytes) -> Path:
        final = self._path(reservation.ref)
        final.parent.mkdir(parents=True, exist_ok=True)
        self._contained(final.parent)
        # Persist newly created namespace before publishing a file into it.
        self._sync_directory(self._root.parent)
        self._sync_directory(self._root)
        owner = hashlib.sha256(f"{reservation.lease.operation_id}:{reservation.lease.fence}".encode()).hexdigest()
        fd, name = tempfile.mkstemp(prefix=f".tmp-{owner}-", dir=final.parent)
        temp = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self._verify(temp, reservation.ref)
            return temp
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

    def _place(self, temp: Path, ref: ArtifactRef) -> None:
        final = self._path(ref)
        self._contained(temp)
        if os.name == "nt":
            # Same-volume rename, no REPLACE_EXISTING; WRITE_THROUGH waits for durability.
            move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
            move.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong)
            move.restype = ctypes.c_int
            if not move(str(temp), str(final), 0x8):
                error = ctypes.get_last_error()
                if error not in (80, 183):
                    raise ctypes.WinError(error)
        else:
            try:
                os.link(temp, final)
            except FileExistsError:
                pass
        # Existing content is verified, never repaired or overwritten.
        self._verify(final, ref)

    async def write(self, reservation: StagingReservation, content: bytes) -> None:
        reservation = StagingReservation.model_validate(reservation, strict=True)
        ref = self._ref(reservation.ref)
        if type(content) is not bytes:
            raise TypeError("BLOB content must be bytes")
        data = self.contract.encode(content)
        if type(data) is not bytes or len(data) != ref.nbytes or hashlib.sha256(data).hexdigest() != ref.content_hash:
            raise ValueError("content differs from reserved descriptor")
        async with self._leases.writer(reservation):
            await self._leases.assert_writable(reservation.lease)
            # Keep ownership of the temp even when cancellation arrives during its creation.
            temps: list[Path] = []
            def prepare() -> None:
                temps.append(self._temp(reservation, data))
            try:
                await self._io(prepare)
                await self._leases.assert_writable(reservation.lease)
                await self._io(lambda: self._place(temps[0], ref))
            finally:
                for temp in temps:
                    self._contained(temp).unlink(missing_ok=True)

    async def verify(self, ref: ArtifactRef) -> None:
        ref = self._ref(ref)
        await self._io(lambda: self._verify(self._path(ref), ref))

    async def read_verified(self, ref: ArtifactRef, *, max_bytes: int) -> bytes:
        if type(ref) is not ArtifactRef:
            raise ValueError("expected an ArtifactRef")
        ref = self._ref(ref)
        if type(max_bytes) is not int or not 0 < ref.nbytes <= max_bytes:
            raise ValueError("artifact size outside read budget")
        try:
            return await self._io(lambda: read_verified_file(self._path(ref), ref))
        except OSError as exc:
            raise PublicationInfrastructureError("cannot read artifact content") from exc

    async def delete(self, ref: ArtifactRef) -> None:
        """Caller must hold the shared GC guard and have rechecked the live-set."""
        ref = self._ref(ref)
        def remove() -> None:
            path = self._path(ref)
            path.unlink(missing_ok=True)
            if path.parent.exists():
                self._sync_directory(path.parent)
        await self._io(remove)
