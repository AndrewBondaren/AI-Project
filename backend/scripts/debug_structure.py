"""
Универсальный скрипт для тестирования генерации структур через debug API.

Использование:
    python scripts/debug_structure.py <template> [options]

Примеры:
    python scripts/debug_structure.py ../fixtures/templates/tavern_1.json
    python scripts/debug_structure.py ../fixtures/templates/tavern_1.json --world ../fixtures/world_test.json
    python scripts/debug_structure.py ../fixtures/templates/tavern_1.json --world world-test-001
    python scripts/debug_structure.py ../fixtures/templates/tavern_1.json --x 5 --y 5 --z 0 --all
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import httpx

BASE_URL = "http://localhost:8000/api"


async def ensure_world(client: httpx.AsyncClient, world_source: str) -> str:
    """
    Создаёт мир если нужно. world_source — либо uid (строка без .json),
    либо путь к файлу фикстуры мира.
    Возвращает world_uid.
    """
    if not world_source.endswith(".json"):
        # Передан uid — проверяем что мир существует
        r = await client.get(f"{BASE_URL}/worlds/{world_source}")
        if r.status_code == 200:
            return world_source
        print(f"[!] Мир '{world_source}' не найден — создаю минимальный")
        return await _create_minimal_world(client, world_source)

    # Передан путь к файлу фикстуры
    fixture_path = Path(world_source)
    if not fixture_path.exists():
        print(f"[!] Файл фикстуры не найден: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Поддерживаем формат world_test.json ({"world": {...}}) и plain ({...})
    world_data = data.get("world", data)
    world_uid = world_data.get("world_uid")
    if not world_uid:
        print("[!] Нет world_uid в фикстуре", file=sys.stderr)
        sys.exit(1)

    # Проверяем есть ли уже
    r = await client.get(f"{BASE_URL}/worlds/{world_uid}")
    if r.status_code == 200:
        print(f"[✓] Мир '{world_uid}' уже существует")
        return world_uid

    # Создаём
    r = await client.post(f"{BASE_URL}/worlds", json=world_data)
    if r.status_code not in (200, 201):
        print(f"[!] Не удалось создать мир: {r.status_code} {r.text[:300]}", file=sys.stderr)
        sys.exit(1)

    print(f"[+] Мир '{world_uid}' создан")
    return world_uid


async def _create_minimal_world(client: httpx.AsyncClient, world_uid: str) -> str:
    from datetime import datetime, timezone
    data = {
        "world_uid": world_uid,
        "name": world_uid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "material_registry": [
            {"system_material": "stone",  "use_types": ["wall", "floor"], "economic_tier": "poor"},
            {"system_material": "wood",   "use_types": ["wall", "floor"], "economic_tier": "poor"},
            {"system_material": "brick",  "use_types": ["wall", "floor"], "economic_tier": "modest"},
            {"system_material": "oak",    "use_types": ["wall", "floor"], "economic_tier": "modest"},
            {"system_material": "marble", "use_types": ["wall", "floor"], "economic_tier": "wealthy"},
        ],
    }
    r = await client.post(f"{BASE_URL}/worlds", json=data)
    if r.status_code not in (200, 201):
        print(f"[!] Не удалось создать мир: {r.text[:300]}", file=sys.stderr)
        sys.exit(1)
    print(f"[+] Минимальный мир '{world_uid}' создан")
    return world_uid


async def run(args: argparse.Namespace) -> None:
    template_path = Path(args.template)
    if not template_path.exists():
        print(f"[!] Шаблон не найден: {template_path}", file=sys.stderr)
        sys.exit(1)

    async with httpx.AsyncClient(timeout=30) as client:
        world_uid = await ensure_world(client, args.world)

        params = {"map_x": args.x, "map_y": args.y, "map_z": args.z}
        if args.wall:
            params["wall_material"] = args.wall
        if args.floor:
            params["floor_material"] = args.floor
        if args.verbose:
            params["verbose"] = "true"

        print(f"\n[→] Генерация: world={world_uid}  template={template_path.name}  pos=({args.x},{args.y},{args.z})\n")

        with open(template_path, "rb") as f:
            r = await client.post(
                f"{BASE_URL}/debug/worlds/{world_uid}/generate-structure",
                params=params,
                files={"file": (template_path.name, f, "application/json")},
            )

        if r.status_code != 200:
            print(f"[!] Ошибка {r.status_code}:", r.text[:2000], file=sys.stderr)
            sys.exit(1)

        data = r.json()

    _print_results(data, show_all=args.all, target_z=args.show_z, verbose=args.verbose)


_STAIR_TYPES  = {"staircase", "stair_anchor", "stair_floor"}
_LADDER_TYPES = {"ladder", "trapdoor"}


def _print_results(data: dict, show_all: bool, target_z: int | None, verbose: bool = False) -> None:
    s = data["summary"]
    print("=== ИТОГ ===")
    print(f"  Уровней:  {s['levels']}")
    print(f"  Комнат:   {s['rooms']}")
    print(f"  Ячеек:    {s['cells']}")
    print(f"  Проходов: {s['passages']}")
    print(f"  Элементы: {s['elements']}")

    print("\n--- Уровни ---")
    for lvl in data["levels"]:
        print(f"  z={lvl['z']:+d}  z_height={lvl['z_height']}  '{lvl['display_name']}'")

    print("\n--- Проходы ---")
    for p in data["passages"]:
        if p["system_passage_type"] == "staircase":
            continue
        fr = p["from_level_uid"] or "exterior"
        print(f"  {p['system_passage_type']:12s}  {fr} → {p['to_level_uid']}  to=({p['to_xy'][0]},{p['to_xy'][1]})")

    validation = data.get("validation", {})
    warnings = validation.get("warnings", [])
    label = "--- Логи генерации ---" if verbose else f"--- Предупреждения ({validation.get('count', 0)}) ---"
    if warnings or verbose:
        print(f"\n{label}")
        for w in warnings:
            print(f"  {w}")

    print("\n--- Лестница: все ячейки ---")
    level_z = {lvl["level_uid"]: lvl["z"] for lvl in data["levels"]}
    cells = data["cells"]
    rows: list[tuple[int, int, int, str, str | None]] = [
        (c["x"], c["y"], c["z"], "fr_anchor" if c["element"] == "stair_anchor" else c["element"], c.get("facing"))
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

    if target_z is not None:
        key = str(target_z)
        grid = grids.get(key, "")
        print(f"\n--- Сетка z={target_z} ---")
        print(grid if grid else "  (нет ячеек)")
        return

    z_with_cells = {int(z): grid for z, grid in grids.items()}

    if z_with_cells:
        z_lo = min(z_with_cells)
        z_hi = max(z_with_cells)
    else:
        return

    for z in range(z_lo, z_hi + 1):
        tag = "" if z in level_zs else " [промежуточный]"
        grid = z_with_cells.get(z, "")
        print(f"\n=== z={z:+d}{tag} ===")
        print(grid if grid else "  (нет ячеек)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug: генерация структуры через API")
    parser.add_argument("template", help="Путь к JSON-шаблону (напр. ../fixtures/templates/tavern_1.json)")
    parser.add_argument("--world", default="../fixtures/world_test.json",
                        help="Путь к фикстуре мира или world_uid (default: ../fixtures/world_test.json)")
    parser.add_argument("--x",     type=int, default=10, help="map_x (default: 10)")
    parser.add_argument("--y",     type=int, default=10, help="map_y (default: 10)")
    parser.add_argument("--z",     type=int, default=0,  help="map_z (default: 0)")
    parser.add_argument("--wall",  default=None, help="wall_material (default: stone)")
    parser.add_argument("--floor", default=None, help="floor_material (default: wood)")
    parser.add_argument("--all",   action="store_true", help="Показать все z включая промежуточные лестницы")
    parser.add_argument("--show-z", type=int, default=None, metavar="Z",
                        help="Показать только конкретный z-уровень")
    parser.add_argument("--verbose", action="store_true",
                        help="Показать DEBUG/INFO логи генерации")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
