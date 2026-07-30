from pydantic import BaseModel

from app.application.importResult import ImportError, ImportResult

__all__ = ["PathImportRequest", "ImportError", "ImportResult"]


class PathImportRequest(BaseModel):
    path: str
