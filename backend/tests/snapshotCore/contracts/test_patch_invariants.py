"""Core invariants and canonical-preserving shared model migration."""

import itertools
import unittest
from pydantic import ValidationError

from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.request.patchSetData import PatchSetData
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.dataModel.patch.validation.invariantDetails import (
    PatchSetInvariantCode as Code, WorldMismatchDetails, MissingPackDetails, DuplicatePlayerDetails,
    DuplicateSectionDetails, MissingPreparedDependencyDetails, PreparedDependencyOrderDetails,
    PatchOperationMismatchDetails, PatchSectionMismatchDetails, DuplicatePatchOrdinalDetails,
)
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.patch.validation.patchSetInvariants import PatchSetInvariants
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef, PlayerHeadExpectation
from tests.snapshotCore.support.fakeSection import HeaderOnlyPatch, FakePatch


def section(key="x", refs=None, dependencies=()):
    refs = refs if refs is not None else (("op", key, 0),)
    return DomainSection[HeaderOnlyPatch](
        header=SectionHeader(key=RegistryKey[PatchSectionRegistry](key), format_version=1, depends_on=tuple(
            PreparedSectionDependency(section_key=RegistryKey[PatchSectionRegistry](dep), section_fingerprint="a" * 64)
            for dep in dependencies)),
        patches=tuple(HeaderOnlyPatch(header=PatchHeader(ref=PatchRef(
            operation_id=operation, section_key=RegistryKey[PatchSectionRegistry](patch_key), ordinal=ordinal),
            format_version=1, depends_on=(), artifacts=())) for operation, patch_key, ordinal in refs))


def values(sections=()):
    return dict(format_version=1, operation_id="op", preparation_fingerprint="b" * 64,
        world_uid="world", timeline_id="main", turn_id=1,
        expected_world=WorldPublicationRef(world_uid="world", publication_id="pub", pack_hash="a" * 64,
            snapshot_head=None, active_timeline_id="main", gameplay_started=True),
        expected_players=(), sections=sections)


