"""Unknown substrates and immutable complete source closure."""
from unittest import TestCase

from app.application.encoding.canonicalCodec import encode,decode
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind as Substrate
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import MaterialSupportEntry
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, validate_contracts
from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.support_sources.fixtures import captured,fingerprint


class SupportInputTests(TestCase):
    def test_ref_w_reaches_material_keys_inside_the_new_tuple_projection(self):
        base=captured()
        value=base.model_copy(update={"terrain_entries":(),"materials":(MaterialSupportEntry(key="water",category=base.materials[0].category,substrate=None),)})
        index=WorldRegistryIndex(materials=frozenset({"water"}),terrains=frozenset({str(base.landcover.fallback_terrain)}))
        ctx=ResolveContext(validate_only=True,path_prefix=("support",))
        validate_contracts(SurfaceSupportInput,value.model_dump(),ctx=ctx,references=index)
        bad=value.model_copy(update={"materials":(value.materials[0].model_copy(update={"key":"unknown"}),)})
        with self.assertRaises(UnresolvedModelError) as caught:
            validate_contracts(SurfaceSupportInput,bad.model_dump(),ctx=ResolveContext(validate_only=True,path_prefix=("support",)),references=index)
        self.assertEqual(caught.exception.issues[0].path,("support","materials",0,"key"))
        self.assertEqual(caught.exception.issues[0].code,"REF_W_UNKNOWN")

    def test_canonical_substrate_is_explicit_in_fixture_and_engine_declarations(self):
        for registry in (WorldMaterialRegistry.canonical_defaults(),WorldMaterialRegistry.canonical_engine()):
            for row in registry.root:
                expected=Substrate.ROCK if row.system_material=="stone" else Substrate.LOOSE_SEDIMENT if row.system_material in ("earth","sand","dirt_road") else Substrate.OTHER
                self.assertIs(row.substrate_kind,expected)

    def test_custom_solid_does_not_infer_substrate_from_name_tags_or_hardness(self):
        row=MaterialRegistryEntry(system_material="custom_rock",display_name="rock",material_category="solid",
            tags=["stone","rock"],hardness=5)
        self.assertIsNone(row.substrate_kind)
        value=captured(materials=WorldMaterialRegistry([row]))
        self.assertIsNone(value.materials[0].substrate)
        other=row.model_copy(update={"substrate_kind":Substrate.OTHER})
        self.assertNotEqual(fingerprint(value),fingerprint(captured(materials=WorldMaterialRegistry([other]))))

    def test_full_input_is_immutable_and_round_trips_json_and_production_codec(self):
        value=captured();validate_immutable(value)
        self.assertEqual(type(value).model_validate_json(value.model_dump_json()),value)
        self.assertEqual(decode(encode(value,SURFACE_MANIFEST),SurfaceSupportInput,SURFACE_MANIFEST),value)
        self.assertEqual(fingerprint(value),fingerprint(captured()))
        self.assertNotIn("resolution_mode",type(value).model_fields)

    def test_duplicate_or_unsorted_identity_collections_are_rejected(self):
        value=captured()
        for update in ({"materials":value.materials*2},{"terrain_entries":tuple(reversed(value.terrain_entries))},
                       {"templates":value.templates*2},{"relief_policies":value.relief_policies[:-1]}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                SurfaceSupportInput.model_validate(value.model_copy(update=update),strict=True)

    def test_explicit_presence_bits_survive_canonical_decode(self):
        value=captured();decoded=decode(encode(value,SURFACE_MANIFEST),SurfaceSupportInput,SURFACE_MANIFEST)
        self.assertEqual(tuple(e.hills_authored for e in value.terrain_entries),tuple(e.hills_authored for e in decoded.terrain_entries))
        self.assertEqual(value.landcover.terrain_policy_hills_authored,decoded.landcover.terrain_policy_hills_authored)
