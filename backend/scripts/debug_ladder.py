"""
Запуск генератора здания с детальным выводом ladder/stair данных через API.

Использование:
    python scripts/debug_ladder.py <template> [world] [z]

Примеры:
    python scripts/debug_ladder.py manor_1
    python scripts/debug_ladder.py manor_1 world_test
    python scripts/debug_ladder.py manor_1 world_test -3
"""
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import httpx

BASE_URL  = "http://localhost:8000/api"
FIXTURES  = Path(__file__).parent.parent.parent / "fixtures"
_OUT_FILE = Path(__file__).parent / "last_output.txt"

_STAIR_TYPES  = {"staircase", "stair_anchor", "stair_floor"}
_LADDER_TYPES = {"ladder", "trapdoor"}


def _parse_args():
    args      = sys.argv[1:]
    z_filter  = None
    rest      = []
    for a in args:
        stripped = a.lstrip("-")
        if stripped.lstrip("0123456789") == "" and a.startswith("-") and len(a) > 1:
            z_filter = int(a)
        else:
            rest.append(a)
    template  = rest[0] if len(rest) > 0 else "manor_1"
    world     = rest[1] if len(rest) > 1 else "world_test"
    return template, world, z_filter


async def ensure_world(client: httpx.AsyncClient, world_name: str) -> str:
    fixture = FIXTURES / f"{world_name}.json"
    if fixture.exists():
        data = json.loads(fixture.read_text(encoding="utf-8"))
        world_data = data.get("world", data)
        world_uid  = world_data["world_uid"]

        r = await client.get(f"{BASE_URL}/worlds/{world_uid}")
        if r.status_code == 200:
            print(f"[✓] Мир '{world_uid}' уже существует")
            return world_uid

        r = await client.post(f"{BASE_URL}/worlds", json=world_data)
        if r.status_code not in (200, 201):
            print(f"[!] Не удалось создать мир: {r.status_code} {r.text[:300]}", file=sys.stderr)
            sys.exit(1)
        print(f"[+] Мир '{world_uid}' создан")
        return world_uid

    # Передан uid напрямую
    r = await client.get(f"{BASE_URL}/worlds/{world_name}")
    if r.status_code == 200:
        return world_name
    print(f"[!] Мир '{world_name}' не найден", file=sys.stderr)
    sys.exit(1)


async def run() -> None:
    template_name, world_name, z_filter = _parse_args()

    template_path = FIXTURES / "templates" / f"{template_name}.json"
    if not template_path.exists():
        print(f"[!] Шаблон не найден: {template_path}", file=sys.stderr)
        sys.exit(1)

    async with httpx.AsyncClient(timeout=30) as client:
        world_uid = await ensure_world(client, world_name)

        print(f"\n[→] Генерация: world={world_uid}  template={template_name}.json\n")

        with open(template_path, "rb") as f:
            r = await client.post(
                f"{BASE_URL}/debug/worlds/{world_uid}/generate-structure",
                files={"file": (template_path.name, f, "application/json")},
            )

        if r.status_code != 200:
            print(f"[!] Ошибка {r.status_code}:", r.text[:2000], file=sys.stderr)
            sys.exit(1)

        data = r.json()

    _print_results(data, z_filter)


