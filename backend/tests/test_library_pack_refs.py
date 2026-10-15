"""LIBPACK-4C-R-2: reading/remapping cover the same declared references."""
from copy import deepcopy
from unittest import TestCase

from pydantic import ValidationError

from test_library_packs_4b import _ServiceCase, _plot_body, _PLOT, _STRUCT
from app.application.worldData.libraryPacks.domainAdapters.refFields import (
    remap_template_body, relief_policy_refs, template_body_refs,
)
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import (
    remap_relief_pick_policy,
)
from app.application.worldData.libraryPacks.errors import LibraryPackInUseError
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.db.models.world import World
from app.ids import runtime_uid


def _refs(raw: dict):
    return template_body_refs(_PLOT, PlotLayoutTemplate.model_validate(raw), 'consumer')


def _remap(raw: dict, uid_map):
    return remap_template_body(_PLOT, PlotLayoutTemplate.model_validate(raw), uid_map)


class ReferenceFieldTests(TestCase):
    def test_structure_read_and_remap_cover_main_and_every_secondary(self):
        main, secondary, external = runtime_uid(), runtime_uid(), runtime_uid()
        uid_map = {main: runtime_uid(), secondary: runtime_uid()}
        raw = _plot_body('house', main, secondary_buildings=[
            {'structure': secondary}, {'structure': external}, {'structure': main}],
            author_extension={'keep': True})
        before = deepcopy(raw)
        refs = _refs(raw)
        self.assertEqual([ref.path for ref in refs], [
            'main_building.structure', 'secondary_buildings[0].structure',
            'secondary_buildings[1].structure', 'secondary_buildings[2].structure'])
        result = _remap(raw, uid_map)
        after = template_body_refs(_PLOT, result, 'consumer')
        self.assertEqual([(ref.path, ref.template_uid) for ref in after],
                         [(ref.path, uid_map.get(ref.template_uid, ref.template_uid)) for ref in refs])
        self.assertEqual(raw, before)
        self.assertEqual(after[2].template_uid, external)

    def test_bodies_without_layout_refs_have_none(self):
        uid = runtime_uid()
        for raw in ({'system_name': 'outline', 'display_name': 'Outline'},
                    _plot_body('empty', uid, main_building=None, secondary_buildings=[])):
            with self.subTest(raw=raw):
                body = PlotLayoutTemplate.model_validate(raw)
                self.assertEqual(template_body_refs(_PLOT, body, 'consumer'), ())
                self.assertIs(remap_template_body(_PLOT, body, {uid: runtime_uid()}), body)

    def test_secondary_only_and_external_refs(self):
        uid = runtime_uid()
        raw = _plot_body('annex', uid, main_building=None, secondary_buildings=[{'structure': uid}])
        self.assertEqual(_refs(raw)[0].path, 'secondary_buildings[0].structure')
        body = PlotLayoutTemplate.model_validate(raw)
        self.assertIs(remap_template_body(_PLOT, body, {runtime_uid(): runtime_uid()}), body)
        self.assertIs(remap_template_body(_PLOT, body, {uid: uid}), body)

    def test_incomplete_body_is_not_silently_skipped(self):
        raw = {'main_building': {'structure': runtime_uid()}}
        with self.assertRaises(ValidationError):
            PlotLayoutTemplate.model_validate(raw)

    def test_relief_all_contexts_match_read_and_remap_and_preserve_wire(self):
        contexts = ('mountain', 'open_land', 'shore', 'road_shoulder', 'ravine')
        raw = {name: {'mode': 'fixed', 'default_template_uid': runtime_uid(), 'author_note': name}
               for name in contexts}
        raw['canal_obstacle_policy'] = []
        raw['author_extension'] = {'keep': True}
        world = World(world_uid='w1', name='World', created_at='2026-10-11', relief_pick_policy=raw)
        before = deepcopy(raw)
        refs = relief_policy_refs(world)
        self.assertEqual({ref.path for ref in refs},
                         {f'relief_pick_policy.{name}.default_template_uid' for name in contexts})
        uid_map = {ref.template_uid: runtime_uid() for ref in refs[:-1]}
        remapped = remap_relief_pick_policy(world, uid_map)
        world.relief_pick_policy = remapped
        after = relief_policy_refs(world)
        self.assertEqual([(ref.path, ref.template_uid) for ref in after],
                         [(ref.path, uid_map.get(ref.template_uid, ref.template_uid)) for ref in refs])
        self.assertEqual(raw, before)
        for name in contexts:
            self.assertEqual(remapped[name]['author_note'], name)
        self.assertEqual(remapped['author_extension'], {'keep': True})
        self.assertEqual(remapped['canal_obstacle_policy'], [])

    def test_relief_without_refs_is_a_noop(self):
        world = World(world_uid='w1', name='World', created_at='2026-10-11',
                      relief_pick_policy={'open_land': {'mode': 'random'}})
        self.assertEqual(relief_policy_refs(world), ())
        self.assertIsNone(remap_relief_pick_policy(world, {runtime_uid(): runtime_uid()}))


class SecondaryReferenceLifecycleTests(_ServiceCase):
    async def test_secondary_reference_is_remapped_and_blocks_delete(self):
        await self._world('w1')
        pack = await self.service.create_pack(system_name='engine.secondary')
        struct = await self.service.create_member(pack.pack_uid, library_kind=_STRUCT,
                                                  local_uid='geometry', body={'display_name': 'Geometry'})
        external = runtime_uid()
        plot = await self.service.create_member(pack.pack_uid, library_kind=_PLOT,
            local_uid='house', body=_plot_body('house', external,
                                              secondary_buildings=[{'structure': struct.template_uid}]))
        result = await self.service.instantiate_pack(pack.pack_uid, world_uid='w1')
        struct_uid = result.uid_map[struct.template_uid]
        plot_uid = result.uid_map[plot.template_uid]
        body = await self.service.read_member_body(plot_uid)
        self.assertEqual(body['main_building']['structure'], external)
        self.assertEqual(body['secondary_buildings'][0]['structure'], struct_uid)
        with self.assertRaises(LibraryPackInUseError) as caught:
            await self.service.delete_member(struct_uid, world_uid='w1')
        self.assertTrue(any('secondary_buildings[0].structure' in reason for reason in caught.exception.usages))
        self.assertIsNotNone(await self.members.get_by_uid(struct_uid))
