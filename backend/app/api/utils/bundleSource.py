"""Select the world bundle transport before invoking the JSON-only resolver."""

import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.api.utils.jsonResolver import JsonResolver


async def resolve_bundle_source(
    *,
    file: UploadFile | None,
    path: str | None,
    read_archive: Callable[[Path], dict],
) -> dict | list:
    if (file is None) == (path is None):
        detail = "Provide file or path" if file is None else "Provide either file or path, not both"
        raise HTTPException(status_code=400, detail=detail)

    if file is not None:
        signature = await file.read(4)
        await file.seek(0)
        if signature != b"PK\x03\x04":
            return await JsonResolver.resolve(file=file)
        with tempfile.TemporaryDirectory(prefix="world-import-") as directory:
            archive_path = Path(directory) / "world.wpack"
            with archive_path.open("wb") as stream:
                while chunk := await file.read(1024 * 1024):
                    stream.write(chunk)
            return read_archive(archive_path)

    assert path is not None  # Exactly one source was checked above.
    source = Path(path)
    if not source.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    if not source.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {path}")
    with source.open("rb") as stream:
        signature = stream.read(4)
    if signature == b"PK\x03\x04":
        return read_archive(source)
    return await JsonResolver.resolve(path=path)
