---
name: "source-command-impl-staircase-pojo"
description: "Имплементирует срез 6.2 плана entry-point-pojo: staircases[] → StaircaseSpec POJO (staircase_id/staircase_type/stops/ladder-поля), typed-потребители, фикс passage_height в verticalLadderValidator. Новый чат: /impl-staircase-pojo."
---

# source-command-impl-staircase-pojo

Use this skill when the user asks to run the migrated source command `impl-staircase-pojo`.

## Command Template

# Имплементация: POJO-срез 6.2 — `staircases[]` → `StaircaseSpec`

Это **явная просьба писать код** (срез 6.2 плана entry-point-pojo). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo.md`](../plans/entry-point-pojo.md) — **§6.2 инвентарь** (файлы/места) + **§6.5** баг №3; §6.1 — статус сделанного `RoomConnection` (образец среза); §1–2 — паттерн.
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) §3.7b (поля `staircases[]`, defaults, `stops`), §3.7 (фолбэк `staircase`→`doorway` — уже сделан в 6.1).
3. [`docs/tz_staircase_generation.md`](../../docs/tz_staircase_generation.md) — типы лестниц, ladder-поля, shaft-контракт.
4. Образцы реализации (уже в коде): `dataModel/structure/building/roomConnection.py` (**ближайший образец** — тот же домен), `dataModel/structure/room/entryPoint.py`, `StructureTemplate._validate_connections`/`_validate_entry_points`, `StructureGeneratorService._resolve_connections`, `tests/test_room_connection.py`.
5. Правила (нарушение = стоп): `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (**один срез за заход**: отчёт → «ок» мастера), `project-context.mdc` (DAG / backend / commit / schema = только `0001`), логирование — один фасад `loggingConfig`: emit из `app.application.worldData.generators.*` (транскрипт + core/runtime), **не** из `app.dataModel.*`.

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

`staircases[]` остаётся `list[dict]` на `StructureTemplate` (POJO-D-16); POJO `StaircaseSpec` парсится **на границах**: import-strict в model_validator шаблона + повторный `model_validate` на runtime-границе сервиса → `GenerationError`. Потребители читают typed-поля, литералы defaults уходят в `Field`/validator'ы POJO.

## Что в срезе (§6.2 + баг §6.5 №3)

**Поля** по ТЗ §3.7b и tz_staircase_generation: `staircase_id`, `staircase_type` (parse через `StaircaseType.parse_template`), `stops`, `step_material`, `on_the_edge`, `in_a_room`, `outside`, `size` (sub-POJO: `size_type`, `depth_range` fallback `width_range`), `facing`; ladder: `is_movable`, `has_trapdoor`, `near_wall`, `has_walls`, `open_wall_shaft`, `closed_exit`. `embed_in` (conditional при `in_a_room`).

**Raw-чтения → typed** (места взять из §6.2 таблицы плана; строки могли съехать после 6.1):
- `passages/builder.py` (`sc.get("staircase_id")`, `sc.get("staircase_type")`, `sc.get("stops", [])`, `sc.get("step_material")`, `sc.get("on_the_edge", False)`)
- `shaftFactory.py` (`staircase_id` дефолт, `size` sub-dict)
- `shaftPlacer.py` (`in_a_room`/`outside` → False)
- `corridorTrimmer.py` (`staircase_id` → `"?"`)
- `structureGeneratorService.py` (`staircase_id` → `"staircase"`/`"?"` в `_build_synth_conns`/`_place_level_shafts`/`_propagate_trapdoor_starts`, `stops`, `staircase_type` через `requires_shaft`)
- `staircase/builder.py` (`sc_entry` dict-чтения; **dual-schema `is_new_schema` — мёртвый старый путь удалить**: после 6.1 `connections` не несут staircase)
- `verticalLadder.py` (7 bool/enum `.get(..., False/None)`)
- `uShape.py` (`staircase_id` label default)

**Баги:**
- `verticalLadderValidator.py` `kwargs.get("passage_height", 2)` — литерал `2` вместо `world.default_passage_height` (как `builder.py:52` до E3) → дефолт POJO мира.
- `staircase_id` — **один дефолт вместо 6 мест**: ТЗ §3.7b авто-формат `staircase_{from}_{to}` (от `stops`); POJO-резолв вместо разных `"staircase"`/`"?"`/`conn_label`.

## Жёсткие запреты

- Не трогать структуру `staircases` как `list[dict]` на шаблоне (POJO-D-16) — POJO только на границах и typed-чтении внизу.
- Не менять wire-ключи и порядок генерации (RNG, порядок segments, fallback-семантику) — только typed-чтение + перечисленные баги.
- Не reopen `entry_point`/`connections` (6.1 сдан). Не `rooms[]`/`levels[]` (6.3 — отдельное «ок» мастера).
- Не трогать `structureOrientation.py` сверх необходимого (WIP шага 3c основного плана — координировать с мастером).
- Не DAG `application/engine/nodes/`. Не стартовать backend. Не коммитить, пока мастер не скажет. Не `0002_*.sql`.

## Решения, которые снести мастеру (если ТЗ молчит)

- `has_walls` default `true` по ТЗ — сверить с текущим чтением кода (shaft/ladder); расхождение → спросить.
- `facing` default: ТЗ §3.7b «шаблон, иначе NORTH» с пометкой о расхождении с целевым авто-детектом (staircase §2, сверка S0) — не решать молча; пересекается со срезом 6.4 (facing-дефолты) — возможно, оставить в 6.4.
- `embed_in` strictness при `in_a_room: true` (conditional required).
- Толерантность vs strict для `stops` (min 2, room_id существование) — по образцу мастерского решения «fallback + ERROR» для connections.

## Проверки

- `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations` + новые тесты среза
- `python -m compileall -q app tests`
- grep `sc\.get(\|sc_entry\.get(\|\.get("staircase\|\.get("stops\|\.get("step_material\|\.get("on_the_edge\|\.get("in_a_room\|\.get("outside` по staircase-домену — пусто (кроме легитимных dict-границ)
- Sweep generate по 13 `structures_templates/base/*.json` с capture `logger.error` — не хуже baseline (8 ERROR после 6.1, §3.6 «Регрессия EntryPoint E4»)
- Детерминизм: generate×2 идентичен (как `test_deterministic_ids`)

## Стиль

Минимум файлов, один срез за заход. Не рефакторить соседние домены «заодно». Pydantic-конвенции — как `roomConnection.py`/`entryPoint.py` (`StrictOnWire`/`DefaultOnWire`/`constrained_field`, `extra="forbid"`, frozen). После среза: что сделано / какие литералы убраны / что осталось + статус-строка в §6.2 плана.