class PatchInvariantTests(unittest.TestCase):
    def test_independent_identity_and_ordinal_failures(self):
        request = PatchSetAssemblyInput[DomainSection[HeaderOnlyPatch]](**values((
            section(refs=(("A", "wrong", 0), ("B", "wrong", 0), ("op", "x", 0))),)))
        facts = PatchSetInvariants.check_core(request)
        self.assertEqual([fact.details.code for fact in facts], [
            Code.PATCH_OPERATION_MISMATCH, Code.PATCH_SECTION_MISMATCH,
            Code.PATCH_OPERATION_MISMATCH, Code.PATCH_SECTION_MISMATCH, Code.DUPLICATE_PATCH_ORDINAL,
            Code.DUPLICATE_PATCH_ORDINAL])
        self.assertEqual([fact.related_index for fact in facts[-2:]], [0, 0])
        with self.assertRaises(ValidationError):
            PatchSet[DomainSection[HeaderOnlyPatch]](**values(request.sections))
        for sections in ((section("x"), section("y")), (section(refs=(("op", "x", 12),)),)):
            self.assertEqual(PatchSetInvariants.check_core(PatchSetAssemblyInput(**values(sections))), ())

    def test_all_batch_relations_aggregate_in_order(self):
        data = values((section(), section()))
        data["world_uid"] = "wrong"
        data["expected_world"] = WorldPublicationRef(world_uid="world", publication_id="pub", pack_hash=None,
            snapshot_head=None, active_timeline_id=None, gameplay_started=False)
        player = PlayerHeadExpectation(player_uid="p", expected_head=None)
        data["expected_players"] = (player, player, player)
        request = PatchSetAssemblyInput[DomainSection[HeaderOnlyPatch]](**data)
        self.assertEqual([f.details.code for f in PatchSetInvariants.check_core(request)],
            [Code.WORLD_MISMATCH, Code.MISSING_PACK, Code.DUPLICATE_PLAYER, Code.DUPLICATE_PLAYER,
             Code.DUPLICATE_SECTION])

    def test_prepared_order_and_ambiguous_target_are_separate(self):
        for sections, expected in (
            ((section("x", dependencies=("y", "missing")), section("y")),
             [Code.PREPARED_DEPENDENCY_ORDER, Code.MISSING_PREPARED_DEPENDENCY]),
            ((section("x", dependencies=("y", "missing")), section("y"), section("y")),
             [Code.MISSING_PREPARED_DEPENDENCY]),
            ((section("y"), section("x", dependencies=("y",))), []),
        ):
            request = PatchSetAssemblyInput[DomainSection[HeaderOnlyPatch]](**values(sections))
            self.assertEqual([f.details.code for f in PatchSetInvariants.check_prepared_order(request)], expected)
        # A direct result constructor has no prepared-order guarantee.
        result = PatchSet[DomainSection[HeaderOnlyPatch]](**values((section("x", dependencies=("missing",)),)))
        self.assertEqual(len(PatchSetInvariants.check_prepared_order(result)), 1)

    def test_shared_field_schema_and_header_order(self):
        expected = ("format_version", "operation_id", "preparation_fingerprint", "world_uid",
                    "timeline_id", "turn_id", "expected_world", "expected_players", "sections")
        for model in (PatchSetData, PatchSetAssemblyInput, PatchSet):
            self.assertEqual(tuple(model.model_fields), expected)
        self.assertEqual(tuple(PatchData.model_fields), ("header",))
        self.assertEqual(tuple(FakePatch.model_fields), ("header", "target", "change", "prepared"))
        self.assertFalse(PatchSet.__dict__.get("__annotations__", {}))
        self.assertFalse(PatchSetAssemblyInput.__dict__.get("__annotations__", {}))

    def test_published_dependency_is_not_looked_up_in_batch(self):
        from app.dataModel.patch.sections.dependency import PublishedSectionDependency
        from app.dataModel.worldSnapshot.sections.refs import SectionStateRef
        from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
        original = section()
        dependency = PublishedSectionDependency(section_ref=SectionStateRef(
            snapshot=WorldSnapshotRef(world_uid="world", timeline_id="main", snapshot_id="historical"),
            section_key=RegistryKey[PatchSectionRegistry]("absent"), format_version=1))
        published = type(original)(header=SectionHeader(key=original.header.key, format_version=1,
            depends_on=(dependency,)), patches=original.patches)
        request = PatchSetAssemblyInput[DomainSection[HeaderOnlyPatch]](**values((published,)))
        self.assertEqual(PatchSetInvariants.check_prepared_order(request), ())

    def test_detail_records_and_every_index_combination(self):
        publication = values()["expected_world"]
        ref = PatchRef(operation_id="op", section_key=RegistryKey[PatchSectionRegistry]("x"), ordinal=0)
        cases = (
            (WorldMismatchDetails(expected_world_uid="w", actual_world_uid="a"), ()),
            (MissingPackDetails(publication=publication), ()),
            (DuplicatePlayerDetails(player_uid="p"), ("player_index", "related_index")),
            (DuplicateSectionDetails(section_key=RegistryKey[PatchSectionRegistry]("x")), ("section_index", "related_index")),
            (MissingPreparedDependencyDetails(source_section_key=RegistryKey[PatchSectionRegistry]("x"), missing_section_key=RegistryKey[PatchSectionRegistry]("y")),
             ("section_index", "dependency_index")),
            (PreparedDependencyOrderDetails(source_section_key=RegistryKey[PatchSectionRegistry]("x"), dependency_section_key=RegistryKey[PatchSectionRegistry]("y")),
             ("section_index", "dependency_index", "related_index")),
            (PatchOperationMismatchDetails(patch_ref=ref, expected_operation_id="o"), ("section_index", "patch_index")),
            (PatchSectionMismatchDetails(patch_ref=ref, expected_section_key=RegistryKey[PatchSectionRegistry]("y")),
             ("section_index", "patch_index")),
            (DuplicatePatchOrdinalDetails(section_key=RegistryKey[PatchSectionRegistry]("x"), ordinal=0),
             ("section_index", "patch_index", "related_index")),
        )
        names = ("section_index", "patch_index", "dependency_index", "player_index", "related_index")
        exact_fields = (
            ("code", "expected_world_uid", "actual_world_uid"), ("code", "publication"),
            ("code", "player_uid"), ("code", "section_key"),
            ("code", "source_section_key", "missing_section_key"),
            ("code", "source_section_key", "dependency_section_key"),
            ("code", "patch_ref", "expected_operation_id"), ("code", "patch_ref", "expected_section_key"),
            ("code", "section_key", "ordinal"),
        )
        for (details, required), fields in zip(cases, exact_fields):
            self.assertEqual(tuple(type(details).model_fields), fields)
            with self.assertRaises(ValidationError):
                type(details).model_validate({**details.model_dump(), "code": "unknown"})
            for present in itertools.product((False, True), repeat=5):
                indices = {name: 0 if active else None for name, active in zip(names, present)}
                if {name for name, active in zip(names, present) if active} == set(required):
                    fact = PatchSetInvariantViolation(details=details, **indices)
                    self.assertEqual(PatchSetInvariantViolation.model_validate_json(fact.model_dump_json()), fact)
                else:
                    with self.assertRaises(ValidationError):
                        PatchSetInvariantViolation(details=details, **indices)
            for name in names:
                for bad in (True, -1):
                    with self.assertRaises(ValidationError):
                        PatchSetInvariantViolation(details=details, **{name: bad})
            with self.assertRaises(ValidationError):
                type(details).model_validate({**details.model_dump(), "extra": 1})
            with self.assertRaises(ValidationError):
                details.code = Code.MISSING_PACK


if __name__ == "__main__":
    unittest.main()
