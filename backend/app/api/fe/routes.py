from fastapi import APIRouter
from pydantic import BaseModel
from app.methods.compile import compile_dsl

router = APIRouter()

class CompileRequest(BaseModel):
    code: str

@router.get("/health")
def health():
    return {
        "status": "ok"
    }

@router.post("/compile")
def compile(req: CompileRequest):
    return compile_dsl(req.code)