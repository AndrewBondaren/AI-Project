"""Metadata address admission and exact publication-bound subject identity."""
import unittest

from pydantic import TypeAdapter, ValidationError

from app.dataModel.worldPack.preparation.addresses import (
    PackAssemblyAddress, PackChunkMetadataAddress, PackPartAddress,
    PackSettlementAddress, PackSettlementMetadataAddress, PackTileMetadataAddress,
)
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class MetadataSubjectTests(unittest.TestCase):
    def setUp(self):
        self.adapter = TypeAdapter(PackAssemblyAddress)
        self.base = WorldPublicationRef(
            world_uid="world-a", publication_id="publication-a", pack_hash="a" * 64,
            snapshot_head=None, active_timeline_id=None, gameplay_started=False,
        )

    def subject(self, address):
        return PackMetadataSubject(
            base_publication=self.base, address=address, value_fingerprint="b" * 64,
        )

    def test_all_metadata_roles_round_trip(self):
        examples = (
            '{"kind":"header"}',
            '{"kind":"tile","gx":-2,"gy":3}',
            '{"kind":"chunk","gx":-2,"gy":3,"cx":0,"cy":1}',
            '{"kind":"location","location_uid":"loc-a"}',
            '{"kind":"settlement","location_uid":"loc-a"}',
            '{"kind":"region","region_uid":"region-a"}',
        )
        values = []
        for wire in examples:
            with self.subTest(wire=wire):
                address = self.adapter.validate_json(wire)
                subject = self.subject(address)
                restored = PackMetadataSubject.model_validate_json(subject.model_dump_json())
                self.assertEqual(restored, subject)
                self.assertIs(type(restored.address), type(address))
                self.assertEqual(restored.base_publication, self.base)
                values.append(address)
        self.assertEqual(len(set(values)), 6)

    def test_strict_shape_and_flat_coordinates(self):
        for wire in (
            '{"kind":"tile","gx":true,"gy":0}',
            '{"kind":"tile","gx":"1","gy":0}',
            '{"kind":"tile","gx":1.0,"gy":0}',
            '{"kind":"tile","tile":{"gx":0,"gy":0}}',
            '{"kind":"chunk","chunk":{"gx":0,"gy":0,"cx":0,"cy":0}}',
            '{"kind":"chunk","gx":0,"gy":0,"cx":-1,"cy":0}',
            '{"kind":"header","extra":1}',
            '{"kind":"unknown"}',
            '{"kind":"region","region_uid":""}',
            '{"kind":"region","region_uid":" region-a"}',
            '{"kind":"location","location_uid":1}',
        ):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                self.adapter.validate_json(wire)

    def test_payload_instances_do_not_become_metadata(self):
        payload = PackSettlementAddress(kind="settlement", location_uid="loc-a")
        metadata = PackSettlementMetadataAddress(kind="settlement", location_uid="loc-a")
        self.assertNotEqual(payload, metadata)
        with self.assertRaises(ValidationError):
            self.adapter.validate_python(payload)
        with self.assertRaises(ValidationError):
            TypeAdapter(PackPartAddress).validate_python(metadata)

    def test_forged_subject_and_nested_values_are_revalidated(self):
        subject = self.subject(PackTileMetadataAddress(kind="tile", gx=0, gy=0))
        for forged in (
            subject.model_copy(update={"address": subject.address.model_copy(update={"gx": True})}),
            subject.model_copy(update={"base_publication": self.base.model_copy(update={"gameplay_started": 1})}),
            subject.model_copy(update={"value_fingerprint": "bad"}),
        ):
            with self.subTest(forged=forged), self.assertRaises(ValidationError):
                PackMetadataSubject.model_validate(forged)
        with self.assertRaises(ValidationError):
            subject.value_fingerprint = "c" * 64
        with self.assertRaises(ValidationError):
            subject.address.gx = 1
        with self.assertRaises(ValidationError):
            subject.base_publication.publication_id = "other"

    def test_independent_nested_errors_are_preserved(self):
        with self.assertRaises(ValidationError) as caught:
            PackMetadataSubject(
                base_publication=self.base.model_copy(update={"world_uid": ""}),
                address=PackChunkMetadataAddress.model_construct(
                    kind="chunk", gx=True, gy=0, cx=-1, cy=0,
                ),
                value_fingerprint="bad",
            )
        self.assertEqual([error["loc"] for error in caught.exception.errors()], [
            ("base_publication", "world_uid"), ("address", "chunk", "gx"),
            ("address", "chunk", "cx"), ("value_fingerprint",),
        ])

    def test_subject_keeps_publication_identity_and_rejects_extra(self):
        subject = self.subject(PackTileMetadataAddress(kind="tile", gx=0, gy=0))
        other = PackMetadataSubject(
            base_publication=self.base.model_copy(update={"publication_id": "publication-b"}),
            address=subject.address, value_fingerprint=subject.value_fingerprint,
        )
        self.assertNotEqual(subject, other)
        with self.assertRaises(ValidationError):
            PackMetadataSubject(**subject.model_dump(), proof=True)


if __name__ == "__main__":
    unittest.main()
