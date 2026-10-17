"""Contract hygiene: bare ``str`` on ``*_type``/``*_kind`` fields is a hole.

Rules: ``.cursor/rules/type-kind-str-fields.mdc`` +
``.cursor/rules/contract-creation.mdc`` — a contract field named
``*_type``/``*_kind`` must be a ``RegistryKey[…]`` alias, ``StrEnum`` or a
closed ``Literal``; a bare ``str`` loses registry membership and fails
silently. This test scans class-level annotations under ``app/`` with the
AST (no runtime imports — it cannot mask an import error and covers
``@dataclass`` and Pydantic models identically) and rejects holes that
are not in ``KNOWN_HOLES``.

``KNOWN_HOLES`` mirrors the debt map in
``.cursor/plans/type-kind-str-fields-debt.md``: an entry may only leave
the list when the corresponding plan step lands — a stale entry fails
the test, so the list can only shrink. A legitimate ``str`` field needs
an explicit marking in ``docs/tz_*.md`` AND an entry here naming it
(``grid_kind``/scaffold/dependent-key rows below are exactly that).
"""

from __future__ import annotations

import ast
import re
import tempfile
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _read_wire_alias_names() -> frozenset[str]:
    """Read the policy's literal alias inventory without importing app modules."""
    path = APP_ROOT / "dataModel" / "annotationPolicy.py"
    tree = ast.parse(path.read_bytes(), filename=str(path))
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_WIRE_ALIAS_NAMES"
            for target in stmt.targets
        ):
            value = stmt.value
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == "frozenset" and len(value.args) == 1):
                return frozenset(ast.literal_eval(value.args[0]))
    raise AssertionError("annotationPolicy.py: expected literal _WIRE_ALIAS_NAMES inventory")


_WIRE_ALIAS_NAMES = _read_wire_alias_names()

_FIELD_RE = re.compile(r"(?:^|_)(?:type|kind)$")
_PEEL_HEADS = frozenset({"Annotated", "ClassVar", "Optional"})