def _print_results(data: dict, z_filter: int | None) -> None:
    s = data["summary"]
    print("=== РЕЗУЛЬТАТ ===")
    print(f"Уровней:   {s['levels']}")
    print(f"Комнат:    {s['rooms']}")
    print(f"Ячеек:     {s['cells']}")
    print(f"Проходов:  {s['passages']}")

    print("\n--- Уровни ---")
    for lvl in data["levels"]:
        print(f"  z={lvl['z']:+d}  z_height={lvl['z_height']}  '{lvl['display_name']}'")

    print("\n--- Комнаты ---")
    for room in data["rooms"]:
        o = room["origin"]
        print(f"  [{room['system_location_subtype']}] '{room['display_name']}'  "
              f"origin=({o['x']},{o['y']})  z={o['z']}")

    print("\n--- Проходы ---")
    for p in data["passages"]:
        fr  = p["from_level_uid"] or "exterior"
        txy = p["to_xy"]
        print(f"  {p['system_passage_type']}  {fr} -> {p['to_level_uid']}  to=({txy[0]},{txy[1]})")

    cells = data["cells"]

    print("\n--- Элементы ячеек ---")
    counts = Counter(c["element"] for c in cells)
    for elem, n in sorted(counts.items()):
        print(f"  {elem}: {n}")
    railing_cells = [(c["x"], c["y"], c["z"], c["railing"]) for c in cells if c.get("railing")]
    print(f"  [railing cells: {len(railing_cells)}]")
    for rc in sorted(railing_cells):
        print(f"    ({rc[0]},{rc[1]},z={rc[2]}) {rc[3]}")

    validation = data.get("validation", {})
    warnings   = validation.get("warnings", [])
    print(f"\n--- Валидация ({validation.get('count', 0)} предупреждений) ---")
    if warnings:
        for w in warnings:
            print(f"  ⚠  {w}")
    else:
        print("  ОК")

    # Spot-check: tunnel exit at z=-2 and z=-1
    spot_coords = [(23, 10, -2), (23, 10, -1), (22, 10, -2), (22, 10, -1)]
    spot_map = {(c["x"], c["y"], c["z"]): c["element"] for c in cells}
    spot_hits = [(x, y, z, spot_map.get((x, y, z), "<MISSING>")) for x, y, z in spot_coords]
    print("\n--- Spot check ячеек (23,10) и (22,10) ---")
    for x, y, z, elem in spot_hits:
        print(f"  ({x},{y},z={z:+d}): {elem}")

    print("\n--- Лестница: все ячейки ---")
    level_z = {lvl["level_uid"]: lvl["z"] for lvl in data["levels"]}
    rows: list[tuple[int, int, int, str, str | None]] = [
        (c["x"], c["y"], c["z"], c["element"], c.get("facing"))
        for c in cells if c["element"] in _STAIR_TYPES | _LADDER_TYPES
    ]
    for p in data["passages"]:
        if p["system_passage_type"] != "staircase":
            continue
        tz = level_z.get(p["to_level_uid"], 0)
        rows.append((p["to_xy"][0], p["to_xy"][1], tz, "to_anchor", None))
    if rows:
        for x, y, z, t, facing in sorted(rows, key=lambda c: (c[2], c[0], c[1])):
            f = f"facing={facing}" if facing else ""
            print(f"  ({x},{y},z={z:+d}) {t:<14} {f}".rstrip())
    else:
        print("  (нет ячеек)")

    grids: dict[str, str] = data["grids"]
    level_zs = {lvl["z"] for lvl in data["levels"]}

    floor_names = ["Первый этаж", "Второй этаж", "Третий этаж",
                   "Четвёртый этаж", "Пятый этаж", "Шестой этаж"]
    floor_idx = 0
    level_labels: dict[int, str] = {}
    for lvl in sorted(data["levels"], key=lambda l: l["z"]):
        if lvl["z"] < 0:
            level_labels[lvl["z"]] = "Подвал"
        else:
            level_labels[lvl["z"]] = floor_names[floor_idx] if floor_idx < len(floor_names) else f"Этаж {floor_idx+1}"
            floor_idx += 1

    if z_filter is not None:
        grid = grids.get(str(z_filter), "")
        label = level_labels.get(z_filter, f"z={z_filter}")
        print(f"\n--- Сетка: {label} (z={z_filter:+d}) ---")
        print(grid if grid else "  (нет ячеек)")
        return

    all_z = sorted(int(z) for z in grids)
    for z in all_z:
        tag    = f" [{level_labels[z]}]" if z in level_labels else " [промежуточный]"
        marker = "★" if z in level_zs else "·"
        grid   = grids.get(str(z), "")
        print(f"\n{marker} z={z:+d}{tag}")
        print(grid if grid else "  (нет ячеек)")


def main() -> None:
    import io

    file_handle = open(_OUT_FILE, "w", encoding="utf-8")

    class _Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s)
            file_handle.write(s)
            return len(s)
        def flush(self):
            sys.__stdout__.flush()
            file_handle.flush()

    sys.stdout = _Tee()
    try:
        asyncio.run(run())
    finally:
        sys.stdout = sys.__stdout__
        file_handle.close()


if __name__ == "__main__":
    main()
