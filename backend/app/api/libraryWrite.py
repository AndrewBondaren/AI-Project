"""Shared transport for existing library write entry points."""
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.application.templateLibrary.packs.errors import (
    LibraryPackConflictError, LibraryPackInUseError, LibraryPackNotFoundError,
    LibraryPackOwnershipError, LibraryPackPolicyRequiredError, LibraryPackReadOnlyError,
    LibraryPackValidationError,
)
from app.application.templateLibrary.packs.write.writeContracts import LibraryWriteSelection
from app.application.templateLibrary.packs.write.writeResults import PolicyRequired


class WriteNegotiation(BaseModel):
    decisions: tuple[LibraryWriteSelection, ...] = ()
    preview_token: str | None = None


def parse_negotiation(decisions: str | None = None, preview_token: str | None = None) -> WriteNegotiation:
    try:
        parsed = TypeAdapter(tuple[LibraryWriteSelection, ...]).validate_json(decisions) if decisions else ()
        return WriteNegotiation(decisions=parsed, preview_token=preview_token)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_context=False))) from exc


def policy_response(outcome: PolicyRequired) -> JSONResponse:
    previews = []
    for variant in outcome.preview:
        preview = {"actions": variant.actions, "issues": variant.issues, "copy": variant.copy}
        if variant.plan is not None:
            plan = variant.plan
            preview.update(items=[{"item_key": item.item_key,
                "pack_uid": item.pack.value.pack_uid if item.pack else None,
                "metadata_changes": item.pack.changes if item.pack else (),
                "members": [{"template_uid": w.value.member.template_uid, "added": w.added,
                             "changes": w.changes} for w in item.members],
                "preserved": item.preserved} for item in plan.items],
                removed=[m.template_uid for m in plan.removed], held=dict(plan.held),
                diagnostics=plan.diagnostics)
        previews.append(preview)
    choices = [{"item_key": choice.item_key, "matches": choice.matches,
                "options": [{"policy": o.policy, "target_uid": o.target_uid,
                             "allowed": o.allowed, "reasons": o.reasons} for o in choice.options]}
               for choice in outcome.choices]
    return JSONResponse(status_code=409, content=jsonable_encoder({"status": outcome.status,
        "preview_token": outcome.preview_token, "choices": choices, "preview": previews, "stale": outcome.stale}))


def write_response(outcome) -> JSONResponse:
    """Expose applied identities/remap, never raw bodies or persistence plans."""
    if isinstance(outcome, PolicyRequired):
        return policy_response(outcome)
    return JSONResponse(content=jsonable_encoder({"status": outcome.status,
        "items": [{"item_key": item.item_key, "pack_uid": item.pack.value.pack_uid if item.pack else None,
                   "members": [w.value.member.template_uid for w in item.members],
                   "uid_map": dict(item.uid_map)} for item in outcome.plan.items]}))


def library_error_response(exc) -> JSONResponse:
    if isinstance(exc, LibraryPackPolicyRequiredError):
        return policy_response(exc.outcome)
    code = 500
    if isinstance(exc, LibraryPackNotFoundError):
        code = 404
    elif isinstance(exc, (LibraryPackReadOnlyError, LibraryPackOwnershipError)):
        code = 403
    elif isinstance(exc, LibraryPackValidationError):
        code = 422
    elif isinstance(exc, (LibraryPackConflictError, LibraryPackInUseError)):
        code = 409
    return JSONResponse(status_code=code, content={"detail": str(exc)})
