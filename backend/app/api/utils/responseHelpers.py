from fastapi.responses import JSONResponse


def json_or_download(content: dict | list, download: bool, filename: str) -> JSONResponse:
    if download:
        return JSONResponse(
            content=content,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return JSONResponse(content=content)
