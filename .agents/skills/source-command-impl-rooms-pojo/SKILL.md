---
name: "source-command-impl-rooms-pojo"
description: "Имплементирует срез 6.3 плана entry-point-pojo: rooms[]/levels[] → RoomDef/LevelDef/SizeSpec/ShapeParams POJO (room_def ~18 полей, level_def), typed-потребители roomFactory/shapeResolver/layoutEngine/service. Новый чат: /impl-rooms-pojo."
---

# source-command-impl-rooms-pojo

Use this skill when the user asks to run the migrated source command `impl-rooms-pojo`.

## Command Template

# Имплементация: POJO-срез 6.3 — `rooms[]`/`levels[]` → `RoomDef`/`LevelDef`/`SizeSpec`/`ShapeParams`

Это **явная просьба писать код** (срез 6.3 плана entry-point-pojo). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo.md`](../plans/entry-point-pojo.md) — **§6.3 инвентарь** (файлы/места; номера строк могли съехать после 6.1/6.2); §6.1/§6.2 — статусы сделанных срезов (`RoomConnection`, `StaircaseSpec` — **образцы среза**); §4 — найденные расхождения.
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) §3.4 (levels), §3.5 (`size` — три взаимоисключающие формы), §3.5b (`shape_params` l_shape/t_shape), §3.7 (entry_point/back_entry_point — уже POJO), §2.1/purpose (room_purposes — CITY-T-5n/5o).
3. Образцы реализации (уже в коде): `dataModel/structure/building/roomConnection.py`, `dataModel/structure/building/staircaseSpec.py` (вкл. `ShaftSize` — тот же паттерн size-форм), `dataModel/structure/room/entryPoint.py`, `StructureTemplate._validate_connections`/`_validate_staircases`, `StructureGeneratorService._resolve_connections`/`_resolve_staircases`, `tests/test_room_connection.py`, `tests/test_staircase_spec.py`.
4. Правила (нарушение = стоп): `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (**один срез за заход**: отчёт → «ок» мастера), `project-context.mdc` (DAG / backend / commit / schema = только `0001`), логирование — emit только из `app.application.worldData.generators.*`, **не** из `app.dataModel.*`.

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

`rooms[]`/`levels[]` остаются `list[dict]` на `StructureTemplate` (POJO-D-16); POJO парсятся **на границах**: import-strict в model_validator шаблона + повторный `model_validate` на runtime-границе сервиса → `GenerationError`. Потребители читают typed-поля, литералы defaults уходят в `Field`/validator'ы POJO.

## Что в срезе (§6.3)

**`RoomDef`** (~18 полей wire): `room_id`, `display_name`, `room_type`, `is_public`, `is_forbidden`, `required`, `count`, `economic_tier`, `attach_to`, `attach_wall`, `perimeter_required`, `underground_fallback`, `staircase_type`, `facing`, `size` (→ `SizeSpec`), `shape_params` (→ `ShapeParams`), `entry_point`, `back_entry_point` (→ существующий `EntryPoint` POJO — переиспользовать, не дублировать), `purpose`.

**`LevelDef`**: `z_offset`, `z_height`, `isolated`, `access_mechanic`, `rooms`, `purpose`.

**`SizeSpec`**: три формы §3.5 — `size_type` ⊥ явные `width_range`/`depth_range`; `z_range` допустим поверх `size_type`. Пресеты — из dataModel (как `staircaseSize.py` для шахт — искать существующий enum/registry, не плодить литералы).

**`ShapeParams`**: `l_shape` (`arm_width_range`, `arm_depth_range`, `arm_corner`), `t_shape` (`stem_width_range`, `stem_wall`).

