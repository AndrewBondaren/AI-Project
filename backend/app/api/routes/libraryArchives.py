"""Standalone engine library archive transport; common application policy."""
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.deps import get_container
from app.api.libraryWrite import parse_negotiation, write_response
from app.api.utils.bundleSource import resolve_bundle_source
from app.application.worldData.bundle.errors import BundleValidationError
from app.application.worldData.libraryPacks.archiveSources import packs_from_wire

router = APIRouter()


@router.post("/library-packs/import")
async def import_library(file: UploadFile | None = File(default=None), path: str | None = Form(default=None),
                         decisions: str | None = Form(default=None), preview_token: str | None = Form(default=None),
                         container=Depends(get_container)):
    archives = container.library_pack_service().archives
    try:
        raw = await resolve_bundle_source(file=file, path=path, read_archive=archives.read_engine_archive)
        negotiation = parse_negotiation(decisions, preview_token)
        return write_response(await archives.import_engine(packs_from_wire(raw),
            decisions=negotiation.decisions, preview_token=negotiation.preview_token))
    except (BundleValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/library-packs/{pack_uid}/export")
async def export_library(pack_uid: str, container=Depends(get_container)):
    temporary = tempfile.TemporaryDirectory(prefix="library-export-")
    try:
        path = await container.library_pack_service().archives.write_engine_archive(
            pack_uid, path=Path(temporary.name) / "library.wpack")
        return FileResponse(path, media_type="application/zip", filename=f"library_{pack_uid}.wpack",
                            background=BackgroundTask(temporary.cleanup))
    except Exception:
        temporary.cleanup()
        raise
