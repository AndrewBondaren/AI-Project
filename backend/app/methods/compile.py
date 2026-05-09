def compile_dsl(code: str):
    if not code.strip():
        return {"success": False, "error": "Empty code"}

    return {
        "ast": ["ROOT", code],
        "success": True,
        "code": code
    }