# (module, class, field) → plan step or spec reference.
# Entries may only be REMOVED (as plan steps land) — never added without
# a spec marking in docs/tz_*.md. New hole = failed test.
KNOWN_HOLES: dict[tuple[str, str, str], str] = {
    # --- шаг 1: library_kind → LibraryKind ---
    ("app/application/templateLibrary/packs/lifecycleContracts.py", "MemberRef", "library_kind"): "1",
    ("app/application/templateLibrary/packs/legacy/legacyWorldContracts.py", "LegacyPointerDecision", "library_kind"): "1",
    ("app/dataModel/libraryPacks/libraryPinEntry.py", "LibraryPinEntry", "library_kind"): "1+scan",
    ("app/dataModel/libraryPacks/packManifest.py", "LibraryPackManifestMember", "library_kind"): "1+scan",
    # --- шаг 2: connection_type → ConnectionTypeKey ---
    ("app/application/worldData/generators/assemblers/districtAssembler/connectionEntry.py", "ConnectionEntry", "connection_type"): "2",
    ("app/application/worldData/generators/road/connectionPolicy.py", "ConnectionPaint", "connection_type"): "2",
    ("app/application/worldData/generators/hydrology/types.py", "DeclaredRiverEdge", "connection_type"): "2",
    ("app/application/worldData/generators/hydrology/types.py", "RiverSegment", "connection_type"): "2",
    ("app/dataModel/hydrology/declaredRiver.py", "DeclaredRiverSegment", "connection_type"): "2+scan",
    ("app/application/jsonValidation/bundle/connectionGraph.py", "ConnectionEdgeImportRow", "connection_type"): "2+scan",
    ("app/dataModel/roads/roadSettingsEntry.py", "RoadSettingsEntry", "system_connection_type"): "2+scan",
    # --- шаг 3: structure shape/room/staircase ---
    ("app/application/worldData/generators/structure/room/roomInstance.py", "_RoomInstance", "shape_type"): "3",
    ("app/application/worldData/generators/structure/room/roomInstance.py", "_RoomInstance", "room_type"): "3",
    ("app/application/worldData/generators/structure/room/roomInstance.py", "_RoomInstance", "staircase_type"): "3",
    ("app/dataModel/locations/structure/enums/staircaseType.py", "StaircaseTypeSpec", "default_shaft_size_type"): "3",
    ("app/dataModel/locations/structure/room/roomDef.py", "RoomDef", "shape_type"): "3+scan",
    ("app/dataModel/locations/structure/room/roomDef.py", "RoomDef", "room_type"): "3+scan",
    ("app/dataModel/locations/structure/room/roomDef.py", "RoomDef", "staircase_type"): "3+scan",
    # --- dependent-key секция плана (namespace по родителю) ---
    ("app/dataModel/locations/structure/room/sizeSpec.py", "SizeSpec", "size_type"): "docs/tz_json_validation.md § Contract hygiene (dependent-key)",
    ("app/dataModel/locations/structure/building/staircaseSpec.py", "ShaftSize", "size_type"): "docs/tz_json_validation.md § Contract hygiene (dependent-key)",
    # --- шаг 4 / scaffold-контексты (enum при появлении producer) ---
    ("app/application/worldData/generators/assemblers/buildingAssembler/structureContext.py", "StructureContext", "foundation_type"): "4",
    ("app/application/worldData/generators/assemblers/buildingAssembler/vastHullAssembler.py", "VastHullContext", "hull_type"): "docs/tz_json_validation.md § Contract hygiene (scaffold)",
    ("app/application/worldData/generators/assemblers/buildingAssembler/resourceExtractionAssembler.py", "ResourceExtractionContext", "extraction_type"): "docs/tz_json_validation.md § Contract hygiene (scaffold)",
    ("app/application/worldData/generators/assemblers/buildingAssembler/resourceExtractionAssembler.py", "ResourceExtractionContext", "resource_type"): "4",
    ("app/application/worldData/generators/assemblers/buildingAssembler/ruinsAssembler.py", "RuinsContext", "base_structure_type"): "docs/tz_json_validation.md § Contract hygiene (scaffold)",
    ("app/dataModel/locations/structure/building/buildingBodyTemplate.py", "BuildingBodyTemplate", "foundation_type"): "4+scan",
    # --- шаг 5: pole_kind → enum ---
    ("app/application/worldData/generators/climate/climatePole.py", "ClimatePolePoint", "pole_kind"): "5",
    ("app/dataModel/climate/enums/climatePolePreset.py", "ClimatePoleSpec", "pole_kind"): "5",
    # --- шаг 6: system_location_type → LocationTypeKey ---
    # --- шаг 7: hydrology node_type ---
    ("app/application/worldData/generators/hydrology/types.py", "ResolvedConnectionNode", "node_type"): "7",
    # --- шаг 8: task_type → TaskType ---
    ("app/api/routes/chat.py", "ChatRequest", "task_type"): "8",
    ("app/application/cancellation/sessionSnapshot.py", "SessionSnapshot", "task_type"): "8",
    ("app/application/events/sseEvents.py", "NodeStatusEvent", "task_type"): "8",
    ("app/api/schemas/chat.py", "SocketEvent", "type"): "new: plan § Инвентаризация шага 0 (domain unverified)",
    ("app/application/engine/rules/rule.py", "Rule", "type"): "new: plan § Инвентаризация шага 0 (domain unverified)",
    ("app/application/worldData/render/renderPayloads.py", "WorldTileEntryPayload", "grid_kind"): "docs/tz_json_validation.md § Contract hygiene (grid_kind)",
    # --- шаг 9: roof_type (str|list — форма контракта с мастером) ---
    ("app/application/worldData/generators/assemblers/buildingAssembler/structureContext.py", "StructureContext", "roof_type"): "9",
    ("app/dataModel/locations/structure/building/buildingBodyTemplate.py", "BuildingBodyTemplate", "roof_type"): "9",
    # --- находки сканом вне карты плана — новые дыры, требуют шагов ---
    ("app/application/jsonValidation/bundle/connectionGraph.py", "ConnectionEdgeImportRow", "lighting_type"): "new",
    ("app/application/jsonValidation/bundle/connectionGraph.py", "ConnectionNodeImportRow", "portal_type"): "new",
    ("app/dataModel/locations/locationType/locationTypeEntry.py", "LocationTypeEntry", "display_type"): "docs/tz_json_validation.md § Contract hygiene (display text)",
    ("app/dataModel/locations/settlement/district/districtTemplateEntry.py", "DistrictTemplateEntry", "district_type"): "new",
    ("app/dataModel/locations/settlement/district/placementCondition.py", "PlacementCondition", "district_type"): "new",
    ("app/dataModel/locations/settlement/settlement/typicalDistrictRef.py", "TypicalDistrictRef", "district_type"): "new",
    ("app/dataModel/locations/settlement/settlement/settlementSpecializationEntry.py", "SettlementSpecializationEntry", "subject_kind"): "new",
    ("app/dataModel/terrain/relief/canal.py", "EarthenCanal", "system_type"): "new",
    ("app/dataModel/terrain/relief/canal.py", "StructureCanal", "system_type"): "new",
    ("app/dataModel/terrain/relief/canalTemplateEntry.py", "CanalTemplateEntry", "system_type"): "new",
}


