# source-command-impl-wall-openings

Use this skill when the user asks to run the migrated source command `impl-wall-openings`.

## Command Template

# Имплементация: срез 6.7 — `wall_openings` → WallOpeningSpec POJO + потребление

Это **явная просьба писать код** (срез 6.7 плана entry-point-pojo — контракт зафиксирован мастером в ТЗ 2026-10-01). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo-done.md`](../plans/entry-point-pojo-done.md) — **§6.7** (контракт среза), статусы 6.1–6.6 (сданы; паттерны подмен: `_attach_wall_substitution` в RoomDef, `ResolvedStemWall`).
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) — §3.2 поле `wall_openings` (~§282), **§3.10–3.11**: граница authored/algorithmic (позиции/количество — всегда алгоритм; authored = только `opening_type`/`frame_material`/`glass_material`/`window_z`; невалидное/отсутствие → auto-resolve + ERROR), статус-блок «не реализовано», `window_z_ratio`/`window_z_offset` на template/level (~§186, §210).
3. Код: `passages/wallOpening.py` (`place_wall_openings` — единственный потребитель: `element = StructureElement.WINDOW` хардкод OQ-17, `_GLASS_USE_TYPE`, `zadjuster.resolve`, `_opening_cell`), `passages/wallZAdjuster.py` (`ZADJUSTER_BY_TYPE`, `ProportionalWindowHeight`, `MiddleCellZAdjuster`), `dataModel/structure/room/roomDef.py` (`wall_openings: list[dict]` + substitution-паттерн), `dataModel/structure/enums/buildingElement.py` (`WALL_OPENING_ELEMENTS`), `room/roomFactory.py` (создание `_RoomInstance`), `room/roomInstance.py` (`wall_openings: list[dict]`), `cellFactory._opening_cell`.
4. Правила: `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (один срез → отчёт → «ок» мастера), `project-context.mdc` (не стартовать backend, не коммитить).

## Цель

Авторский `wall_openings` на комнате становится typed и потребляется: параметры проёмов переопределяют авто-резолв; позиции/количество остаются алгоритмическими.

## Спецификация (контракт §3.11 ТЗ — не менять)

**POJO `WallOpeningSpec`** (`dataModel/structure/room/wallOpeningSpec.py`, frozen, extra=forbid):

| Поле | Тип | Дефолт / fallback |
|---|---|---|
| `opening_type` | `StrictEnumOnWire[StructureElement]`, `∈ WALL_OPENING_ELEMENTS` | None → авто (правило room_type / WINDOW) |
| `frame_material` | `DefaultOnWire[str \| None]` | None → `room.wall_material` |
| `glass_material` | `DefaultOnWire[str \| None]` | None → `resolve_material` по тиру через `_GLASS_USE_TYPE` |
| `window_z` | `DefaultOnWire[int \| None]`, `ge=0` | None → `ZADJUSTER_BY_TYPE[element]` |

- `RoomDef.wall_openings`: `list[dict]` → `DefaultOnWire[list[WallOpeningSpec]]`.
- **Подмены** — паттерн `_attach_wall_substitution`: невалидный authored-параметр фиксируется, runtime-граница пишет централизованный **ERROR**, значение auto-resolve'ится (мир остаётся играбельным). dataModel не логирует.
- `window_z` вне диапазона комнаты (`>= room.z_height` или проём не влезает) — runtime-проверка: auto-resolve + ERROR (POJO видит только `ge=0`).
- Пустая спека `{}` — легальный no-op (все поля None), не ошибка.
- Несколько записей в массиве: **v1 — `spec[0]` применяется ко всем проёмам комнаты**; записи сверх первой → ERROR «ignored». (Семантика распределения нескольких спек по сторонам не определена в ТЗ — зафиксировать так в отчёте; если мастер уточнил иное — следовать уточнению.)

**Потребление (`wallOpening.py` + plumbing):**

```text
element      = spec.opening_type  or WINDOW            # OQ-17 baseline сохранён
glass_use    = _GLASS_USE_TYPE[element]
glass_mat    = spec.glass_material or resolve_material(world, glass_use, tier, rng, glass_use)
frame_mat    = spec.frame_material or room.wall_material   # → _opening_cell frame
z_list       = [level.z + spec.window_z .. +wh] если window_z задан (wh — высота проёма
               по ProportionalWindowHeight этого элемента), иначе zadjuster.resolve(...)
```

- `_RoomInstance.wall_openings` → `list[WallOpeningSpec]`; `roomFactory` прокидывает `room_def.wall_openings`.
- Алгоритм XY (`_zone_positions`, Правила 1–2) и фильтры (подземелье, exterior-only, shaft-skip) **не меняются**.
- `window_z` задаёт нижнюю z проёма от `level.z`; высота проёма — пропорциональная, как у `MiddleCellZAdjuster` (`int(z_height * 0.4)`).

## Границы среза

- Только: `WallOpeningSpec` POJO, `RoomDef.wall_openings` typing, `_RoomInstance` поле, `roomFactory` plumbing, `wallOpening.py` override-чтение, тесты.
- **Не трогать:** shaft-автоокна (`ShaftZAdjuster` — отдельная фаза), `OQ-13/14/15/16` (TopWall/display_facing/cell_states/arc-length — v2), `placement`-стратегии (поля нет на wire — v2+), правила по `room_type` (OQ-17 остаётся OPEN — базовый default WINDOW сохраняется), `corridorTrimmer`, остальные leftovers (host-not-placed, door_height auto-resolve, mixed L/T, EmbeddedShaftPlacer).
- Не DAG, не backend, не коммит, не `0002_*.sql`.
- Ни один stdlib-фикстур не содержит authored `wall_openings` → A/B обязан остаться идентичным (проверить grep'ом по `structures_templates/` перед sweep).

## Проверки

- Полный suite: `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations tests.test_room_def tests.test_attach_any` + новые тесты среза
- Новый тест (`tests/test_wall_opening_spec.py`): defaults/extra=forbid, подмена невалидного `opening_type`/`window_z` → substitution + ERROR на границе, override element/frame/glass/window_z в `_opening_cell`, empty-spec no-op, multi-entry → first + ERROR, underground skip сохранён, generate×2 детерминизм, шаблон не мутируется
- `python -m compileall -q app tests`; `git diff --check`
- A/B fingerprint 13 stdlib (`.local/rooms_pojo_sweep.py`-техника, артефакты `.local/wall_openings_{before,after}.json`) — **идентичен**, те же 8 ERROR

## Старт

Прочитай §6.7 плана, ТЗ §3.10–3.11 (граница authored/algorithmic + статус-блок), `wallOpening.place_wall_openings` и `roomDef`. Отчёт: поля спеки, какие параметры потреблены, семантика multi-entry, что вне среза; статус-строка в §6.7 + убрать статус-блок «не реализовано» из ТЗ §3.11.
