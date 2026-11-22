"""Relations to admitted subject claims; never interprets subject mutations."""
from typing import Protocol, cast
from pydantic import BaseModel
from app.application.lifecycle.validation.stateValidator import Native
from app.application.lifecycle.contracts.typedViews import ReasonView
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.evidence.effects import DomainEffect, LifecycleEffectKind
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyCode, LifecycleApplyIssue
from app.dataModel.lifecycle.publication.section import LifecycleSection
from app.dataModel.patch.changes.header import PatchHeader
from app.dataModel.patch.sections.section import SectionHeader
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionRefused
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind


class SubjectPatchClaims(Protocol):
    @property
    def header(self) -> PatchHeader: ...
    @property
    def base(self) -> WorldPublicationRef: ...
    @property
    def effects(self) -> tuple[DomainEffect[object], ...]: ...


class SubjectSectionClaims(Protocol):
    @property
    def header(self) -> SectionHeader: ...
    @property
    def patches(self) -> tuple[SubjectPatchClaims, ...]: ...


type _EffectKey = tuple[EntityUid, LifecycleEntityRef[object], LifecycleEffectKind, EntityUid]


def _require_transition_coverage(native: Native) -> None:
    """Reject structurally valid native input that bypassed prepare relations."""
    required: set[_EffectKey] = set()
    for patch in native.patches:
        intent = patch.prepared.transition.intent
        action = cast(ReasonView, intent.reason).action_uid
        for participant in patch.prepared.transition.participants:
            entity = participant.after.entity
            effect: LifecycleEffectKind
            if intent.operation is LifecycleOperation.REPLACEMENT:
                effect = "end" if entity in intent.predecessors else "create"
            elif intent.operation is LifecycleOperation.CREATE:
                effect = "create"
            elif intent.operation is LifecycleOperation.END:
                effect = "end"
            else:
                effect = "reactivate"
            key = (intent.change_uid, entity, effect, action)
            if key in required:
                raise ValueError("native transitions contain a duplicate required effect")
            required.add(key)
    seen: set[_EffectKey] = set()
    violations: list[str] = []
    for index, entry in enumerate(native.domain_evidence):
        key = (entry.change_uid, entry.effect.entity, entry.effect.effect, entry.effect.reason_action_uid)
        if key not in required:
            violations.append(f"domain_evidence[{index}]: no matching transition/change/entity/effect/action")
        if key in seen:
            violations.append(f"domain_evidence[{index}]: duplicate transition coverage")
        seen.add(key)
    if required - seen:
        violations.append("domain_evidence: missing required transition effects")
    if violations:
        raise ValueError(tuple(violations))


class LifecycleEvidenceValidator[F: SectionRefused[LifecycleApplyIssue]]:
    def __init__(self, refusal_model: type[F]) -> None:
        self._refusal_model = refusal_model

    def validate(
        self, section: BaseModel, *, prepared_domain_sections: tuple[SubjectSectionClaims, ...],
        expected_world: WorldPublicationRef, operation_id: EntityUid,
    ) -> SectionAccepted | F:
        section_model = type(section)
        if not isinstance(section, LifecycleSection):
            raise TypeError("evidence validation requires a native Lifecycle section")
        native = cast(Native, section_model.model_validate(section, strict=True))
        if any(p.prepared.base != expected_world or p.header.ref.operation_id != operation_id for p in native.patches):
            raise ValueError("Lifecycle native base/operation differs from admitted context")
        _require_transition_coverage(native)
        sources = {source.header.key: source for source in prepared_domain_sections}
        if len(sources) != len(prepared_domain_sections):
            raise ValueError("duplicate admitted subject section")
        if set(sources) != {entry.section.section_key for entry in native.domain_evidence}:
            raise ValueError("subject projection must cover exactly the promised evidence sections")
        errors = ValidatorAggregationHelper[LifecycleApplyIssue]((LifecycleApplyIssue,))
        evidence_ref = FieldRef(lambda: type(native), lambda value: value.domain_evidence)
        evidence_path = CheckedPath.root(type(native)).field(evidence_ref)
        for index, entry in enumerate(evidence_ref.select(native)):
            if entry.section not in native.header.depends_on:
                raise ValueError("evidence dependency is absent from native header")
            source = sources[entry.section.section_key]
            path = evidence_path.item(index).variant(type(entry))
            effects_ref = FieldRef(lambda: type(entry), lambda value: value.effect)
            refs_ref = FieldRef(lambda: type(entry), lambda value: value.patch_refs)
            expected_refs = tuple(p.header.ref for p in source.patches if entry.effect in p.effects)
            if not expected_refs:
                errors.add(LifecycleApplyIssue(code=LifecycleApplyCode.EVIDENCE_MISMATCH,
                    path=path.field(effects_ref).freeze(), message="Admitted subject section does not claim this typed effect"))
            for ordinal, ref in enumerate(refs_ref.select(entry)):
                matches = tuple(p for p in source.patches if p.header.ref == ref)
                if (len(matches) != 1 or ref.operation_id != operation_id
                        or matches[0].base != expected_world or entry.effect not in matches[0].effects):
                    errors.add(LifecycleApplyIssue(code=LifecycleApplyCode.EVIDENCE_MISMATCH,
                        path=path.field(refs_ref).item(ordinal).freeze(),
                        message="Evidence patch ref contradicts admitted effect, action, entity or base"))
            if expected_refs and entry.patch_refs != expected_refs and all(ref in expected_refs for ref in entry.patch_refs):
                errors.add(LifecycleApplyIssue(code=LifecycleApplyCode.EVIDENCE_MISMATCH,
                    path=path.field(refs_ref).freeze(), message="Coverage must retain every matching patch in source order"))
        issues = errors.snapshot()
        return (self._refusal_model(category=SnapshotApplyOutcomeKind.CONFLICT, diagnostics=issues)
                if issues else SectionAccepted())