**Raw-чтения → typed** (инвентарь §6.3 плана; проверить актуальные строки grep'ом):

- `roomFactory.py` — `size` sub-dict (`depth_range`/`z_range` → `[3,3]` литералы), `shape_params` (`arm_*_range`/`stem_width_range` → `[2,3]`, `arm_corner`/`stem_wall` → `"any"`), `count` → `1`, `staircase_type`, `facing`, остальные `.get` по room_def

**Strict по ТЗ (решение мастера 2026-09-30) — доктрина границ:**

Продуктовое правило: **игрок не должен терять мир из-за косяка шаблона**. Поэтому strict — **только на импорте** (канал автора-мастера), а в рантайме — degrade, не падение:

| Ситуация | Import-граница | Runtime-граница |
|---|---|---|
| Required-поле/условие нарушено | `ValidationError` — отклонить | не должно случаться; иначе `GenerationError` |
| Значение задано, но битое, есть фолбэк | coerce + пометка | coerce **+ ERROR в транскрипт** (не silent) |
| Ссылка битая (`attach_to`/`embed_in` → нет такого room_id) | reject — `attach_to` должен существовать | skip объекта **+ ERROR** (не WARNING — тонет), генерация продолжается |
| Documented default, поле не задано | применить, **тихо** | тихо — это контракт, не подмена |

Любая **подмена заданного автором значения** — всегда лог; применение дефолта к **незаданному** — без лога.

- `attach_wall` — **required при `attach_to`** (ТЗ §3.4): сейчас отсутствие молча → `"both"` (`layoutEngine:374`); import-strict. Значения `both`/`any` легальны.
- `shape_params` — **required при `shape_type` l_shape/t_shape** (ТЗ §3.5b); `arm_width_range`/`arm_depth_range`/`stem_width_range` — required внутри; `[2,3]`-фолбэки удалить. **Нюанс:** `shape_type` бывает массивом (`["square","rectangle"]` — rng выбирает) — правило срабатывает если **любой** элемент = l_shape/t_shape.
- Кросс-валидация §455: `stem_width_range[1] < size.width_range[0]` → ValidationError (в коде отсутствует — добавить).
- Не отклонять: `shape_params` при shape не l_shape/t_shape — ТЗ «игнорируется» → accept (как embed-поля в StaircaseSpec). Defaults `arm_corner`/`stem_wall` = `"any"` — легальны по ТЗ, остаются POJO-дефолтами.
- **Латентные баги (НЕ чинить в этом срезе — меняют генерацию):** `attach_wall: "any"` код резолвит по ориентации хоста, а ТЗ §1641–1644 — по позиции лестницы в коридоре; host-not-placed — WARNING вместо ERROR (`layoutEngine:371`). Зафиксировать как открытые вопросы мастеру.
- `shapeResolver.py` — `width_range` → `[1,1]`
- `structureGeneratorService.py` — `level_def.get("z_height") or default` (**`or` проглатывает falsy — `0` легален? вопрос мастеру**), `isolated` → `False`, `access_mechanic` → `[]`, `z_offset`
- `layoutEngine.py` — `attach_wall or "both"` строковый литерал; `attach_to`/`perimeter_required`/`underground_fallback`
- `instantiate_level_rooms` — сигнатура `level_def: dict` → typed
- sweep по `.get("room_id"`, `.get("display_name"`, `.get("room_type"`, `.get("required"`, `.get("count"`, `.get("attach` и т.д. в `generators/structure/` — добить хвосты

## Жёсткие запреты

- `rooms[]`/`levels[]` остаются `list[dict]` на шаблоне (POJO-D-16) — POJO только на под-словарях и на границах.
- Не менять wire-ключи, порядок генерации (RNG-поток!), runtime-fallback-семантику — только typed-чтение. **Исключение — решение мастера:** required-поля по ТЗ отклоняются **на импорте** (см. «Strict по ТЗ» выше); runtime остаётся degrade+ERROR — игрок не теряет мир.
- **RNG-осторожность:** комната за комнатой резолвится из общего `rng` — порядок/число вызовов `rng.*` не должен измениться. Проверка — A/B fingerprint (см. Проверки).
- Не reopen `entry_point`/`connections`/`staircases` (6.1/6.2 сданы). Не facing-дефолты изолированных мест (6.4 — отдельный срез).
- Не трогать `structureOrientation.py` сверх необходимого (WIP шага 3c основного плана — координировать с мастером).
- Не DAG `application/engine/nodes/`. Не стартовать backend. Не коммитить, пока мастер не скажет. Не `0002_*.sql`.

## Решения, которые снести мастеру (если ТЗ молчит)

- `z_height`: `or`-falsy — легален ли `0`? (§6.3 инвентарь)
- Дефолты `depth_range`/`z_range` `[3,3]` (size без size_type: ТЗ §3.5 говорит `depth_range` обязателен — strict? `z_range` default `(3,3)` легален), `width_range` `[1,1]` в shapeResolver — легитимный POJO-default или strict-required?
- `count` → `1` — то же.
- `attach_wall: "any"` — семантика ТЗ §1641–1644 (позиция лестницы) vs код (ориентация хоста): баг поведения, чинить отдельно.
- Строгость `rooms[]`: дубли `room_id`, неизвестный `attach_to`, `required`-семантика, `stops`↔room_id связность — какие проверки на import vs tolerant+ERROR на runtime-границе (по образцу мастерского решения для connections).
- `purpose`/`room_purposes()` — уже есть потребитель в dataModel (CITY-T-5n/5o) — не дублировать.

## Проверки

- `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations` + новые тесты среза
- `python -m compileall -q app tests`
- grep `.get("` по room/level-домену в `generators/structure/` — пусто (кроме легитимных dict-границ и kwargs-параметров)
- **A/B fingerprint (обязательно для этого среза — меняется главный потребитель):** до правок снять `sha256(cells+passages)` по всем 13 `structures_templates/base/*.json` на текущем коде; после — сравнить побайтово. Техника: `git checkout HEAD -- <мои файлы>`/`cp` backup → sweep → restore (шаблон скрипта — generate per template, `world_uid="entry-sweep-world"`, `building_uid="entry-sweep-"+system_name`, map=(0,0,0), capture `logger.error` + hash layout)
- Sweep ERROR по 13 stdlib — не хуже baseline (8 ERROR, §6.1 статус)
- Детерминизм: generate×2 идентичен (как `test_deterministic_ids`)

## Стиль

Минимум файлов, один срез за заход. Pydantic-конвенции — как `roomConnection.py`/`staircaseSpec.py`/`entryPoint.py` (`StrictOnWire`/`DefaultOnWire`/`StrictEnumOnWire`, `extra="forbid"`, frozen). `EntryPoint` для `entry_point`/`back_entry_point` — встраивать существующий POJO, не переписывать. После среза: что сделано / какие литералы убраны / что осталось + статус-строка в §6.3 плана.

## Старт

Прочитай план §6.3 + §6.1/§6.2 (образцы), ТЗ §3.4/§3.5/§3.5b, `roomFactory.py`/`shapeResolver.py`/`layoutEngine.py`/`instantiate_level_rooms`. Сними A/B fingerprint **до** правок.
