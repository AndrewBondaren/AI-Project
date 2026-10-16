"""Target template body preparation — TZ domain libraries §1–2/6–7.

No SQL, member creation, fallback or cross-domain availability decisions.
Full POJO validation precedes a separate graph check against supplied facts.
"""

from collections.abc import Mapping
from typing import ClassVar, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.jsonValidation.sourceValidation import validate_prepared_source
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.libraryPacks.domainAdapters.contract import (
    SYSTEM_NAME_FIELD,
)
from app.application.worldData.libraryPacks.domainAdapters.refFields import (
    remap_template_body, template_body_refs,
)
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.ids import LibraryKind


class TemplatePreparationError(LibraryPackValidationError):
    def __init__(self, issues: tuple[FieldPathError, ...]):
        self.issues = issues
        super().__init__('; '.join(f'{issue.path}: {issue.message}' for issue in issues))


class TemplateBodyPreparation[T: BaseModel]:
    library_kind: ClassVar[LibraryKind]
    model: type[T]
    model_a: ClassVar[bool] = False

    def prepare_body(self, raw: dict, *, local_uid: str, template_uid: str, world=None) -> T:
        path = (self.library_kind.value, template_uid)
        issues = []
        try:
            if not isinstance(template_uid, str) or str(UUID(template_uid)) != template_uid:
                raise ValueError()
        except (ValueError, AttributeError, TypeError):
            issues.append(FieldPathError(path, 'member identity must be a canonical UUID', code='TEMPLATE_UID'))
        if not isinstance(raw, dict):
            issues.append(FieldPathError(path, 'template body must be an object', code='EXPECTED_OBJECT'))
            raise TemplatePreparationError(tuple(issues))
        payload = dict(raw)
        if self.model_a and SYSTEM_NAME_FIELD not in payload:
            payload[SYSTEM_NAME_FIELD] = template_uid
        try:
            body = self.model.model_validate(payload)
        except ValidationError as exc:
            issues.extend(FieldPathError(path + tuple(error['loc']), error['msg'], code=error['type'])
                          for error in exc.errors())
            raise TemplatePreparationError(tuple(issues)) from exc
        expected = template_uid if self.model_a else local_uid
        if str(body.system_name) != expected:
            issues.append(FieldPathError(path + (SYSTEM_NAME_FIELD,),
                'body name does not match declared member identity/key', code='TEMPLATE_IDENTITY'))
        for ref in self.body_refs(body, template_uid):
            try:
                if str(UUID(ref.template_uid)) != ref.template_uid:
                    raise ValueError()
            except ValueError:
                issues.append(FieldPathError(path + (ref.path,),
                    'template reference must be a canonical UUID', code='TEMPLATE_REF_UID'))
        if issues:
            raise TemplatePreparationError(tuple(issues))
        if world is not None:
            self.validate_world(body, world, path)
        return body

    def validate_world(self, body: T, world, path: tuple) -> None:
        ctx = ResolveContext.for_import(validate_only=True)
        ctx.path_prefix = path
        try:
            validate_prepared_source(world, body, ctx=ctx)
        except UnresolvedModelError as exc:
            raise TemplatePreparationError(tuple(exc.issues)) from exc

    def body_refs(self, body: T, consumer: str):
        return template_body_refs(self.library_kind, body, consumer)

    def remap_body(self, body: T, uid_map: Mapping[str, str]) -> T:
        return cast(T, remap_template_body(self.library_kind, body, uid_map))