def _head_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _subscript_args(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.Tuple):
        return list(node.elts)
    return [node]


def _is_none(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Constant) and node.value is None
    ) or (isinstance(node, ast.Name) and node.id == "None")


def _leaf_atoms(node: ast.expr) -> list[ast.expr]:
    """Strip wire-policy/Annotated/ClassVar/Optional wrappers and ``| None``.

    Returns the remaining leaf annotations (one per union member). A field
    is a hole when any leaf is a bare ``str`` name.
    """
    if _is_none(node):
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _leaf_atoms(ast.parse(node.value, mode="eval").body)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _leaf_atoms(node.left) + _leaf_atoms(node.right)
    if isinstance(node, ast.Subscript):
        head = _head_name(node.value)
        args = _subscript_args(node.slice)
        if head in _WIRE_ALIAS_NAMES or head in _PEEL_HEADS:
            # Annotated's remaining arguments are metadata, not union branches.
            return _leaf_atoms(args[0])
        if head == "Union":
            return [leaf for arg in args for leaf in _leaf_atoms(arg)]
    return [node]


def _is_bare_str(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "str"


def _iter_class_fields(tree: ast.AST, prefix: str = ""):
    """Yield (qualname, field_name, annotation) for class-level AnnAssign."""
    for child in ast.iter_child_nodes(tree):
        if isinstance(child, ast.ClassDef):
            qual = f"{prefix}.{child.name}" if prefix else child.name
            for stmt in child.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    yield qual, stmt.target.id, stmt.annotation
            yield from _iter_class_fields(child, qual)
        else:
            yield from _iter_class_fields(child, prefix)


def scan_holes(app_root: Path = APP_ROOT) -> set[tuple[str, str, str]]:
    """All ``*_type``/``*_kind`` class fields with a bare ``str`` leaf."""
    holes: set[tuple[str, str, str]] = set()
    for path in sorted(app_root.rglob("*.py")):
        rel = path.relative_to(app_root.parent).as_posix()
        parts = path.relative_to(app_root).parts
        if parts[:2] == ("db", "models"):
            continue  # SQL rows — str by layer definition, not a contract
        tree = ast.parse(path.read_bytes(), filename=str(path))
        for qual, name, annotation in _iter_class_fields(tree):
            if not _FIELD_RE.search(name):
                continue
            if any(_is_bare_str(leaf) for leaf in _leaf_atoms(annotation)):
                holes.add((rel, qual, name))
    return holes


def _fmt(holes: set[tuple[str, str, str]]) -> str:
    return "\n".join(
        f'    ("{m}", "{c}", "{f}"): "??",' for m, c, f in sorted(holes)
    )


def assert_no_new_holes(holes, known_holes) -> None:
    new = set(holes) - set(known_holes)
    if new:
        raise AssertionError(
            "new bare-str *_type/*_kind contract fields — type them "
            "(RegistryKey/StrEnum/Literal, see type-kind-str-fields.mdc) "
            "or mark the exception in docs/tz_*.md and add an entry:\n" + _fmt(new))


def assert_no_stale_holes(holes, known_holes) -> None:
    stale = set(known_holes) - set(holes)
    if stale:
        raise AssertionError(
            "debt closed — remove these entries from KNOWN_HOLES:\n" + _fmt(stale))


class ContractHygieneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.holes = scan_holes()

    def test_no_new_str_type_kind_holes(self):
        assert_no_new_holes(self.holes, KNOWN_HOLES)

    def test_known_holes_are_not_stale(self):
        assert_no_stale_holes(self.holes, KNOWN_HOLES)


class ContractScannerTests(unittest.TestCase):
    def scan_source(self, source):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "app"
            root.mkdir()
            (root / "contracts.py").write_text(source, encoding="utf-8")
            models = root / "db" / "models"
            models.mkdir(parents=True)
            (models / "row.py").write_text("class Row:\n    node_type: str\n", encoding="utf-8")
            return scan_holes(root)

    def test_wrapped_optional_union_and_quoted_annotations(self):
        annotations = (
            "str", "str | None", "Optional[str]", "typing.Optional[str]",
            "Annotated[str, 'metadata']", "ClassVar[Optional[str]]",
            "'StrictOnWire[str | None]'", "Union[int, Optional[str]]",
            "int | Annotated[Optional[str], 'metadata']", "str | list[str]",
            *[f"{name}[str | None]" for name in sorted(_WIRE_ALIAS_NAMES)],
        )
        for annotation in annotations:
            with self.subTest(annotation=annotation):
                holes = self.scan_source(f"class Contract:\n    task_type: {annotation}\n")
                self.assertEqual(holes, {("app/contracts.py", "Contract", "task_type")})

    def test_typed_keys_enums_literals_parameters_and_db_rows_are_excluded(self):
        self.assertEqual(self.scan_source('''
raise RuntimeError("AST scanner must not execute app modules")
from unavailable_module import Missing
class Contract:
    node_type: StrictOnWire[ConnectionNodeType]
    connection_type: ConnectionTypeKey | None
    task_type: Annotated[TaskType, "str"]
    grid_kind: Literal["world_map_light"]
    description: str
    def lookup(self, node_type: str):
        local_type: str
'''), set())

    def test_dataclass_pydantic_and_nested_classes_are_scanned(self):
        holes = self.scan_source('''
@dataclass
class Data:
    shape_type: str
class Model(BaseModel):
    class Inner:
        node_kind: str
    task_type: str
if TYPE_CHECKING:
    class Conditional:
        node_kind: str
''')
        self.assertEqual(holes, {
            ("app/contracts.py", "Data", "shape_type"),
            ("app/contracts.py", "Model.Inner", "node_kind"),
            ("app/contracts.py", "Model", "task_type"),
            ("app/contracts.py", "Conditional", "node_kind"),
        })

    def test_syntax_errors_are_not_silently_skipped(self):
        with self.assertRaises(SyntaxError):
            self.scan_source("class Broken(\n")

    def test_removing_allowlist_entry_fails_and_typing_field_makes_entry_stale(self):
        key = ("app/contracts.py", "Contract", "task_type")
        holes = self.scan_source("class Contract:\n    task_type: str\n")
        assert_no_new_holes(holes, {key: "8"})
        with self.assertRaisesRegex(AssertionError, "new bare-str"):
            assert_no_new_holes(holes, {})
        typed = self.scan_source("class Contract:\n    task_type: TaskType\n")
        with self.assertRaisesRegex(AssertionError, "debt closed"):
            assert_no_stale_holes(typed, {key: "8"})


if __name__ == "__main__":
    unittest.main()
