import json
from pathlib import Path

from fastapi import HTTPException, UploadFile


class JsonResolver:

    @staticmethod
    async def resolve(
        file: UploadFile | None = None,
        path: str | None = None,
    ) -> dict | list:
        if file is not None and path is not None:
            raise HTTPException(status_code=400, detail="Provide either file or path, not both")
        if file is None and path is None:
            raise HTTPException(status_code=400, detail="Provide file or path")

        if file is not None:
            return await JsonResolver._from_upload(file)
        return JsonResolver._from_path(path)

    @staticmethod
    async def _from_upload(file: UploadFile) -> dict | list:
        try:
            raw = await file.read()
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise HTTPException(status_code=422, detail=f"JSON parse failed: {e}")

    @staticmethod
    def _from_path(path: str) -> dict | list:
        p = Path(path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"Path is not a file: {path}")
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise HTTPException(status_code=422, detail=f"JSON parse failed: {e}")
