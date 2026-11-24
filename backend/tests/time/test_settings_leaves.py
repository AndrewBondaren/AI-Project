"""Time settings leaf bindings against real owning pipelines."""
import unittest
from importlib import import_module
from unittest.mock import patch

from app.application.engine.nodes.timeSettings import registration as bindings
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.worldData.timeSettings.factory import (
    make_hours_settings_pipeline, make_calendar_settings_pipeline, make_epoch_settings_pipeline,
)
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.registryKey import RegistryKey
from app.dataModel.world.calendar.epochs.epoch import WorldCalendarEpoch
from app.dataModel.world.settings.timeOperations.changes import (
    HoursChange, CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove,
    EpochCreate, EpochUpdate, EpochRemove,
)
from tests.time import test_time_logging_bindings as time_fixtures


class SettingsLeafTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = time_fixtures.ProjectBindingTests()
        fixture.setUp()
        self.base = fixture.base
        self.key = fixture.first.definition.system_calendar
        self.hours = make_hours_settings_pipeline(fixture.validator, fixture.projector)
        self.calendar = make_calendar_settings_pipeline(fixture.validator, fixture.projector)
        self.epoch = make_epoch_settings_pipeline(fixture.validator)
        self.registry = NodeRegistry()
        bindings.register_time_settings_nodes(self.registry)
        self.runner = NodeRunner(ContractValidator(), NodeValidator())

    async def run_case(self, suffix, pipeline, request):
        name = "".join(part.title() for part in suffix.split("_"))
        node_type = getattr(import_module(
            "app.application.engine.nodes.timeSettings.prepare" + name + "Node"
        ), "Prepare" + name + "Node")
        node = node_type(pipeline=pipeline)
        contract = getattr(bindings, "PREPARE_" + suffix.upper() + "_CONTRACT")
        input_value = contract.input_type(request=request)
        registration = self.registry.get(node.id, contract)
        context = DAGContext(ExecutionId("time-leaf"), self.registry)
        identity = context.begin_attempt(node.id, PlanRevision("1"))
        method = "prepare_" + suffix
        with patch.object(pipeline, method, wraps=getattr(pipeline, method)) as call:
            outcome = await self.runner.run(node, context.read_view(node.id), identity,
                                            registration, PythonNodeExecutor(), explicit_input=input_value)
            call.assert_called_once_with(input_value.request)
        self.assertEqual(outcome.status, NodeStatus.SUCCESS)
        self.assertIsInstance(outcome.output.value, tuple(contract.output_type.model_fields["value"].annotation.__args__))
        self.assertEqual(contract.output_type.model_validate(outcome.output), outcome.output)
        return outcome.output.value

    async def test_all_eight_real_methods_and_registration(self):
        self.assertEqual(len(self.registry.ids()), 8)
        entry = self.base.capture.settings.calendars.entries[0]
        epoch = WorldCalendarEpoch(system_epoch=RegistryKey("reign"), display_epoch="Reign",
                                   description="", calendar=self.key, start_seconds=0,
                                   start_nanoseconds=1, start_year_label=10)
        cases = (
            ("hours_change", self.hours, HoursChange(base=self.base, hours_per_day=30, anchors=())),
            ("calendar_create", self.calendar, CalendarCreate(base=self.base, entry=entry)),
            ("calendar_update", self.calendar, CalendarUpdate(base=self.base, entry=entry)),
            ("calendar_select", self.calendar, CalendarSelect(base=self.base, calendar=self.key)),
            ("calendar_remove", self.calendar, CalendarRemove(base=self.base, calendar=self.key, replacement=self.key)),
            ("epoch_create", self.epoch, EpochCreate(base=self.base, epoch=epoch)),
            ("epoch_update", self.epoch, EpochUpdate(base=self.base, epoch=epoch)),
            ("epoch_remove", self.epoch, EpochRemove(base=self.base, epoch=epoch.system_epoch)),
        )
        for suffix, pipeline, request in cases:
            with self.subTest(suffix=suffix):
                await self.run_case(suffix, pipeline, request)
