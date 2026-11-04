"""In-process Spatial contracts, without storage or a domain solver."""
import asyncio
import unittest
from uuid import UUID

from pydantic import ValidationError

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.planning.identity.planKey import (
    AlgorithmVersion, InputFingerprint, OutputFingerprint, PlanKey, SchemaVersion, WorldPlanScope,
)
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ
from app.dataModel.spatial.query.window import SpatialBox, SpatialWindow
from app.dataModel.spatial.read.failure import SpatialReadError, SpatialReadFailure
from app.dataModel.spatial.read.reader import SpatialFieldReader
from app.dataModel.spatial.read.request import SpatialReadMode, SpatialReadRequest
from app.dataModel.spatial.read.result import SpatialReadResult, SpatialSlice
from app.dataModel.spatial.readFailureReason import SpatialReadFailureReason
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


def bootstrap(world: str = "w") -> PlanRef:
    key = PlanKey(world_uid=world, scope=WorldPlanScope(), contract_id=RegistryKey("water"),
                  schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1),
                  input_fingerprint=InputFingerprint(b"i" * 32))
    return PlanRef(key=key, output_fingerprint=OutputFingerprint(b"o" * 32))


def box(x: int) -> SpatialBox:
    return SpatialBox(x0=FineX(x), x1=FineX(x + 1), y0=FineY(0), y1=FineY(1), z0=FineZ(-1), z1=FineZ(1))


class FixtureReader:
    def __init__(self, source: PlanRef):
        self.source = source

    async def read_window(self, request: SpatialReadRequest) -> SpatialReadResult[int]:
        if request.revision != self.source:
            error = SpatialReadError(reason=SpatialReadFailureReason.REVISION_MISMATCH,
                                     issue=FieldPathError(path=("revision",), message="unexpected revision"))
            return SpatialReadFailure(request=request, errors=(error,))
        return SpatialSlice[int](request=request, payload=0, source_refs=(self.source,), issues=())


class SpatialReadContractTest(unittest.TestCase):
    def setUp(self):
        self.source = bootstrap()
        self.bounds = WorldBounds(x_min=-2, x_max=1, y_min=-2, y_max=1)
        self.frame = WorldTopology(mode=WorldTopologyMode.SPHERE, bounds=self.bounds)
        self.window = SpatialWindow(space=CoordinateSpace.WORLD_FINE_GRID, topology=self.frame, boxes=(box(-1), box(0)))
        self.request = SpatialReadRequest(request_id=UUID(int=1), window=self.window,
                                          revision=self.source, mode=SpatialReadMode.REQUIRED)
        self.issue = FieldPathError(path=("a",), message="unknown")
        self.blob = ArtifactRef(kind=ArtifactKind.BLOB, format_key=RegistryKey("root"), format_version=1,
                                content_hash="a" * 64, nbytes=4)

    def test_protocol_outcomes(self):
        reader: SpatialFieldReader[int] = FixtureReader(self.source)
        success = asyncio.run(reader.read_window(self.request))
        self.assertIsInstance(success, SpatialSlice)
        self.assertEqual(success.request, self.request)
        other = self.request.model_copy(update={"revision": bootstrap("other")})
        failure = asyncio.run(reader.read_window(other))
        self.assertIsInstance(failure, SpatialReadFailure)
        self.assertEqual(failure.request, other)

    def test_revalidate_nested_window(self):
        first, second = self.window.boxes
        for boxes in ((), (second, first), (first, first), (first.model_copy(update={"x1": 1}), second),
                      (box(2),), (first.model_copy(update={"z1": -1}),),
                      (first.model_copy(update={"x0": True}),)):
            with self.subTest(boxes=boxes), self.assertRaises(ValidationError):
                SpatialReadRequest.model_validate(self.request.model_copy(
                    update={"window": self.window.model_copy(update={"boxes": boxes})}))

    def test_malformed_frame(self):
        for frame in (self.frame.model_dump(), self.frame.model_copy(update={"mode": "sphere"}),
                      self.frame.model_copy(update={"bounds": self.bounds.model_copy(update={"x_max": 0})}),
                      self.frame.model_copy(update={"bounds": self.bounds.model_copy(update={"x_min": 0.5})})):
            with self.subTest(frame=frame), self.assertRaises(ValidationError):
                SpatialWindow.model_validate(self.window.model_copy(update={"topology": frame}))

    def test_discriminants(self):
        with self.assertRaises(ValidationError):
            SpatialWindow.model_validate(self.window.model_copy(update={"space": self.window.space.value}))
        for update in ({"revision": self.source.model_dump()}, {"mode": "required"},
                       {"revision": self.source.model_copy(update={"output_fingerprint": b"short"})}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                SpatialReadRequest.model_validate(self.request.model_copy(update=update))

    def test_provenance_and_issues(self):
        valid = SpatialSlice[int](request=self.request, payload=1, source_refs=(self.source,), issues=())
        for refs in ((), (self.source, self.source), (self.source, bootstrap("other")), (self.blob,),
                     (self.source.model_dump(),)):
            with self.subTest(refs=refs), self.assertRaises(ValidationError):
                SpatialSlice[int].model_validate(valid.model_copy(update={"source_refs": refs}))
        with self.assertRaises(ValidationError):
            SpatialSlice[int].model_validate(valid.model_copy(update={"issues": (self.issue,)}))
        preview = self.request.model_copy(update={"mode": SpatialReadMode.PREVIEW})
        self.assertEqual(SpatialSlice[int](request=preview, payload=0, source_refs=(self.source,),
                                           issues=(self.issue,)).issues, (self.issue,))

    def test_pack_revision(self):
        pin = WorldPublicationRef(world_uid="w", publication_id="p", pack_hash="1" * 64,
                                  snapshot_head=None, active_timeline_id=None, gameplay_started=False)
        request = self.request.model_copy(update={"revision": pin})
        valid = SpatialSlice[int](request=request, payload=0, source_refs=(self.blob,), issues=())
        with self.assertRaises(ValidationError):
            SpatialSlice[int].model_validate(valid.model_copy(update={"source_refs": (self.source,)}))
        unpinned = request.model_copy(update={"revision": pin.model_copy(update={"pack_hash": None})})
        with self.assertRaises(ValidationError):
            SpatialSlice[int].model_validate(valid.model_copy(update={"request": unpinned}))

    def test_all_failure_diagnostics(self):
        errors = tuple(SpatialReadError(reason=SpatialReadFailureReason.SOURCE_MISSING,
                                        issue=FieldPathError(path=(i,), message="missing")) for i in range(2))
        errors += (SpatialReadError(reason=SpatialReadFailureReason.SOURCE_CORRUPT, issue=self.issue),)
        failure = SpatialReadFailure(request=self.request, errors=errors)
        self.assertEqual(failure.errors, errors)
        with self.assertRaises(ValidationError):
            SpatialReadFailure(request=self.request, errors=())
        with self.assertRaises(ValidationError):
            SpatialReadFailure.model_validate(dict(request=self.request, errors=errors, payload=1))
