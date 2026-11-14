"""POJO checks only: fixtures are not finalized captures or verified closure."""

import unittest

from pydantic import ValidationError

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDescriptor import (
    SourceCollectionOrder, SourceDescriptorCategory as Category,
    SourceDescriptorDefinition, SourceDescriptorRegistry, SourceDescriptorScope as Scope,
    SourceMemberKey, SourceMemberKeyKind as KeyKind,
)
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceObjectId import (
    EntityObjectId, LibraryMemberId, RegistryMemberId, SourceCollectionId, SourceSettingsId,
)
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceProofGroups import SourceProofGroupsInput, SourceProofGroupsResult
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.sourceVersioning.sourceProofResult import SourceProofResult
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef
from app.dataModel.validation.immutableValue import validate_immutable


def witness(digest="a", world="world"):
    return SourceCaptureRef(world_uid=world, artifact=ArtifactRef(
        kind=ArtifactKind.SQL_ROWS, format_key=RegistryKey("source.capture-witness"),
        format_version=1, content_hash=digest * 64, nbytes=123, row_count=1,
    ))


def revision(seq=1):
    return SourceRevision(seq=seq, content_hash="b" * 64)


def member(world="world"):
    return RegistryMemberId(kind=Category.REGISTRY_MEMBER, world_uid=world,
                            descriptor=RegistryKey("terrain/member"), member_key=SourceMemberKey("stone"))


def usage(seq=1, capture=None):
    return SourceCaptureUsage(capture=capture or witness(), dependencies=SourceDependencySet(
        objects=(SourceVersionRef(object_id=member(), revision=revision(seq)),), collections=(),
    ))


def proof(uses=None):
    return SourceDurableProof(schema_version=1, world_uid="world", uses=(usage(),) if uses is None else uses)


def definition(key="terrain/member", **overrides):
    fields = dict(key=RegistryKey(key), category=Category.REGISTRY_MEMBER, scope=Scope.WORLD,
                  key_kind=KeyKind.TEXT, collection_order=None, member_descriptors=())
    fields.update(overrides)
    return SourceDescriptorDefinition(**fields)


