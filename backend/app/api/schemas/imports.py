from pydantic import BaseModel

from app.application.imports.result import ImportError, ImportResult

__all__ = ["PathImportRequest", "ImportError", "ImportResult"]


class PathImportRequest(BaseModel):
    path: str
