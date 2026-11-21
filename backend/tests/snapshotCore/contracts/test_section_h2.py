"""Closed local-to-composition transport; output faults stay outside business refusals."""
import asyncio
import unittest

from pydantic import BaseModel, ConfigDict, model_validator
from app.application.patch.errors import SectionHandlerContractError
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionApplyReceipt, SectionRefused
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind as Kind
from tests.snapshotCore.contracts import test_registry
from tests.snapshotCore.support.fakeSection import FakeTargetIssue, FakeSectionRefused, FakeSectionHandler
from tests.snapshotCore.support.diagnostics import target_issue


class OtherIssue(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    reason: str


class CompositionRefused(SectionRefused[FakeTargetIssue | OtherIssue]):
    pass


class OtherRefused(SectionRefused[OtherIssue]):
    pass


class H2Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_registry.SectionRegistryTests()
        self.fixture.setUp()
        self.registry = SectionRegistry(CompositionRefused)
        self.registry.register(self.fixture.contract, self.fixture.handler, self.fixture.section_codec)
        self.bound = self.registry.resolve(self.fixture.section)

    def run_output(self, value, stage="validate"):
        async def returned(section, context):
            return value
        setattr(self.fixture.handler, stage, returned)
        return self.fixture._complete(getattr(self.bound, stage)(self.fixture.section, self.fixture.context))

    def test_local_carrier_preserves_exact_diagnostics_paths_and_order(self):
        issues = (target_issue("first"), target_issue("second"))
        local = FakeSectionRefused(category=Kind.REJECTED, diagnostics=issues)
        for stage in ("validate", "apply"):
            result = self.run_output(local, stage)
            self.assertIs(type(result), CompositionRefused)
            self.assertEqual(result.category, local.category)
            self.assertEqual(result.diagnostics, issues)
            self.assertEqual(tuple(map(type, result.diagnostics)), (FakeTargetIssue,) * 2)
        self.assertEqual(self.registry.diagnostic_types, frozenset({FakeTargetIssue, OtherIssue}))
        self.assertIs(self.registry.refusal_model, CompositionRefused)

    def test_invalid_output_is_contract_fault_with_cause(self):
        class ChildAccepted(SectionAccepted):
            pass
        valid = FakeSectionRefused(category=Kind.REJECTED, diagnostics=(target_issue("x"),))
        receipt = SectionApplyReceipt(section_key=self.fixture.key, states=(), history=(), changed=())
        for stage, values in (
            ("validate", (None, receipt, ChildAccepted(), valid.model_copy(update={"diagnostics": ()}),
                          valid.model_copy(update={"diagnostics": (OtherIssue(reason="foreign"),)}),
                          FakeSectionRefused.model_construct(),
                          CompositionRefused(category=Kind.REJECTED, diagnostics=valid.diagnostics))),
            ("apply", (SectionAccepted(), receipt.model_copy(update={"changed": ("bad",)}))),
        ):
            for value in values:
                with self.subTest(stage=stage, value=value), self.assertRaises(SectionHandlerContractError) as caught:
                    self.run_output(value, stage)
                self.assertIsNotNone(caught.exception.__cause__)

    def test_handler_exceptions_and_cancellation_are_not_wrapped(self):
        for error in (ValueError("domain failure"), asyncio.CancelledError()):
            async def failed(section, context):
                raise error
            self.fixture.handler.validate = failed
            with self.assertRaises(type(error)) as caught:
                self.fixture._complete(self.bound.validate(self.fixture.section, self.fixture.context))
            self.assertIs(caught.exception, error)

    def test_configuration_requires_named_roster_and_local_subset(self):
        class ExtraField(FakeSectionRefused):
            detail: str

        class Weakened(FakeSectionRefused):
            diagnostics: tuple[FakeTargetIssue, ...]

        class SemanticOverride(FakeSectionRefused):
            @model_validator(mode="after")
            def refusal_category(self):
                return self

        for model in (SectionRefused, SectionRefused[FakeTargetIssue], SectionRefused[BaseModel],
                      ExtraField, Weakened, SemanticOverride):
            with self.assertRaises(TypeError):
                SectionRegistry(model)
        registry = SectionRegistry(OtherRefused)
        with self.assertRaises(ValueError):
            registry.register(self.fixture.contract, self.fixture.handler, self.fixture.section_codec)
        with self.assertRaises(ValueError):
            registry.require(self.fixture.key)
