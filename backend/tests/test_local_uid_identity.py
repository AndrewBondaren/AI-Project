import ast
import unittest
import asyncio
from types import SimpleNamespace
from pathlib import Path
from uuid import UUID
from contextlib import ExitStack
from unittest.mock import patch

from app.ids import (
    area_scope_uid, debug_building_uid, packing_token_uid,
    room_scope_uid, runtime_uid, standalone_building_uid,
)


def local_uid_expressions(source):
    """Track local string construction into UID sinks within lexical scopes."""
    hits = []
    def is_uid(name):
        return name == "uid" or name.endswith("_uid")

    def target_name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            return str(node.slice.value)
        return ""

    def scan(scope):
        nodes = []
        def collect(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scan(node)
                return
            nodes.append(node)
            for child in ast.iter_child_nodes(node):
                collect(child)
        for statement in scope.body:
            collect(statement)
        assignments = {}
        sinks = []
        for node in nodes:
            pairs = []
            if isinstance(node, ast.Assign):
                pairs = [(target, node.value) for target in node.targets]
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                pairs = [(node.target, node.value)]
            for target, value in pairs:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(value)
                if is_uid(target_name(target)):
                    sinks.append((node.lineno, target_name(target), value))
            if isinstance(node, ast.keyword) and is_uid(node.arg or ""):
                sinks.append((node.lineno, node.arg, node.value))
            if isinstance(node, ast.Return) and is_uid(getattr(scope, "name", "")):
                sinks.append((node.lineno, scope.name, node.value))

        def constructed(value, seen=frozenset()):
            if value is None:
                return False
            if isinstance(value, ast.Name):
                if value.id in seen:
                    return False
                return any(constructed(v, seen | {value.id}) for v in assignments.get(value.id, []))
            if isinstance(value, (ast.JoinedStr, ast.BinOp)):
                return True
            if isinstance(value, ast.Call):
                return isinstance(value.func, ast.Attribute) and value.func.attr in ("format", "format_map", "join")
            if isinstance(value, ast.IfExp):
                return constructed(value.body, seen) or constructed(value.orelse, seen)
            return False

        for line, name, value in sinks:
            if constructed(value):
                hits.append((line, name))
    scan(ast.parse(source))
    return hits


class LocalIdentityTests(unittest.TestCase):
    def test_build_tokens_replay_count_order_and_empty(self):
        from app.application.worldData.generators.assemblers.districtAssembler.planner import tokens as module
        template = SimpleNamespace(system_name="district", plot_counts={}, plot_priority={})
        slot = SimpleNamespace(district_template=template, origin_x=1, origin_y=2,
                               ground_z=3, slot_index=4)
        skeleton = SimpleNamespace(plot_counts={}, plot_priority={})
        required = SimpleNamespace(position=None)
        world = SimpleNamespace(world_uid="world")
        cache = SimpleNamespace(envelope=lambda uid: SimpleNamespace(width=2, depth=3))
        with ExitStack() as stack:
            stack.enter_context(patch.object(module, "buildings_rng", return_value=None))
            stack.enter_context(patch.object(module, "pick_layout_picks",
                return_value=[(SimpleNamespace(template_uid="template"), required)]))
            count = stack.enter_context(patch.object(module, "resolve_plot_count", return_value=(2, "test")))
            stack.enter_context(patch.object(module, "resolve_plot_priority", return_value=7))
            stack.enter_context(patch.object(module, "packing_info"))
            identity = stack.enter_context(patch.object(module, "packing_token_uid", wraps=packing_token_uid))
            def build(owner):
                return module.build_tokens(slot, cache, world, skeleton, catalog=None, settlement_uid=owner)
            first, replay, other = build("a"), build("a"), build("b")
            self.assertEqual(first, replay)
            self.assertEqual([t.copy_index for t in first], [0, 1])
            self.assertEqual([(t.w, t.h, t.priority) for t in first], [(2, 3, 7), (2, 3, 7)])
            self.assertTrue(set(t.uid for t in first).isdisjoint(t.uid for t in other))
            count.return_value = (0, "test")
            identity.reset_mock()
            self.assertEqual(build("a"), [])
            identity.assert_not_called()

    def test_district_caller_forwards_token_owner(self):
        from app.application.worldData.generators.assemblers.districtAssembler import districtAssembler as module
        slot = SimpleNamespace(district_template=SimpleNamespace(system_name="district"),
                               cell_x=0, cell_y=0, origin_x=1, origin_y=2,
                               ground_z=3, slot_index=4)
        world = SimpleNamespace(world_uid="world")
        values = []
        class Captured(Exception):
            pass
        def capture(slot, cache, world, skeleton, *, catalog, rng, settlement_uid=None):
            values.append(packing_token_uid(world.world_uid, settlement_uid,
                          slot.origin_x, slot.origin_y, slot.ground_z, slot.slot_index, "template", 0))
            self.assertEqual(settlement_uid, owner)
            raise Captured
        with ExitStack() as stack:
            for name, result in (
                ("street_classes_for", []), ("_as_cache", None),
                ("inner_bbox_for_slot", (None, None, None)),
                ("district_step", 1), ("make_lattice", None),
                ("corridor_rects_from_entries", (None, None)),
            ):
                stack.enter_context(patch.object(module, name, return_value=result))
            stack.enter_context(patch.object(module, "build_tokens", side_effect=capture))
            for owner in ("settlement-a", "settlement-b", "settlement-a"):
                with self.assertRaises(Captured):
                    module.DistrictAssembler().assemble(world, slot, SimpleNamespace(),
                                                        settlement_uid=owner, catalog=None)
        self.assertNotEqual(values[0], values[1])
        self.assertEqual(values[0], values[2])

    def test_native_store_identity_is_stable(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        store = MemoryExecutionStore()
        first = asyncio.run(store.get_store_id())
        self.assertIsInstance(first, UUID)
        self.assertEqual(first, asyncio.run(store.get_store_id()))

    def test_authored_identity_survives_roundtrip(self):
        from app.dataModel.perks.perkTemplateOutline import PerkTemplateOutline
        from app.dataModel.races.raceTemplateOutline import RaceTemplateOutline
        for model in (PerkTemplateOutline, RaceTemplateOutline):
            given = model.model_validate({"template_uid": "authored"})
            self.assertEqual(given.template_uid, "authored")
            generated = model.model_validate({})
            UUID(generated.template_uid)
            self.assertEqual(model.model_validate(generated.model_dump()).template_uid, generated.template_uid)

    def test_barrier_without_owner_has_no_dangling_reference(self):
        from app.application.worldData.generators.barrier.cells import emit_barrier_cells
        cells = emit_barrier_cells(SimpleNamespace(world_uid="world"),
                                   {(1, 2), (2, 2)}, {(1, 2)}, "stone", None, 3)
        self.assertEqual([(cell.x, cell.y, cell.z) for cell in cells], [(1, 2, 3), (2, 2, 3)])
        self.assertTrue(all(cell.location_uid is None for cell in cells))

    def test_identity_domains_and_owners(self):
        functions = (
            lambda w: area_scope_uid(w, "building"),
            lambda w: room_scope_uid(w, "building", "room"),
            lambda w: debug_building_uid(w),
            lambda w: standalone_building_uid(w, "template", 1, 2),
            lambda w: packing_token_uid(w, None, 1, 2, 3, 0, "template", 0),
        )
        values = [fn("world") for fn in functions]
        self.assertEqual(len(values), len(set(values)))
        for fn in functions:
            self.assertEqual(fn("world"), fn("world"))
            self.assertNotEqual(fn("world"), fn("other"))
            UUID(fn("world"))
        self.assertNotEqual(area_scope_uid("w", "a"), area_scope_uid("w", "b"))
        self.assertNotEqual(room_scope_uid("w", "b", "a"), room_scope_uid("w", "b", "b"))

    def test_each_token_component_is_identity(self):
        args = ["world", "settlement", 1, 2, 3, 4, "template", 0]
        base = packing_token_uid(*args)
        for index, value in enumerate(args):
            changed = list(args)
            changed[index] = value + 1 if isinstance(value, int) else value + "-other"
            self.assertNotEqual(base, packing_token_uid(*changed))
        args[1] = None
        self.assertNotEqual(base, packing_token_uid(*args))

    def test_invalid_identity_and_runtime_type(self):
        for call in (
            lambda: debug_building_uid(""),
            lambda: area_scope_uid("w", ""),
            lambda: room_scope_uid("w", "b", ""),
            lambda: standalone_building_uid("w", "", 0, 0),
            lambda: packing_token_uid("w", None, 0, 0, 0, 0, "t", -1),
            lambda: packing_token_uid("w", "", 0, 0, 0, 0, "t", 0),
        ):
            with self.assertRaises(ValueError):
                call()
        a, b = runtime_uid(), runtime_uid()
        self.assertEqual(str(UUID(a)), a)
        self.assertNotEqual(a, b)

    def test_gate_detects_bypasses_without_banning_diagnostics(self):
        self.assertTrue(local_uid_expressions('room_uid = f"{building}|{room}"'))
        self.assertTrue(local_uid_expressions('create(uid=owner + suffix)'))
        self.assertFalse(local_uid_expressions('message = f"room {room}"'))
        self.assertFalse(local_uid_expressions('room_uid = room_scope_uid(world, building, room)'))
        for source in (
            'item.location_uid = f"{world}-local"',
            'location_uid = "{}-local".format(world)',
            'value = f"{world}-local"\nalias = value\nlocation_uid = alias',
            'def local_uid(world):\n    value = f"{world}-local"\n    return value',
            'record["location_uid"] = "-".join(parts)',
        ):
            with self.subTest(source=source):
                self.assertTrue(local_uid_expressions(source))
        self.assertFalse(local_uid_expressions(
            'def diagnostic():\n    value = f"{world}-local"\n'
            'def consume(value):\n    location_uid = value'))
        self.assertFalse(local_uid_expressions(
            'value = room_scope_uid(world, building, room)\nitem.location_uid = value'))

    def test_closed_slice_has_no_local_string_uid(self):
        root = Path(__file__).resolve().parents[1] / "app"
        for relative in (
            "api/routes/debug.py",
            "application/cascade/locationScope.py",
            "application/worldData/generators/structure/room/roomFactory.py",
            "application/worldData/generators/assemblers/areaAssembler/structureAreaAssembler.py",
            "application/worldData/generators/assemblers/areaAssembler/planner/areaBarriers.py",
            "application/worldData/generators/assemblers/districtAssembler/planner/tokens.py",
        ):
            with self.subTest(path=relative):
                self.assertEqual(local_uid_expressions((root / relative).read_text(encoding="utf-8-sig")), [])


if __name__ == "__main__":
    unittest.main()
