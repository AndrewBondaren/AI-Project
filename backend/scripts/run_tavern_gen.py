"""
Запуск генератора таверны с выводом логов.

Использование:
    python scripts/run_tavern_gen.py
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

# --- Мир из фикстуры ---
world_data = json.loads((FIXTURES / "world_test.json").read_text(encoding="utf-8"))
w = world_data["world"]
world = World(
    world_uid=w["world_uid"],
    name=w["name"],
    created_at=w["created_at"],
)

# --- Здание-таверна ---
building = NamedLocation(
    location_uid="bld-tavern-test-001",
    world_uid=world.world_uid,
    display_name="Таверна «Золотой грифон»",
    system_location_type="building",
    created_at=datetime.now(timezone.utc).isoformat(),
    map_x=10,
    map_y=10,
    map_z=0,
    parent_wall_material="stone",
    parent_floor_material="wood",
)

# --- Шаблон таверны ---
template = json.loads((FIXTURES / "templates" / "tavern_1.json").read_text(encoding="utf-8"))

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

from app.application.worldData.generators.structure._gridRenderer import render_level, render_all_levels

if len(sys.argv) > 1 and sys.argv[1] == "all":
    # Все z-уровни включая промежуточные (лестницы)
    all_z = sorted({c.z for c in layout.cells})
    level_z_set = {lvl.z for lvl in layout.levels}
    labels = {-3: "Подвал", 0: "Первый этаж", 3: "Второй этаж"}
    for z in all_z:
        tag = f" [{labels[z]}]" if z in labels else " [промежуточный]"
        marker = "★" if z in level_z_set else "·"
        grid = render_level(layout.cells, z_target=z)
        print(f"\n{marker} z={z:+d}{tag}")
        print(grid if grid else "  (нет ячеек)")
else:
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    labels = {-3: "Подвал", 0: "Первый этаж", 3: "Второй этаж"}
    label  = labels.get(target, f"z={target}")
    grid = render_level(layout.cells, z_target=target)
    if grid:
        print(f"\n--- Сетка: {label} (z={target}) ---")
        print(grid)
    else:
        print(f"\n[{label}] нет ячеек на z={target}")