class SourceValueTests(unittest.TestCase):
    def test_full_graph_json_roundtrip_and_deep_immutability(self):
        identities = (
            member(),
            LibraryMemberId(kind=Category.LIBRARY_MEMBER, descriptor=RegistryKey("library"),
                            template_uid="12345678-1234-1234-1234-123456789abc"),
            EntityObjectId(kind=Category.ENTITY, world_uid="world", descriptor=RegistryKey("entity"), entity_uid="e1"),
            SourceSettingsId(kind=Category.SETTINGS, world_uid="world", descriptor=RegistryKey("settings")),
        )
        collection = SourceCollectionVersionRef(collection_id=SourceCollectionId(
            kind=Category.COLLECTION, world_uid="world", descriptor=RegistryKey("terrain/membership")),
            revision=revision())
        use = SourceCaptureUsage(capture=witness(), dependencies=SourceDependencySet(
            objects=tuple(SourceVersionRef(object_id=i, revision=revision()) for i in identities),
            collections=(collection,)))
        value = SourceProofGroupsResult(admission=SourceProofResult(proof=proof((use,)), durable_refs=(witness().artifact,)),
                                       selections=(SourceProofSelection(proof_fingerprint="c" * 64, dependency_indices=(0, 4)),))
        restored = SourceProofGroupsResult.model_validate_json(value.model_dump_json())
        self.assertEqual(restored, value)
        self.assertIs(type(restored.admission.proof.uses[0].dependencies.objects[0].object_id.member_key), SourceMemberKey)
        validate_immutable(restored)
        for obj, field, replacement in (
            (value, "selections", ()), (value.admission.proof, "uses", ()),
            (use.dependencies, "objects", ()), (identities[0], "member_key", SourceMemberKey("sand")),
            (witness().artifact, "nbytes", 0), (collection.revision, "seq", 2),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                setattr(obj, field, replacement)

    def test_strict_scalars_and_aggregated_structural_errors(self):
        for seq in (True, 0, -1, 1.0, "1"):
            with self.subTest(seq=seq), self.assertRaises(ValidationError):
                SourceRevision.model_validate(dict(seq=seq, content_hash="b" * 64))
        with self.assertRaises(ValidationError) as caught:
            SourceRevision.model_validate(dict(seq=True, content_hash="bad", extra=1))
        self.assertEqual([error["loc"] for error in caught.exception.errors()],
                         [("seq",), ("content_hash",), ("extra",)])
        for version in (True, 1.0, "1", 2):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                SourceDurableProof.model_validate(dict(schema_version=version, world_uid="world", uses=()))

    def test_required_fields_and_extra(self):
        for fields in ({"world_uid": "world", "uses": ()},
                       {"schema_version": 1, "uses": ()},
                       {"schema_version": 1, "world_uid": "world", "uses": (), "label": "x"}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                SourceDurableProof.model_validate(fields)
        fields = definition().model_dump()
        del fields["collection_order"]
        with self.assertRaises(ValidationError):
            SourceDescriptorDefinition.model_validate(fields)

    def test_tuple_strictness(self):
        with self.assertRaises(ValidationError):
            SourceProofInput.model_validate(dict(world_uid="world", uses=[usage()]))
        with self.assertRaises(ValidationError):
            SourceDependencySet.model_validate(dict(objects=[], collections=()))

    def test_revalidate_forged_nested_revision(self):
        bad = SourceRevision.model_construct(seq=True, content_hash="b" * 64)
        ref = SourceVersionRef.model_construct(object_id=member(), revision=bad)
        deps = SourceDependencySet.model_construct(objects=(ref,), collections=())
        forged = SourceCaptureUsage.model_construct(capture=witness(), dependencies=deps)
        with self.assertRaises(ValidationError):
            SourceProofInput(world_uid="world", uses=(forged,))

    def test_revalidate_missing_extra_and_mutable_nested_instances(self):
        cases = [SourceDependencySet.model_construct(objects=[], collections=()),
                 SourceDependencySet.model_construct(objects=())]
        extra = SourceDependencySet.model_construct(objects=(), collections=())
        object.__setattr__(extra, "__pydantic_extra__", {"unapproved": []})
        cases.append(extra)
        for deps in cases:
            with self.subTest(deps=deps), self.assertRaises(ValidationError):
                SourceCaptureUsage(capture=witness(), dependencies=deps)
        artifact = witness().artifact.model_copy()
        object.__delattr__(artifact, "row_count")
        with self.assertRaises(ValidationError):
            SourceCaptureRef(world_uid="world", artifact=artifact)

    def test_identity_union_distinguishes_collection(self):
        collection = SourceCollectionId(kind=Category.COLLECTION, world_uid="world", descriptor=RegistryKey("members"))
        with self.assertRaises(ValidationError):
            SourceVersionRef.model_validate(dict(object_id=collection, revision=revision()))
        with self.assertRaises(ValidationError):
            SourceCollectionVersionRef.model_validate(dict(collection_id=member(), revision=revision()))

    def test_identity_discriminators_are_required_and_strict(self):
        data = member().model_dump()
        del data["kind"]
        with self.assertRaises(ValidationError):
            RegistryMemberId.model_validate(data)
        data["kind"] = "registry_member"
        with self.assertRaises(ValidationError):
            RegistryMemberId.model_validate(data)
        self.assertEqual(RegistryMemberId.model_validate_json(member().model_dump_json()), member())

    def test_nominal_key_no_coercion_or_normalization(self):
        for key in ("", 1, b"stone", SourceMemberKey("")):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                RegistryMemberId.model_validate(dict(kind=Category.REGISTRY_MEMBER, world_uid="world",
                                                     descriptor=RegistryKey("terrain"), member_key=key))
        data = member().model_dump()
        data["member_key"] = " Stone "
        self.assertEqual(RegistryMemberId.model_validate(data).member_key, " Stone ")
        data["descriptor"] = RegistryKey("")
        with self.assertRaises(ValidationError):
            RegistryMemberId.model_validate(data)

    def test_library_uuid_is_canonical_entity_uid_is_not_uuid(self):
        for uid in ("name", "12345678123412341234123456789abc", "12345678-1234-1234-1234-123456789ABC"):
            with self.subTest(uid=uid), self.assertRaises(ValidationError):
                LibraryMemberId(kind=Category.LIBRARY_MEMBER, descriptor=RegistryKey("library"), template_uid=uid)
        EntityObjectId(kind=Category.ENTITY, world_uid="world", descriptor=RegistryKey("entity"), entity_uid="named-entity")

    def test_capture_shape(self):
        fields = witness().artifact.model_dump()
        for change in (dict(format_key=RegistryKey("source.capture")), dict(format_version=2),
                       dict(row_count=2), dict(kind=ArtifactKind.BLOB, row_count=None)):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                SourceCaptureRef(world_uid="world", artifact=ArtifactRef.model_validate(fields | change))

    def test_world_relations(self):
        with self.assertRaises(ValidationError):
            SourceCaptureUsage(capture=witness(), dependencies=SourceDependencySet(
                objects=(SourceVersionRef(object_id=member("other"), revision=revision()),), collections=()))
        collection = SourceCollectionId(kind=Category.COLLECTION, world_uid="other", descriptor=RegistryKey("members"))
        with self.assertRaises(ValidationError):
            SourceCaptureUsage(capture=witness(), dependencies=SourceDependencySet(objects=(), collections=(
                SourceCollectionVersionRef(collection_id=collection, revision=revision()),)))
        with self.assertRaises(ValidationError):
            SourceProofInput(world_uid="other", uses=(usage(),))
        with self.assertRaises(ValidationError):
            SourceDurableProof(schema_version=1, world_uid="other", uses=(usage(),))

    def test_declared_duplicates_preserved_persisted_duplicates_rejected(self):
        use = usage()
        duplicate = SourceCaptureUsage(capture=use.capture, dependencies=SourceDependencySet(
            objects=use.dependencies.objects * 2, collections=()))
        request = SourceProofInput(world_uid="world", uses=(duplicate, duplicate))
        self.assertEqual(len(request.uses), 2)
        self.assertEqual(len(request.uses[0].dependencies.objects), 2)
        for uses in ((duplicate,), (use, use)):
            with self.subTest(uses=uses), self.assertRaises(ValidationError):
                proof(uses)

    def test_historical_revisions_across_captures(self):
        first, second = usage(), usage(2, witness("d"))
        self.assertEqual(len(proof((first, second)).uses), 2)
        conflict = SourceCaptureUsage(capture=first.capture, dependencies=SourceDependencySet(
            objects=first.dependencies.objects + second.dependencies.objects, collections=()))
        with self.assertRaises(ValidationError):
            proof((conflict,))

    def test_empty_semantics(self):
        empty_use = SourceCaptureUsage(capture=witness(), dependencies=SourceDependencySet(objects=(), collections=()))
        SourceProofInput(world_uid="world", uses=(empty_use,))
        with self.assertRaises(ValidationError):
            proof((empty_use,))
        SourceProofResult(proof=proof(()), durable_refs=())
        with self.assertRaises(ValidationError):
            SourceProofResult(proof=proof(()), durable_refs=(witness().artifact,))
        with self.assertRaises(ValidationError):
            SourceProofResult(proof=proof(), durable_refs=())

    def test_duplicate_refs_rejected(self):
        with self.assertRaises(ValidationError):
            SourceProofResult(proof=proof(), durable_refs=(witness().artifact,) * 2)

    def test_selections_strict_order_unique(self):
        for indices in ((True,), (-1,), (1.0,), ("1",), (1, 1), (2, 1)):
            with self.subTest(indices=indices), self.assertRaises(ValidationError):
                SourceProofSelection.model_validate(dict(proof_fingerprint="a" * 64, dependency_indices=indices))
        SourceProofSelection(proof_fingerprint="a" * 64, dependency_indices=())
        SourceProofSelection(proof_fingerprint="a" * 64, dependency_indices=(0, 2))

    def test_groups_nonempty_same_world_order_and_repeated_selections(self):
        one = SourceProofInput(world_uid="world", uses=(usage(),))
        empty = SourceProofInput(world_uid="world", uses=())
        groups = SourceProofGroupsInput(groups=(one, empty, one))
        self.assertEqual(groups.groups, (one, empty, one))
        for values in ((), (one, SourceProofInput(world_uid="other", uses=()))):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                SourceProofGroupsInput(groups=values)
        admission = SourceProofResult(proof=proof(), durable_refs=(witness().artifact,))
        selection = SourceProofSelection(proof_fingerprint="a" * 64, dependency_indices=(0,))
        SourceProofGroupsResult(admission=admission, selections=(selection, selection))
        with self.assertRaises(ValidationError):
            SourceProofGroupsResult(admission=admission, selections=())

    def test_descriptor_registry_members(self):
        item = definition()
        members = definition("terrain/membership", category=Category.COLLECTION, key_kind=KeyKind.NONE,
                             collection_order=SourceCollectionOrder.SET, member_descriptors=(item.key,))
        registry = SourceDescriptorRegistry(entries=(item, members))
        self.assertEqual(SourceDescriptorRegistry.model_validate_json(registry.model_dump_json()), registry)
        for entries in ((item, item), (members,)):
            with self.subTest(entries=entries), self.assertRaises(ValidationError):
                SourceDescriptorRegistry(entries=entries)
        self_ref = definition("self", category=Category.COLLECTION, key_kind=KeyKind.NONE,
                              collection_order=SourceCollectionOrder.SEQUENCE, member_descriptors=(RegistryKey("self"),))
        with self.assertRaises(ValidationError):
            SourceDescriptorRegistry(entries=(self_ref,))

    def test_descriptor_category_matrix(self):
        valid = (
            dict(category=Category.REGISTRY_MEMBER, scope=Scope.WORLD, key_kind=KeyKind.UUID),
            dict(category=Category.LIBRARY_MEMBER, scope=Scope.GLOBAL, key_kind=KeyKind.UUID),
            dict(category=Category.ENTITY, scope=Scope.WORLD, key_kind=KeyKind.NONE),
            dict(category=Category.SETTINGS, scope=Scope.WORLD, key_kind=KeyKind.NONE),
        )
        for fields in valid:
            definition(**fields)
        invalid = (
            dict(scope=Scope.GLOBAL), dict(key_kind=KeyKind.NONE),
            dict(category=Category.LIBRARY_MEMBER), dict(category=Category.ENTITY),
            dict(collection_order=SourceCollectionOrder.SET),
            dict(member_descriptors=(RegistryKey("x"),)),
            dict(category=Category.COLLECTION, key_kind=KeyKind.NONE),
            dict(category=Category.COLLECTION, key_kind=KeyKind.NONE, collection_order=SourceCollectionOrder.SET,
                 member_descriptors=(RegistryKey("x"), RegistryKey("x"))),
        )
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                definition(**fields)


if __name__ == "__main__":
    unittest.main()
