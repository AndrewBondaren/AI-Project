import unittest
from pydantic import ValidationError
from app.dataModel.lifecycle.operations.kind import LifecycleOperation as Op
from app.encoding.canonicalCodec import CanonicalCodec, encode, decode, content_digest, CanonicalEncodingError
from app.application.lifecycle.publication.sectionCodec import LifecycleSectionCodec
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline
from app.application.patch.contracts.sectionHandler import SectionContract
from tests.lifecycle.support.manifest import MOCK_NATIVE_MANIFEST
from tests.lifecycle.support import mixedContracts as m, domainSections as d
from tests.lifecycle.support.subjectCodec import MockSubjectCodec
from tests.lifecycle.test_section import section_binding, mixed_request
from tests.lifecycle.test_apply_predicates import subject_section


class EffectEnumTests(unittest.TestCase):
    def test_exact_enum_and_replacement_string_rejection(self):
        ref = m.RefA(kind="test_entity_a", entity_uid="one")
        for operation in (Op.CREATE, Op.END, Op.REACTIVATE):
            effect = m.EffectA(entity=ref, effect=operation, reason_action_uid="action")
            restored = decode(encode(effect, MOCK_NATIVE_MANIFEST), m.EffectA, MOCK_NATIVE_MANIFEST)
            self.assertIs(restored.effect, operation)
        for invalid in (Op.REPLACEMENT, "create", "end", "reactivate"):
            with self.assertRaises(ValidationError):
                m.EffectA(entity=ref, effect=invalid, reason_action_uid="action")

    def test_old_canonical_string_record_is_not_coerced_to_enum(self):
        effect = m.EffectA(entity=m.RefA(kind="test_entity_a", entity_uid="one"),
                           effect=Op.CREATE, reason_action_uid="action")
        codec = CanonicalCodec(MOCK_NATIVE_MANIFEST)
        type_id = next(e.type_id for e in MOCK_NATIVE_MANIFEST.entries if e.python_type is m.EffectA)
        # Historical RECORD envelope with the old string-valued effect field.
        old_record = (type_id, tuple((name, effect.effect.value if name == "effect" else getattr(effect, name))
                                    for name in m.EffectA.model_fields))
        old_bytes = codec._tlv(7, codec.encode(old_record))
        self.assertNotEqual(content_digest(old_bytes), content_digest(codec.encode(effect)))
        with self.assertRaises((CanonicalEncodingError, ValidationError)):
            decode(old_bytes, m.EffectA, MOCK_NATIVE_MANIFEST)

    def test_section_v2_and_distinct_patch_versions(self):
        binding = section_binding()
        section = LifecycleSectionPipelineOpenPipeline(binding=binding).prepare_section(mixed_request())
        codec = LifecycleSectionCodec(binding.section_contract)
        self.assertEqual(section.header.format_version, 2)
        self.assertTrue(all(p.header.format_version == 1 for p in section.patches))
        self.assertIs(codec.decode(codec.encode(section), 2).domain_evidence[0].effect.effect,
                      section.domain_evidence[0].effect.effect)
        with self.assertRaises(ValueError):
            codec.decode(codec.encode(section), 1)
        for suffix, model in (("A", d.TestDomainSectionA), ("B", d.TestDomainSectionB)):
            subject = subject_section(suffix)
            subject_codec = MockSubjectCodec(SectionContract(key=subject.header.key,
                section_model=model, supported_versions=frozenset({2}), manifest=MOCK_NATIVE_MANIFEST))
            restored = subject_codec.decode(subject_codec.encode(subject), 2)
            self.assertIs(restored.patches[0].effects[0].effect, Op.CREATE)
            with self.assertRaises(ValueError):
                subject_codec.decode(subject_codec.encode(subject), 1)
            old_patch = subject.patches[0].model_copy(update={
                "header": subject.patches[0].header.model_copy(update={"format_version": 1})})
            with self.assertRaises(ValueError):
                subject_codec.encode(subject.model_copy(update={"patches": (old_patch, *subject.patches[1:])}))
