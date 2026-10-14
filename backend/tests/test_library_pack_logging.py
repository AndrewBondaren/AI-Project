"""LIBPACK-4C-R-1: lifecycle diagnostics use the shared resolve sink."""
import io
import json
import logging
from pathlib import Path
from unittest import TestCase

from test_library_packs_4b import _ServiceCase, _plot_body, _relief_body, _PLOT, _RELIEF, _STRUCT
from app.application.jsonValidation.types import ReferenceIssueReason
from app.application.worldData.libraryPacks.lifecycleContracts import MemberRef
from app.application.worldData.libraryPacks.referenceResolver import reference_index
from app.core.generationLogging import generation_world_log
from app.core.loggingConfig import _remove_facade_handlers, flush_console_queue, setup_logging
from app.ids import runtime_uid

_LOGGER = 'app.application.jsonValidation.resolve'


class LifecycleLoggingTests(_ServiceCase):
    async def world_plot(self, world_uid='w1', structure_uid=None):
        await self._world(world_uid)
        pack = await self.service.create_pack(system_name=f'world.{world_uid}.plots', owner_world_uid=world_uid)
        plot = await self.service.create_member(
            pack.pack_uid, library_kind=_PLOT, local_uid='house',
            body=_plot_body('house', structure_uid or runtime_uid()), world_uid=world_uid)
        return pack, plot

    async def test_copy_reports_owner_and_dependency_once_and_keeps_dto(self):
        engine = await self.service.create_pack(system_name='engine.geometry')
        geometry = await self.service.create_member(engine.pack_uid, library_kind=_STRUCT,
                                                    local_uid='geometry', body={'display_name': 'Geometry'})
        pack, plot = await self.world_plot(structure_uid=geometry.template_uid)
        missing = runtime_uid()
        await self.service.set_dependencies(pack.pack_uid, [missing], world_uid='w1')
        with self.assertLogs(_LOGGER, 'WARNING') as captured:
            copied = await self.service.copy_member(plot.template_uid, pack.pack_uid, world_uid='w1')
        self.assertEqual(len(captured.records), 2)
        reference, dependency = captured.records
        self.assertEqual(reference.reason, ReferenceIssueReason.OWNER_UNAVAILABLE)
        self.assertEqual(reference.world_uid, 'w1')
        self.assertEqual(reference.domain, _STRUCT.value)
        self.assertEqual(reference.owner_pack_uid, engine.pack_uid)
        self.assertEqual(reference.requested_template_uid, geometry.template_uid)
        self.assertEqual(reference.reference_path, (copied.member.template_uid, 'main_building.structure'))
        self.assertIsNone(reference.selected_default)  # lifecycle does not apply a fallback
        self.assertEqual(dependency.dependency_pack_uid, missing)
        self.assertEqual(dependency.owner_pack_uid, pack.pack_uid)
        self.assertEqual(len(copied.diagnostics), 2)

    async def test_preview_and_confirm_each_emit_one_event_per_issue(self):
        await self._world('w1')
        pack = await self.service.create_pack(system_name='engine.plots')
        missing_template = runtime_uid()
        await self.service.create_member(pack.pack_uid, library_kind=_PLOT, local_uid='house',
                                         body=_plot_body('house', missing_template))
        await self.service.instantiate_pack(pack.pack_uid, world_uid='w1')
        missing_pack = runtime_uid()
        await self.service.set_dependencies(pack.pack_uid, [missing_pack])
        for confirm in (False, True):
            with self.assertLogs(_LOGGER, 'WARNING') as captured:
                preview = await self.service.instantiate_pack(
                    pack.pack_uid, world_uid='w1', confirm=confirm,
                    preview_token=preview.preview_token if confirm else None)
            self.assertEqual(len(captured.records), 2)
            self.assertEqual(len(preview.diagnostics), 2)
            self.assertEqual(captured.records[0].reason, ReferenceIssueReason.UNKNOWN_TEMPLATE)
            self.assertEqual(captured.records[0].requested_template_uid, missing_template)
            self.assertEqual(captured.records[1].dependency_pack_uid, missing_pack)
            self.assertEqual(preview.applied, confirm)

    async def test_usage_path_reports_unresolved_refs(self):
        pack, _ = await self.world_plot()
        member = await self.service.create_member(pack.pack_uid, library_kind=_RELIEF,
                    local_uid='meadow', body=_relief_body('meadow'), world_uid='w1')
        with self.assertLogs(_LOGGER, 'WARNING') as captured:
            await self.service.delete_member(member.template_uid, world_uid='w1')
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(captured.records[0].world_uid, 'w1')
        self.assertEqual(captured.records[0].reason, ReferenceIssueReason.UNKNOWN_TEMPLATE)

    async def test_warning_is_not_suppressed_in_another_world(self):
        missing = runtime_uid()
        records = []
        for world_uid in ('w1', 'w2'):
            pack, plot = await self.world_plot(world_uid, missing)
            with self.assertLogs(_LOGGER, 'WARNING') as captured:
                await self.service.copy_member(plot.template_uid, pack.pack_uid, world_uid=world_uid)
            records.extend(captured.records)
        self.assertEqual([r.world_uid for r in records], ['w1', 'w2'])

    async def test_common_sink_and_transcript_receive_same_single_warning(self):
        pack, plot = await self.world_plot()
        logs = Path(self.tmp.name) / 'logs'
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        self.addCleanup(root_logger.setLevel, previous_level)
        self.addCleanup(_remove_facade_handlers)
        setup_logging(level=logging.WARNING, profile='server', logs_dir=logs, stream=io.StringIO())
        with generation_world_log('w1', mode='test', root=logs / 'generation') as transcript:
            await self.service.copy_member(plot.template_uid, pack.pack_uid, world_uid='w1')
        flush_console_queue()
        for handler in root_logger.handlers:
            handler.flush()
        def reference_events(path):
            return [record for line in path.read_text(encoding='utf-8').splitlines()
                    if (record := json.loads(line)).get('requested_template_uid')]
        sink_records = reference_events(logs / 'jsonValidation' / 'resolve.log')
        run_records = reference_events(transcript)
        self.assertEqual(len(sink_records), 1)
        self.assertEqual(sink_records, run_records)
        self.assertEqual(sink_records[0]['world_uid'], 'w1')
        self.assertEqual(sink_records[0]['logger'], _LOGGER)


class ReferenceIndexLoggingTests(TestCase):
    def test_index_returns_typed_facts_without_emitting(self):
        ref = MemberRef(_STRUCT.value, runtime_uid(), 'consumer', 'main_building.structure')
        with self.assertNoLogs(_LOGGER, 'WARNING'):
            index, issues = reference_index((ref, ref), {})
        self.assertEqual(index, {})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].reference.reason, ReferenceIssueReason.UNKNOWN_TEMPLATE)
        self.assertEqual(issues[0].reference.requested_template_uid, ref.template_uid)
