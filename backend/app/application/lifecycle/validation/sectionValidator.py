"""Pure batch relations; subject payload/hash verification belongs to apply."""

from pydantic import BaseModel
from typing import Any
from typing import cast
from app.application.lifecycle.contracts.typedViews import section_request_view, ReasonView
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.sections.section import DomainSection

from app.application.lifecycle.contracts.sectionBinding import LifecycleSectionBinding
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation as Op
from app.dataModel.lifecycle.results.issues import LifecycleIssue, LifecycleFieldIssue, LifecycleRelationIssue, LifecycleRelationCode as R
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class LifecycleSectionValidator[Q: BaseModel, S: DomainSection[Any]]:
    def __init__(self, binding: LifecycleSectionBinding[Q, S]) -> None:
        self._binding = binding

    def validate(self, source: Q) -> tuple[LifecycleIssue, ...]:
        request = section_request_view(source)
        errors = ValidatorAggregationHelper[LifecycleIssue]((LifecycleFieldIssue, LifecycleRelationIssue))
        root = CheckedPath.root(type(request))
        changes_ref = FieldRef(lambda: type(request), lambda value: value.changes)
        evidence_ref = FieldRef(lambda: type(request), lambda value: value.domain_evidence)
        changes = changes_ref.select(request)
        evidence = evidence_ref.select(request)
        cp = root.field(changes_ref)
        ep = root.field(evidence_ref)

        def issue[A: BaseModel, B](code: R, path: CheckedPath[A, B], message: str) -> None:
            errors.add(LifecycleRelationIssue(code=code, path=path.freeze(), related_path=None, message=message))

        seen_changes: set[EntityUid] = set()
        seen_entities: set[LifecycleEntityRef[object]] = set()
        expected: dict[tuple[EntityUid, LifecycleEntityRef[object], str], tuple[int, EntityUid]] = {}
        for index, prepared in enumerate(changes):
            intent = prepared.transition.intent
            if prepared.base != request.expected_world:
                issue(R.BASE_MISMATCH, cp.item(index), "Prepared transition uses a different publication")
            if intent.change_uid in seen_changes:
                issue(R.DUPLICATE_CHANGE_UID, cp.item(index), "Duplicate logical change in one batch")
            seen_changes.add(intent.change_uid)
            local_entities: set[LifecycleEntityRef[object]] = set()
            for participant in prepared.transition.participants:
                entity = participant.after.entity
                if entity in local_entities:
                    issue(R.DUPLICATE_PARTICIPANT, cp.item(index), "Transition repeats an entity")
                if entity in seen_entities:
                    issue(R.PARTICIPANT_OVERLAP, cp.item(index), "Independent transitions must not share an entity")
                local_entities.add(entity)
                effect = (Op.END if entity in intent.predecessors else Op.CREATE) if intent.operation is Op.REPLACEMENT else intent.operation
                expected[(intent.change_uid, entity, effect)] = (index, cast(ReasonView, intent.reason).action_uid)
            seen_entities.update(local_entities)

        entries: dict[tuple[EntityUid, LifecycleEntityRef[object], str], list[int]] = {}
        for index, entry in enumerate(evidence):
            key = (entry.change_uid, entry.effect.entity, entry.effect.effect)
            entries.setdefault(key, []).append(index)
        for key, (change_index, action) in expected.items():
            indices = entries.get(key, [])
            if not indices:
                issue(R.COVERAGE_MISSING, cp.item(change_index), "Required subject effect has no prepared coverage")
            for index in indices:
                if evidence[index].effect.reason_action_uid != action:
                    issue(R.ADMISSION_MISMATCH, ep.item(index), "Coverage belongs to another subject action")
            for index in indices[1:]:
                issue(R.COVERAGE_DUPLICATE, ep.item(index), "Duplicate coverage for the same typed effect")
        fingerprints: dict[str, str] = {}
        for index, entry in enumerate(evidence):
            key = (entry.change_uid, entry.effect.entity, entry.effect.effect)
            if key not in expected:
                issue(R.COVERAGE_EXTRA, ep.item(index), "Coverage has no corresponding transition effect")
            refs: set[PatchRef] = set()
            for ref in entry.patch_refs:
                if ref in refs:
                    issue(R.COVERAGE_DUPLICATE, ep.item(index), "Coverage repeats a patch ref")
                refs.add(ref)
                if ref.operation_id != request.operation_id:
                    issue(R.PATCH_OPERATION_MISMATCH, ep.item(index), "Subject patch belongs to another publication operation")
                if ref.section_key != entry.section.section_key:
                    issue(R.PATCH_SECTION_MISMATCH, ep.item(index), "Patch ref belongs to another section")
            section_key = entry.section.section_key
            if section_key == self._binding.section_contract.key:
                issue(R.SELF_DEPENDENCY, ep.item(index), "Lifecycle cannot provide its own subject coverage")
            if section_key in fingerprints and fingerprints[section_key] != entry.section.section_fingerprint:
                issue(R.FINGERPRINT_CONFLICT, ep.item(index), "One subject section has conflicting declared fingerprints")
            fingerprints.setdefault(section_key, entry.section.section_fingerprint)
        return errors.snapshot()
