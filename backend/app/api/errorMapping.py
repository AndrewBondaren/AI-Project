"""Domain-error → HTTP mapping — single seam (W1-1).

Registered via ``install_error_handlers(app)`` in ``core/app.py`` so a
missed call site cannot degrade to 500. Route-level ``raise
HTTPException`` for request-shape checks stays a legitimate api concern;
per-route catches (``ReliefValidationError``, ``BundleValidationError``)
are untouched.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.application.jsonValidation.types import (
    ImportValidationError,
    import_validation_http_detail,
)
from app.application.worldData.errors import (
    WorldDataNotFoundError,
    WorldDataValidationError,
)


def install_error_handlers(app: FastAPI) -> None:
    from app.api.libraryWrite import library_error_response
    from app.application.templateLibrary.packs.errors import LibraryPackError

    @app.exception_handler(LibraryPackError)
    async def _library_error(_request: Request, exc: LibraryPackError) -> JSONResponse:
        return library_error_response(exc)

    @app.exception_handler(WorldDataNotFoundError)
    async def _world_data_not_found(
        _request: Request, exc: WorldDataNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(WorldDataValidationError)
    async def _world_data_validation(
        _request: Request, exc: WorldDataValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ImportValidationError)
    async def _import_validation(
        _request: Request, exc: ImportValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": import_validation_http_detail(exc)},
        )
