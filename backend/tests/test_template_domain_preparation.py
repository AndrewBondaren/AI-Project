"""A3: prepared bodies, shared ref declarations and scoped graph facts."""

from copy import deepcopy
import unittest

from app.application.jsonValidation.types import ReferenceIssueReason
from app.application.worldData.libraryPacks.domainAdapters.bodyPreparation import TemplatePreparationError
from app.application.worldData.libraryPacks.domainAdapters.building import BuildingBodyPreparation
from app.application.worldData.libraryPacks.domainAdapters.plot import PlotBodyPreparation
from app.application.worldData.libraryPacks.domainAdapters.structure import StructureBodyPreparation
from app.application.worldData.libraryPacks.lifecycleContracts import CatalogSnapshot
from app.application.worldData.libraryPacks.templateGraphValidation import template_graph_issues
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.ids import LibraryKind, runtime_uid


def member(kind, local_uid):
    return LibraryPackMemberRow(runtime_uid(), runtime_uid(), kind.value, local_uid)


def building(structure, **overrides):
    return {'system_name': 'house', 'display_name': 'House', 'structure': structure, **overrides}


def plot(structure, **overrides):
    return {'system_name': 'plot', 'display_name': 'Plot',
            'main_building': {'structure': structure}, **overrides}


def graph(*entries):
    return CatalogSnapshot({m.template_uid: m for m, _ in entries},
                           {m.template_uid: body for m, body in entries}, {})


