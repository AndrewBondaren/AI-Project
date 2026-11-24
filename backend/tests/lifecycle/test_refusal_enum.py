import unittest

from pydantic import ValidationError
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.results.refusalKind import LifecycleRefusalKind as Kind
from tests.lifecycle import test_preparation as preparation, test_section as section
from tests.lifecycle.support import nodeContracts as nodes


class RefusalEnumTests(unittest.TestCase):
    def test_categories_roundtrip_and_output_value_identity(self):
        request = preparation.request_for(LifecycleOperation.CREATE, "A")
        pipeline = preparation.PreparationTests().pipeline(LifecycleOperation.CREATE, "A")
        field = pipeline.prepare_create(request.model_copy(update={
            "capture": request.capture.model_copy(update={"entities": ()})}))
        logic = pipeline.prepare_create(request.model_copy(update={
            "capture": request.capture.model_copy(update={"entities": request.capture.entities * 2})}))
        refused = LifecycleSectionPipelineOpenPipeline(binding=section.section_binding()).prepare_section(
            section.mixed_request().model_copy(update={"domain_evidence": ()}))
        for value, kind, output_model in (
            (field, Kind.FIELD_REFUSAL, nodes.CreateNodeOutputA),
            (logic, Kind.LOGIC_REFUSAL, nodes.CreateNodeOutputA),
            (refused, Kind.SECTION_REFUSAL, nodes.SectionNodeOutputAB),
        ):
            with self.subTest(kind=kind):
                model = type(value)
                restored_values = (value, model.model_validate(value.model_dump(), strict=True),
                                   model.model_validate_json(value.model_dump_json(), strict=True))
                self.assertEqual(value.model_dump(mode="json")["kind"], kind.value)
                for restored in restored_values:
                    self.assertIs(type(restored.kind), Kind)
                    self.assertIs(restored.kind, kind)
                    self.assertEqual(restored.issues, value.issues)
                    output = output_model(value=restored)
                    self.assertIs(type(output.value), model)
                    self.assertIs(output_model.model_validate(output).value.kind, kind)
                for wrong in Kind:
                    if wrong is kind:
                        continue
                    with self.assertRaises(ValidationError):
                        model(**{**dict(value), "kind": wrong})
                with self.assertRaises(ValidationError):
                    model(**{**dict(value), "kind": "unknown_refusal"})
                with self.assertRaises(ValidationError):
                    model(issues=())
