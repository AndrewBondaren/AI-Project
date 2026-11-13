"""Structural coverage admission, without pretending to verify producer evidence."""
import unittest

from pydantic import ValidationError

from app.dataModel.worldPack.preparation.addresses import PackChunkAddress
from app.dataModel.worldPack.preparation.coverage import (
    PackChunkCoverageEntry, PackChunkMaterialized, PackChunkWithoutPayload,
)


class PreparationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.address = PackChunkAddress(kind="wilderness_chunk", gx=-1, gy=2, cx=0, cy=1)

    def test_distinct_outcomes_round_trip(self):
        for result in (
            PackChunkMaterialized(kind="materialized", outputs=(self.address,)),
            PackChunkWithoutPayload(kind="without_payload"),
        ):
            with self.subTest(result=result):
                entry = PackChunkCoverageEntry(address=self.address, result=result)
                restored = PackChunkCoverageEntry.model_validate_json(entry.model_dump_json())
                self.assertEqual(entry, restored)
                self.assertIs(type(restored.result), type(result))

    def test_materialized_requires_nonempty_immutable_outputs(self):
        for outputs in ((), [], [self.address]):
            with self.subTest(outputs=outputs), self.assertRaises(ValidationError):
                PackChunkMaterialized(kind="materialized", outputs=outputs)
        with self.assertRaises(ValidationError):
            PackChunkMaterialized(kind="materialized")
        with self.assertRaises(ValidationError):
            PackChunkWithoutPayload(kind="without_payload", outputs=())

    def test_nested_forgery_is_rejected(self):
        valid = PackChunkMaterialized(kind="materialized", outputs=(self.address,))
        for result in (
            valid.model_copy(update={"outputs": ()}),
            valid.model_copy(update={"outputs": (self.address.model_copy(update={"cx": True}),)}),
        ):
            with self.subTest(result=result), self.assertRaises(ValidationError):
                PackChunkCoverageEntry(address=self.address, result=result)
        entry = PackChunkCoverageEntry(address=self.address, result=valid)
        with self.assertRaises(ValidationError):
            entry.result = PackChunkWithoutPayload(kind="without_payload")

    def test_independent_nested_failures_are_preserved(self):
        with self.assertRaises(ValidationError) as caught:
            PackChunkCoverageEntry(
                address=self.address.model_copy(update={"cx": -1}),
                result=PackChunkMaterialized.model_construct(kind="materialized", outputs=()),
            )
        self.assertEqual(
            [error["loc"] for error in caught.exception.errors()],
            [("address", "cx"), ("result", "materialized", "outputs")],
        )


if __name__ == "__main__":
    unittest.main()