class PreparationTests(unittest.TestCase):
    def test_full_building_defaults_and_explicit_overrides(self):
        uid, structure = runtime_uid(), runtime_uid()
        preparer = BuildingBodyPreparation()
        default = preparer.prepare_body(building(structure), local_uid='house', template_uid=uid)
        overridden = preparer.prepare_body(building(structure, foundation_depth=0,
            roof_type='flat', porch_has_roof=False, roof_material=None),
            local_uid='house', template_uid=uid)
        self.assertEqual(default.foundation_type, 'slab')
        self.assertEqual(overridden.foundation_depth, 0)
        self.assertFalse(overridden.porch_has_roof)
        self.assertIsNone(overridden.roof_material)
        self.assertEqual(overridden.roof_type, 'flat')

    def test_invalid_explicit_values_are_aggregated_without_default_substitution(self):
        with self.assertRaises(TemplatePreparationError) as caught:
            BuildingBodyPreparation().prepare_body(building(runtime_uid(), foundation_depth=-1,
                roof_type=None), local_uid='house', template_uid=runtime_uid())
        self.assertEqual({issue.path[-1] for issue in caught.exception.issues},
                         {'foundation_depth', 'roof_type'})

    def test_missing_structure_name_or_mismatched_local_key_rejects(self):
        body = building(runtime_uid())
        for raw in ({k: v for k, v in body.items() if k != 'structure'},
                    {**body, 'system_name': 'other'}, {**body, 'structure': 'house_geometry'}):
            with self.subTest(raw=raw), self.assertRaises(TemplatePreparationError):
                BuildingBodyPreparation().prepare_body(raw, local_uid='house', template_uid=runtime_uid())

    def test_template_uid_is_not_minted_or_inferred_from_local_key(self):
        with self.assertRaises(TemplatePreparationError):
            BuildingBodyPreparation().prepare_body(building(runtime_uid()), local_uid='house',
                                                    template_uid='house')

    def test_structure_model_a_fills_only_missing_identity(self):
        uid = runtime_uid()
        preparer = StructureBodyPreparation()
        body = preparer.prepare_body({'display_name': 'Geometry'}, local_uid='geometry', template_uid=uid)
        self.assertEqual(body.system_name, uid)
        for identity in (None, runtime_uid()):
            with self.subTest(identity=identity), self.assertRaises(TemplatePreparationError):
                preparer.prepare_body({'display_name': 'Geometry', 'system_name': identity},
                                      local_uid='geometry', template_uid=uid)

    def test_structure_geometry_model_invariants_are_not_bypassed(self):
        with self.assertRaises(TemplatePreparationError):
            StructureBodyPreparation().prepare_body({'display_name': 'Geometry',
                'levels': [{'z_offset': 0, 'rooms': [{'room_id': 'hall',
                    'entry_point': {'wall': 'not-a-wall'}}]}]},
                local_uid='geometry', template_uid=runtime_uid())

    def test_inline_building_is_preserved_without_own_member(self):
        raw = plot(runtime_uid(), secondary_buildings=[{'structure': runtime_uid(), 'foundation_depth': 0}])
        before = deepcopy(raw)
        prepared = PlotBodyPreparation().prepare_body(raw, local_uid='plot', template_uid=runtime_uid())
        self.assertNotIn('template_uid', prepared.main_building.model_dump())
        self.assertEqual(prepared.secondary_buildings[0].foundation_depth, 0)
        self.assertEqual(raw, before)

    def test_absent_building_and_nullable_cascade_values_are_not_filled(self):
        raw = {'system_name': 'plot', 'display_name': 'Plot', 'economic_tier': None,
               'main_building': None, 'secondary_buildings': []}
        body = PlotBodyPreparation().prepare_body(raw, local_uid='plot', template_uid=runtime_uid(),
                                                  world=World('w', 'World', 'now'))
        self.assertIsNone(body.main_building)
        self.assertIsNone(body.economic_tier)
        self.assertIsNone(body.economic_tier_range)
        self.assertEqual(body.secondary_buildings, [])

    def test_world_range_order_is_checked_without_changing_none_inheritance(self):
        from app.dataModel.economy.economyTier.worldEconomyTierRegistry import WorldEconomyTierRegistry
        registry = WorldEconomyTierRegistry.canonical_defaults()
        ordered = registry.sorted_by_base_value()
        world = World('w', 'World', 'now', economic_tier_registry=registry.model_dump(mode='json'))
        raw = plot(runtime_uid(), economic_tier_range={'min': ordered[-1].system_tier,
                                                       'max': ordered[0].system_tier})
        with self.assertRaises(TemplatePreparationError) as caught:
            PlotBodyPreparation().prepare_body(raw, local_uid='plot', template_uid=runtime_uid(), world=world)
        self.assertEqual(caught.exception.issues[0].code, 'DOMAIN_RANGE')

    def test_world_subject_constraints_are_checked(self):
        raw = plot(runtime_uid(), resource_kind='ore', subjects=['missing_resource'])
        with self.assertRaises(TemplatePreparationError) as caught:
            PlotBodyPreparation().prepare_body(raw, local_uid='plot', template_uid=runtime_uid(),
                                               world=World('w', 'World', 'now'))
        self.assertTrue(any(issue.path[-1] == 'subjects' for issue in caught.exception.issues))

    def test_ref_extraction_and_remap_share_main_secondary_and_direct_declarations(self):
        structure, secondary, external = runtime_uid(), runtime_uid(), runtime_uid()
        uid_map = {structure: runtime_uid(), secondary: runtime_uid()}
        for preparer, raw, key in (
            (PlotBodyPreparation(), plot(structure, secondary_buildings=[
                {'structure': secondary}, {'structure': external}]), 'plot'),
            (BuildingBodyPreparation(), building(structure), 'house'),
        ):
            with self.subTest(kind=preparer.library_kind):
                body = preparer.prepare_body(raw, local_uid=key, template_uid=runtime_uid())
                before = body.model_dump(mode='json')
                refs = preparer.body_refs(body, 'consumer')
                result = preparer.remap_body(body, uid_map)
                after = preparer.body_refs(result, 'consumer')
                self.assertEqual([(ref.path, ref.template_uid) for ref in after],
                    [(ref.path, uid_map.get(ref.template_uid, ref.template_uid)) for ref in refs])
                self.assertEqual(body.model_dump(mode='json'), before)
                self.assertTrue(all(ref.library_kind == LibraryKind.STRUCTURE_TEMPLATES for ref in refs))

    def test_structure_remap_keeps_model_a_identity(self):
        uid, target = runtime_uid(), runtime_uid()
        preparer = StructureBodyPreparation()
        body = preparer.prepare_body({'display_name': 'Geometry'}, local_uid='geo', template_uid=uid)
        self.assertEqual(preparer.remap_body(body, {uid: target}).system_name, target)
        self.assertEqual(body.system_name, uid)
        self.assertEqual(preparer.body_refs(body, uid), ())


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.structure = member(LibraryKind.STRUCTURE_TEMPLATES, 'geometry')
        self.plot = member(LibraryKind.PLOT_TEMPLATES, 'plot')
        self.building = member(LibraryKind.BUILDING_TEMPLATES, 'house')
        self.catalog = graph((self.structure, {'display_name': 'Geometry'}),
            (self.plot, plot(self.structure.template_uid)),
            (self.building, building(self.structure.template_uid)))

    def test_valid_scoped_graph_and_duplicate_local_names(self):
        twin = member(LibraryKind.BUILDING_TEMPLATES, 'house')
        self.catalog.members[twin.template_uid] = twin
        self.catalog.bodies[twin.template_uid] = building(self.structure.template_uid)
        before = deepcopy(self.catalog)
        self.assertEqual(template_graph_issues(self.catalog), ())
        self.assertEqual(self.catalog, before)

    def test_unknown_reference_reports_every_consumer_path(self):
        self.catalog.members.pop(self.structure.template_uid)
        self.catalog.bodies.pop(self.structure.template_uid)
        issues = template_graph_issues(self.catalog)
        self.assertEqual({issue.path[-1] for issue in issues}, {'main_building.structure', 'structure'})
        self.assertTrue(all(issue.reference.reason == ReferenceIssueReason.UNKNOWN_TEMPLATE for issue in issues))

    def test_known_foreign_owner_does_not_become_available(self):
        self.catalog.members.pop(self.structure.template_uid)
        issues = template_graph_issues(self.catalog,
            known_members={self.structure.template_uid: self.structure})
        self.assertTrue(all(issue.reference.reason == ReferenceIssueReason.OWNER_UNAVAILABLE for issue in issues))
        self.assertNotIn(self.structure.template_uid, self.catalog.members)

    def test_wrong_kind_rejects_even_when_uid_is_present(self):
        self.catalog.bodies[self.building.template_uid]['structure'] = self.plot.template_uid
        issues = template_graph_issues(self.catalog)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].reference.reason, ReferenceIssueReason.KIND_MISMATCH)

    def test_missing_body_is_distinguished_from_missing_member(self):
        self.catalog.bodies.pop(self.structure.template_uid)
        issues = template_graph_issues(self.catalog)
        self.assertTrue(any(issue.reference.reason == ReferenceIssueReason.BODY_MISSING for issue in issues))
        self.assertTrue(any(issue.path[-1] == 'main_building.structure' for issue in issues))

    def test_invalid_bodies_are_aggregated_without_mutating_or_falling_back(self):
        self.catalog.bodies[self.building.template_uid]['foundation_depth'] = -1
        self.catalog.bodies[self.plot.template_uid]['main_building']['structure'] = None
        before = deepcopy(self.catalog)
        issues = template_graph_issues(self.catalog)
        self.assertGreaterEqual(len(issues), 2)
        self.assertEqual({issue.path[1] for issue in issues},
                         {self.building.template_uid, self.plot.template_uid})
        self.assertEqual(self.catalog, before)


if __name__ == '__main__':
    unittest.main()
