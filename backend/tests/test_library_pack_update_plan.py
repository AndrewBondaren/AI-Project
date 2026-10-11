"""LIBPACK-4C-R-3: update plans depend on snapshots, without repository I/O."""
from copy import deepcopy
from unittest.mock import patch

from test_library_packs_4b import _ServiceCase, _relief_body, _plot_body, _RELIEF, _STRUCT, _BUILDING
from app.application.jsonValidation.types import ReferenceIssueReason
from app.application.worldData.libraryPacks.reinstantiatePlan import build_update_plan, prepare_update
from app.application.worldData.libraryPacks.reinstantiateSnapshot import load_update_snapshot
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import remapped_library_uid


class UpdateSnapshotTests(_ServiceCase):
    async def instance(self):
        await self._world('w1')
        source, members = await self._relief_engine_pack(members=('meadow',))
        result = await self.service.instantiate_pack(source.pack_uid, world_uid='w1')
        return source, members[0], result.pack

    async def load(self, source, instance):
        return await load_update_snapshot(self.service._scope, source, instance,
                                          await self.worlds.get_by_id('w1'))

    async def test_snapshot_replay_without_io_is_stable_and_does_not_mutate_inputs(self):
        source, member, instance = await self.instance()
        snapshot = await self.load(source, instance)
        original = deepcopy(snapshot)
        expected = build_update_plan(snapshot, self.service._scope.adapters)
        await self.service.update_member_body(member.template_uid, _relief_body('meadow', display_name='New'))
        source.version = 'caller mutation'
        with patch.object(self.db.main_conn, '_execute', side_effect=AssertionError('planner performed SQL')):
            replay = build_update_plan(snapshot, self.service._scope.adapters)
            repeated = build_update_plan(snapshot, self.service._scope.adapters)
        self.assertEqual(replay, expected)
        self.assertEqual(repeated, expected)
        self.assertEqual(snapshot, original)
        fresh_source = await self.packs.get_by_uid(source.pack_uid)
        fresh = await self.load(fresh_source, instance)
        fresh_plan = build_update_plan(fresh, self.service._scope.adapters)
        self.assertNotEqual(fresh_plan.preview_token, replay.preview_token)
        self.assertTrue(any(p.changes for p in fresh_plan.prepared))
        # Confirm rebuilds from current data, rather than applying the old snapshot.
        confirmed = await self.service.instantiate_pack(source.pack_uid, world_uid='w1',
                            confirm=True, preview_token=replay.preview_token)
        self.assertTrue(confirmed.stale)
        self.assertFalse(confirmed.applied)
        self.assertEqual(confirmed.preview_token, fresh_plan.preview_token)

    async def test_loader_keeps_global_uid_conflicts_outside_available_catalog(self):
        source, _, instance = await self.instance()
        added = await self.service.create_member(source.pack_uid, library_kind=_RELIEF,
                                                 local_uid='added', body=_relief_body('added'))
        target_uid = remapped_library_uid(_RELIEF, target_pack_uid=instance.pack_uid,
                                          source_template_uid=added.template_uid)
        foreign = await self.service.create_pack(system_name='engine.foreign')
        adapter = self.service._scope.adapter_for(_RELIEF)
        await adapter.write_body(_relief_body('collision'), local_uid='collision', template_uid=target_uid,
                                  pack=foreign, world=None)
        await self.members.insert(LibraryPackMemberRow(target_uid, foreign.pack_uid, _RELIEF.value, 'collision'))
        snapshot = await self.load(source, instance)
        self.assertIn(target_uid, snapshot.known_members)
        self.assertNotIn(target_uid, snapshot.catalog.members)
        with patch.object(self.db.main_conn, '_execute', side_effect=AssertionError('planner performed SQL')):
            plan = build_update_plan(snapshot, self.service._scope.adapters)
        self.assertEqual(plan.conflicts, (f"target UID '{target_uid}' already belongs to another member",))
        self.assertFalse(any(p.member.template_uid == target_uid for p in plan.prepared))

    async def test_owner_diagnostics_are_resolved_from_snapshot_without_catalog_leak(self):
        source, _, instance = await self.instance()
        foreign = await self.service.create_pack(system_name='engine.geometry')
        geometry = await self.service.create_member(foreign.pack_uid, library_kind=_STRUCT,
                            local_uid='geometry', body={'display_name': 'Geometry'})
        await self.service.create_member(source.pack_uid, library_kind=_BUILDING, local_uid='house',
                                         body=_plot_body('house', geometry.template_uid))
        snapshot = await self.load(source, instance)
        self.assertNotIn(geometry.template_uid, snapshot.catalog.members)
        self.assertIn(geometry.template_uid, snapshot.known_members)
        with patch.object(self.db.main_conn, '_execute', side_effect=AssertionError('planner performed SQL')):
            plan = build_update_plan(snapshot, self.service._scope.adapters)
        issue, = plan.resolve_issues
        self.assertEqual(issue.reference.reason, ReferenceIssueReason.OWNER_UNAVAILABLE)
        self.assertEqual(issue.reference.owner_pack_uid, foreign.pack_uid)
        self.assertEqual(issue.reference.world_uid, 'w1')
        self.assertEqual(issue.reference.requested_template_uid, geometry.template_uid)

    async def test_orchestration_returns_same_plan_without_persisting(self):
        source, member, instance = await self.instance()
        await self.service.update_member_body(member.template_uid, _relief_body('meadow', display_name='Update'))
        world = await self.worlds.get_by_id('w1')
        snapshot = await self.load(source, instance)
        expected = build_update_plan(snapshot, self.service._scope.adapters)
        actual = await prepare_update(self.service._scope, source, instance, world)
        self.assertEqual(actual, expected)
        target_uid = actual.uid_map[member.template_uid]
        self.assertEqual((await self.service.read_member_body(target_uid))['display_name'], 'Meadow')
