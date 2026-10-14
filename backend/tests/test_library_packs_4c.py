"""Real SQLite lifecycle acceptance for library-packs-model step 4c."""
import asyncio
import sqlite3
from unittest import TestCase
from unittest.mock import patch

from test_library_packs_4b import _ServiceCase, _relief_body, _plot_body, _RELIEF, _STRUCT, _PLOT
from app.application.worldData.libraryPacks.errors import LibraryPackInUseError, LibraryPackOwnershipError
from app.application.worldData.libraryPacks.lifecycleContracts import MemberRef
from app.application.worldData.libraryPacks.reinstantiatePlan import hold_candidates
from app.db.database import Database, _in_transaction
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import remapped_library_uid, runtime_uid, state_fingerprint


class LifecycleTests(_ServiceCase):
    async def instance(self, names=('meadow', 'shore')):
        await self._world('w1')
        source, members = await self._relief_engine_pack(members=names)
        result = await self.service.instantiate_pack(source.pack_uid, world_uid='w1')
        return source, members, result

    async def preview(self, source, **kwargs):
        return await self.service.instantiate_pack(source.pack_uid, world_uid='w1', **kwargs)

    async def confirm(self, source, preview):
        return await self.preview(source, confirm=True, preview_token=preview.preview_token)

    async def snapshot(self):
        tables = ('library_packs', 'library_pack_members', 'library_pack_dependencies',
                  'relief_templates', 'building_templates', 'structure_templates', 'worlds')
        result = {}
        for name in tables:
            async with self.db.conn.execute(f'SELECT * FROM {name} ORDER BY 1') as cur:
                result[name] = [dict(row) for row in await cur.fetchall()]
        return result

    async def test_independent_same_name_copies_same_pack_preserve_source(self):
        pack, members = await self._relief_engine_pack(members=('meadow',))
        original = members[0]
        await self.db.conn.execute("UPDATE relief_templates SET source_file='user/original.json' WHERE template_uid=?",
                                   [original.template_uid])
        await self.db.conn.commit()
        first = (await self.service.copy_member(original.template_uid, pack.pack_uid)).member
        second = (await self.service.copy_member(original.template_uid, pack.pack_uid)).member
        self.assertEqual(len({original.template_uid, first.template_uid, second.template_uid}), 3)
        self.assertEqual(first.local_uid, original.local_uid)
        self.assertEqual(first.creation_kind, 'member_copy')
        self.assertEqual(first.source_template_uid, original.template_uid)
        self.assertEqual((await self.relief_rows.get_by_uid(first.template_uid)).source_file, 'user/original.json')
        await self.service.update_member_body(original.template_uid, _relief_body('meadow', display_name='Changed'))
        self.assertEqual((await self.relief_rows.get_by_uid(original.template_uid)).source_file, 'user/original.json')
        self.assertNotEqual((await self.service.read_member_body(first.template_uid))['display_name'], 'Changed')
        with self.assertRaises(ValueError):
            await self.members.find_by_local_uid(pack.pack_uid, _RELIEF.value, 'meadow')

    async def test_random_uid_collision_retries(self):
        pack, (member,) = await self._relief_engine_pack(members=('meadow',))
        fresh = runtime_uid()
        with patch('app.application.worldData.libraryPacks.memberWritePlanner.runtime_uid',
                   side_effect=[member.template_uid, fresh]):
            result = await self.service.copy_member(member.template_uid, pack.pack_uid)
        self.assertEqual(result.member.template_uid, fresh)

    async def test_cross_scope_copy_rejected(self):
        source, members, result = await self.instance()
        with self.assertRaises(LibraryPackOwnershipError):
            await self.service.copy_member(members[0].template_uid, result.pack.pack_uid, world_uid='w1')

    async def test_full_pack_remap_of_same_names_is_injective(self):
        source, members = await self._relief_engine_pack(members=('meadow',))
        copied = (await self.service.copy_member(members[0].template_uid, source.pack_uid)).member
        await self._world('w1')
        result = await self.service.instantiate_pack(source.pack_uid, world_uid='w1')
        self.assertEqual(len(set(result.uid_map.values())), 2)
        for uid in (members[0].template_uid, copied.template_uid):
            self.assertEqual(result.uid_map[uid], remapped_library_uid(
                _RELIEF, target_pack_uid=result.pack.pack_uid, source_template_uid=uid))
        published = await self.service.copy_pack(result.pack.pack_uid)
        self.assertEqual(len(set(published.uid_map.values())), 2)

    async def test_preview_diff_confirm_and_no_write_without_token(self):
        source, members, result = await self.instance()
        await self.service.update_member_body(members[0].template_uid, _relief_body('meadow', display_name='New'))
        before = await self.snapshot()
        preview = await self.preview(source)
        self.assertEqual(await self.snapshot(), before)
        changes = [change for p in preview.prepared for change in p.changes]
        self.assertEqual([c.path for c in changes], [('display_name',)])
        await self.preview(source, confirm=True)
        self.assertEqual(await self.snapshot(), before)
        applied = await self.confirm(source, preview)
        self.assertTrue(applied.applied)
        uid = result.uid_map[members[0].template_uid]
        self.assertEqual((await self.service.read_member_body(uid))['display_name'], 'New')
        self.assertFalse(any(p.changes for p in (await self.preview(source)).prepared))

    async def test_stale_source_and_pin_tokens_do_not_write(self):
        source, members, result = await self.instance()
        preview = await self.preview(source)
        await self.service.update_member_body(members[0].template_uid, _relief_body('meadow', display_name='Changed'))
        before = await self.snapshot()
        stale = await self.confirm(source, preview)
        self.assertTrue(stale.stale)
        self.assertEqual(await self.snapshot(), before)
        world = await self.worlds.get_by_id('w1')
        world.library_pins = [{'library_kind': _RELIEF.value, 'template_uid': result.members[0].template_uid}]
        await self.worlds.update(world)
        again = await self.confirm(source, stale)
        self.assertTrue(again.stale)
        self.assertFalse(again.applied)

    async def test_pinned_deleted_member_held_then_removed(self):
        source, members, result = await self.instance()
        uid = result.uid_map[members[0].template_uid]
        world = await self.worlds.get_by_id('w1')
        world.library_pins = [{'library_kind': _RELIEF.value, 'template_uid': uid}]
        await self.worlds.update(world)
        await self.service.delete_member(members[0].template_uid)
        preview = await self.preview(source)
        self.assertIn(uid, preview.held)
        await self.confirm(source, preview)
        self.assertEqual((await self.service.member_status(uid)).status, 'held by use')
        world = await self.worlds.get_by_id('w1')
        world.library_pins = []
        await self.worlds.update(world)
        preview = await self.preview(source)
        self.assertIn(uid, preview.removed)
        await self.confirm(source, preview)
        self.assertIsNone(await self.members.get_by_uid(uid))

    async def test_authored_and_independent_members_survive_update(self):
        source, members, result = await self.instance()
        independent = (await self.service.copy_member(result.members[0].template_uid,
                       result.pack.pack_uid, world_uid='w1')).member
        authored = await self.service.create_member(result.pack.pack_uid, library_kind=_RELIEF,
                    local_uid='extra', body=_relief_body('extra'), world_uid='w1')
        await self.service.delete_member(members[0].template_uid)
        preview = await self.preview(source)
        self.assertIn(independent.template_uid, preview.preserved)
        self.assertIn(authored.template_uid, preview.preserved)
        await self.confirm(source, preview)
        self.assertIsNotNone(await self.members.get_by_uid(independent.template_uid))

    async def mixed_instance(self):
        await self._world('w1')
        pack = await self.service.create_pack(system_name='user.mixed')
        struct = await self.service.create_member(pack.pack_uid, library_kind=_STRUCT,
                                                  local_uid='geometry', body={'display_name': 'Geometry'})
        plot = await self.service.create_member(pack.pack_uid, library_kind=_PLOT,
                                                local_uid='house', body=_plot_body('house', struct.template_uid))
        result = await self.service.instantiate_pack(pack.pack_uid, world_uid='w1')
        return pack, struct, plot, result

    async def test_result_graph_does_not_hold_refs_from_removed_building(self):
        source, struct, plot, result = await self.mixed_instance()
        await self.service.delete_member(plot.template_uid)
        await self.service.delete_member(struct.template_uid)
        preview = await self.preview(source)
        self.assertEqual(set(preview.removed), set(result.uid_map.values()))
        await self.confirm(source, preview)
        self.assertEqual(await self.service.list_members(result.pack.pack_uid), [])

    async def test_independent_copy_ref_holds_structure_and_delete_gate(self):
        source, struct, plot, result = await self.mixed_instance()
        plot_uid, struct_uid = result.uid_map[plot.template_uid], result.uid_map[struct.template_uid]
        copied = (await self.service.copy_member(plot_uid, result.pack.pack_uid, world_uid='w1')).member
        self.assertEqual((await self.service.read_member_body(copied.template_uid))['main_building']['structure'], struct_uid)
        with self.assertRaises(LibraryPackInUseError):
            await self.service.delete_member(struct_uid, world_uid='w1')
        await self.service.delete_member(plot.template_uid)
        await self.service.delete_member(struct.template_uid)
        preview = await self.preview(source)
        self.assertIn(struct_uid, preview.held)
        self.assertIn(plot_uid, preview.removed)
        await self.confirm(source, preview)
        self.assertEqual((await self.service.member_status(copied.template_uid)).status, 'source deleted')

    async def test_model_a_copy_changes_only_own_uid(self):
        source, struct, plot, result = await self.mixed_instance()
        copied = (await self.service.copy_member(struct.template_uid, source.pack_uid)).member
        body = await self.service.read_member_body(copied.template_uid)
        self.assertEqual(body['system_name'], copied.template_uid)
        self.assertEqual(body['display_name'], 'Geometry')

    async def test_confirm_failure_rolls_back_prior_writes(self):
        source, members, result = await self.instance()
        for member in members:
            await self.service.update_member_body(member.template_uid, _relief_body(member.local_uid, display_name='New'))
        preview = await self.preview(source)
        before = await self.snapshot()
        adapter = self.service._scope.adapter_for(_RELIEF)
        original = adapter.persist_prepared
        count = 0
        async def failing(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError('late domain failure')
            return await original(*args, **kwargs)
        with patch.object(adapter, 'persist_prepared', side_effect=failing):
            with self.assertRaises(ValueError):
                await self.confirm(source, preview)
        self.assertEqual(await self.snapshot(), before)

    async def test_other_task_writer_waits_for_transaction_owner(self):
        source, members, result = await self.instance()
        entered = asyncio.Event()
        async def writer():
            self.assertFalse(_in_transaction.get())
            entered.set()
            await self.service.update_member_body(members[0].template_uid, _relief_body('meadow', display_name='Concurrent'))
        async with self.db.transaction_if_needed():
            task = asyncio.create_task(writer())
            await entered.wait()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertNotEqual((await self.service.read_member_body(members[0].template_uid))['display_name'], 'Concurrent')
        await asyncio.wait_for(task, timeout=2)

    async def test_external_connection_cannot_write_during_confirm_uow(self):
        source, members, result = await self.instance()
        other = Database(self.db.path)
        await other.connect()
        try:
            await other.conn.execute('PRAGMA busy_timeout=20')
            async with self.db.transaction():
                with self.assertRaises(sqlite3.OperationalError):
                    await other.conn.execute("UPDATE library_packs SET version='other' WHERE pack_uid=?", [source.pack_uid])
            self.assertEqual((await self.packs.get_by_uid(source.pack_uid)).version, source.version)
        finally:
            await other.disconnect()

    async def test_no_technical_diff_and_source_status(self):
        source, members, result = await self.instance()
        self.assertFalse(any(p.changes for p in (await self.preview(source)).prepared))
        await self.service.delete_pack(source.pack_uid)
        self.assertEqual((await self.service.member_status(result.members[0].template_uid)).status, 'source deleted')

    async def test_added_source_and_renamed_source_keep_saved_identity(self):
        source, members, result = await self.instance(names=('meadow',))
        original = members[0]
        await self.members.update_local_uid(original.template_uid, 'renamed')
        # Seed a consistent renamed source revision; public edits keep the local key.
        row = await self.relief_rows.get_by_uid(original.template_uid)
        row.system_name = 'renamed'
        row.data = _relief_body('renamed')
        await self.relief_rows.save(row)
        added = await self.service.create_member(source.pack_uid, library_kind=_RELIEF,
                    local_uid='new', body=_relief_body('new'))
        preview = await self.preview(source)
        self.assertEqual(preview.uid_map[original.template_uid], result.uid_map[original.template_uid])
        self.assertEqual(sum(p.added for p in preview.prepared), 1)
        applied = await self.confirm(source, preview)
        self.assertTrue(applied.applied)
        saved = await self.members.get_by_uid(result.uid_map[original.template_uid])
        self.assertEqual(saved.local_uid, 'renamed')
        self.assertIsNotNone(await self.members.get_by_uid(preview.uid_map[added.template_uid]))

    async def test_saved_uid_from_older_remap_is_not_recomputed(self):
        await self._world('w1')
        source, (member,) = await self._relief_engine_pack(members=('meadow',))
        old_uid = runtime_uid()
        with patch('app.application.worldData.libraryPacks.packWritePlanner.remapped_library_uid', return_value=old_uid):
            result = await self.service.instantiate_pack(source.pack_uid, world_uid='w1')
        self.assertEqual(result.uid_map[member.template_uid], old_uid)
        await self.service.update_member_body(member.template_uid, _relief_body('meadow', display_name='Updated'))
        preview = await self.preview(source)
        self.assertEqual(preview.uid_map[member.template_uid], old_uid)
        await self.confirm(source, preview)
        self.assertEqual((await self.service.read_member_body(old_uid))['display_name'], 'Updated')

    async def test_world_policy_holds_deleted_source_member(self):
        source, members, result = await self.instance(names=('meadow',))
        uid = result.uid_map[members[0].template_uid]
        world = await self.worlds.get_by_id('w1')
        world.relief_pick_policy = {'open_land': {'default_template_uid': uid}}
        await self.worlds.update(world)
        await self.service.delete_member(members[0].template_uid)
        preview = await self.preview(source)
        self.assertIn(uid, preview.held)
        self.assertTrue(any('relief_pick_policy' in reason for reason in preview.held[uid]))

    async def test_embedded_layout_holds_deleted_structure(self):
        source, struct, plot, result = await self.mixed_instance()
        uid = result.uid_map[struct.template_uid]
        world = await self.worlds.get_by_id('w1')
        world.building_template_registry.append(_plot_body('embedded', uid))
        await self.worlds.update(world)
        await self.service.delete_member(plot.template_uid)
        await self.service.delete_member(struct.template_uid)
        preview = await self.preview(source)
        self.assertIn(uid, preview.held)
        self.assertTrue(any('building_template_registry' in reason for reason in preview.held[uid]))

    async def test_other_world_pin_and_policy_do_not_hold_candidate(self):
        source, members, result = await self.instance(names=('meadow',))
        uid = result.uid_map[members[0].template_uid]
        await self._world('w2')
        other = await self.worlds.get_by_id('w2')
        other.library_pins = [{'library_kind': _RELIEF.value, 'template_uid': uid}]
        other.relief_pick_policy = {'open_land': {'default_template_uid': uid}}
        await self.worlds.update(other)
        await self.service.delete_member(members[0].template_uid)
        preview = await self.preview(source)
        self.assertIn(uid, preview.removed)
        self.assertNotIn(uid, preview.held)

    async def test_initial_instantiate_remaps_pin_uid(self):
        await self._world('w1')
        source, (member,) = await self._relief_engine_pack(members=('meadow',))
        world = await self.worlds.get_by_id('w1')
        world.library_pins = [{'library_kind': _RELIEF.value, 'template_uid': member.template_uid}]
        await self.worlds.update(world)
        result = await self.service.instantiate_pack(source.pack_uid, world_uid='w1')
        saved = await self.worlds.get_by_id('w1')
        self.assertEqual(saved.library_pins[0]['template_uid'], result.uid_map[member.template_uid])

    async def test_member_copy_late_failure_rolls_back_body_and_member(self):
        source, members, result = await self.instance(names=('meadow',))
        before = await self.snapshot()
        adapter = self.service._scope.adapter_for(_RELIEF)
        with patch.object(self.container.world_repository(), 'update', side_effect=ValueError('pointer failure')):
            with self.assertRaises(ValueError):
                await self.service.copy_member(result.members[0].template_uid, result.pack.pack_uid, world_uid='w1')
        self.assertEqual(await self.snapshot(), before)

    async def test_metadata_change_invalidates_token(self):
        source, members, result = await self.instance(names=('meadow',))
        preview = await self.preview(source)
        await self.service.update_pack_metadata(source.pack_uid, display_name='New pack', version='2.0')
        before = await self.snapshot()
        stale = await self.confirm(source, preview)
        self.assertTrue(stale.stale)
        self.assertEqual(await self.snapshot(), before)
        self.assertEqual({c.path for c in stale.metadata_changes}, {('display_name',), ('version',)})
        await self.confirm(source, stale)
        self.assertEqual((await self.packs.get_by_uid(result.pack.pack_uid)).version, '2.0')

    async def test_cancelled_update_rolls_back_and_releases_connection(self):
        source, members, result = await self.instance(names=('meadow',))
        before = await self.snapshot()
        wrote = asyncio.Event()
        async def writer():
            async with self.db.transaction_if_needed():
                await self.service.update_member_body(members[0].template_uid,
                                    _relief_body('meadow', display_name='Cancelled'))
                wrote.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(writer())
        await wrote.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(await asyncio.wait_for(self.snapshot(), timeout=2), before)


class HoldGraphTests(TestCase):
    def test_chain_from_pin_and_cycle_without_roots(self):
        members = {uid: LibraryPackMemberRow(uid, 'pack', 'structure_templates', uid)
                   for uid in ('a', 'b', 'x', 'y')}
        refs = (MemberRef('structure_templates', 'b', 'a', 'ref'),
                MemberRef('structure_templates', 'x', 'y', 'ref'),
                MemberRef('structure_templates', 'y', 'x', 'ref'))
        held = hold_candidates(refs, members, set(members), {'a': ('pin',)})
        self.assertEqual(set(held), {'a', 'b'})

    def test_fingerprint_and_remap_names_not_inputs(self):
        self.assertEqual(state_fingerprint({'a': 1, 'b': 2}), state_fingerprint({'b': 2, 'a': 1}))
        self.assertNotEqual(state_fingerprint({'a': 1}), state_fingerprint({'a': 2}))
        a = remapped_library_uid(_STRUCT, target_pack_uid='target', source_template_uid='source')
        self.assertEqual(a, remapped_library_uid(_STRUCT, target_pack_uid='target', source_template_uid='source'))
        self.assertNotEqual(a, remapped_library_uid(_STRUCT, target_pack_uid='other', source_template_uid='source'))
