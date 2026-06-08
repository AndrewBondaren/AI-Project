"""
Запуск генератора здания с выводом логов.

Использование:
    python scripts/run_tavern_gen.py <template> [world] [z]
    python scripts/run_tavern_gen.py tavern_1
    python scripts/run_tavern_gen.py tavern_2 world_test
    python scripts/run_tavern_gen.py tavern_1 world_test 0
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

from datetime import datetime, timezone

from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"

# --- Аргументы: template [world] [z] ---
_args         = [a for a in sys.argv[1:] if not a.lstrip("-").isdigit()]
_z_filter     = int(sys.argv[-1]) if sys.argv[-1:] and sys.argv[-1].lstrip("-").isdigit() else None

template_name = _args[0] if len(_args) > 0 else "tavern_1"
world_name    = _args[1] if len(_args) > 1 else "world_test"

# --- Мир из фикстуры ---
world_data = json.loads((FIXTURES / f"{world_name}.json").read_text(encoding="utf-8"))
w = world_data["world"]
world = World(
    world_uid=w["world_uid"],
    name=w["name"],
    created_at=w["created_at"],
)

# --- Здание ---
building = NamedLocation(
    location_uid=f"bld-{template_name}-test-001",
    world_uid=world.world_uid,
    display_name=f"Тест: {template_name}",
    system_location_type="building",
    created_at=datetime.now(timezone.utc).isoformat(),
    map_x=10,
    map_y=10,
    map_z=0,
    parent_wall_material="stone",
    parent_floor_material="wood",
)

# --- Шаблон ---
template = json.loads((FIXTURES / "templates" / f"{template_name}.json").read_text(encoding="utf-8"))

# --- Генерация ---
svc = StructureGeneratorService()
layout = svc.generate_from_template(world, building, template)

# --- Итог ---
print("\n=== РЕЗУЛЬТАТ ===")
print(f"Уровней:   {len(layout.levels)}")
print(f"Комнат:    {len(layout.rooms)}")
print(f"Ячеек:     {len(layout.cells)}")
print(f"Проходов:  {len(layout.passages)}")

print("\n--- Уровни ---")
for lvl in sorted(layout.levels, key=lambda l: l.z):
    print(f"  z={lvl.z:+d}  z_height={lvl.z_height}  '{lvl.display_name}'")

print("\n--- Комнаты ---")
for room in layout.rooms:
    print(f"  [{room.system_location_subtype}] '{room.display_name}'  origin=({room.map_x},{room.map_y})  z={room.map_z}")

print("\n--- Проходы ---")
for p in layout.passages:
    fr = p.from_level_uid or "exterior"
    print(f"  {p.system_passage_type}  {fr} -> {p.to_level_uid}  to=({p.to_x},{p.to_y})")

print("\n--- Элементы ячеек ---")
from collections import Counter
counts = Counter(c.system_building_element for c in layout.cells)
for elem, n in sorted(counts.items()):
    print(f"  {elem}: {n}")
railing_cells = [(c.x, c.y, c.z, c.railing_sides) for c in layout.cells if c.railing_sides]
print(f"  [railing cells: {len(railing_cells)}]")
for rc in sorted(railing_cells):
    print(f"    ({rc[0]},{rc[1]},z={rc[2]}) {rc[3]}")

from app.application.worldData.generators.structure._gridRenderer import render_level, render_all_levels
from app.application.worldData.generators.structure._passageBuilder import _spiral_perimeter

level_uid_to_z = {lvl.level_uid: lvl.z for lvl in layout.levels}
anchor_dirs_by_z: dict[int, dict[tuple[int, int], str]] = {}

_MOVE_SYM: dict[tuple[int, int], str] = {
    (0, 1): "↑", (1, 0): "→", (0, -1): "↓", (-1, 0): "←",
}

def _add_dir(z, x, y, direction):
    if z is None or x is None:
        return
    d = anchor_dirs_by_z.setdefault(z, {})
    existing = d.get((x, y))
    d[(x, y)] = "↕" if (existing and existing != direction) else direction

for p in layout.passages:
    if p.system_passage_type != "staircase":
        continue
    fr_z = level_uid_to_z.get(p.from_level_uid)
    to_z = level_uid_to_z.get(p.to_level_uid)
    if fr_z is None or to_z is None or p.from_x is None:
        continue

    # Спиральная лестница: from_anchor == to_anchor
    if p.from_x == p.to_x and p.from_y == p.to_y:
        z_lo_p, z_hi_p = min(fr_z, to_z), max(fr_z, to_z)
        z_h = z_hi_p - z_lo_p
        perimeter = _spiral_perimeter(p.to_x, p.to_y, 2, 2)
        n = len(perimeter)
        # Trail-стрелки: ступень k → trail на z_s+1
        for k in range(z_h):
            sx, sy = perimeter[(k + 1) % n]
            nx, ny = perimeter[(k + 2) % n]
            sym = _MOVE_SYM.get((nx - sx, ny - sy), "?")
            z_trail = z_lo_p + k + 1
            if z_lo_p <= z_trail < z_hi_p:
                anchor_dirs_by_z.setdefault(z_trail, {})[(sx, sy)] = sym
        # Вход C0 на z_lo, выход perimeter[z_h % n] на z_hi
        ex, ey = perimeter[z_h % n]
        _add_dir(z_lo_p, p.to_x, p.to_y, "↑" if to_z > fr_z else "↓")
        _add_dir(z_hi_p, ex, ey, "↓" if fr_z < to_z else "↑")
    else:
        _add_dir(fr_z, p.from_x, p.from_y, "↑" if to_z > fr_z else "↓")
        _add_dir(to_z, p.to_x, p.to_y, "↓" if fr_z < to_z else "↑")

if _z_filter is not None:
    labels = {-3: "Подвал", 0: "Первый этаж", 3: "Второй этаж"}
    label  = labels.get(_z_filter, f"z={_z_filter}")
    grid = render_level(layout.cells, z_target=_z_filter, anchor_dirs=anchor_dirs_by_z.get(_z_filter))
    if grid:
        print(f"\n--- Сетка: {label} (z={_z_filter}) ---")
        print(grid)
    else:
        print(f"\n[{label}] нет ячеек на z={_z_filter}")
else:
    all_z = sorted({c.z for c in layout.cells})
    level_z_set = {lvl.z for lvl in layout.levels}
    floor_names = ["Первый этаж", "Второй этаж", "Третий этаж", "Четвёртый этаж",
                   "Пятый этаж", "Шестой этаж"]
    floor_idx = 0
    level_labels: dict[int, str] = {}
    for lvl in sorted(layout.levels, key=lambda l: l.z):
        if lvl.z < 0:
            level_labels[lvl.z] = "Подвал"
        else:
            level_labels[lvl.z] = floor_names[floor_idx] if floor_idx < len(floor_names) else f"Этаж {floor_idx+1}"
            floor_idx += 1
    for z in all_z:
        tag = f" [{level_labels[z]}]" if z in level_labels else " [промежуточный]"
        marker = "★" if z in level_z_set else "·"
        grid = render_level(layout.cells, z_target=z, anchor_dirs=anchor_dirs_by_z.get(z))
        print(f"\n{marker} z={z:+d}{tag}")
        print(grid if grid else "  (нет ячеек)")
