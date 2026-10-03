---
name: "source-command-impl-structure-pojo"
description: "Имплементирует оставшиеся POJO-срезы структурного генератора по плану entry-point-pojo §6: RoomDef/LevelDef/SizeSpec/ShapeParams (rooms[]/levels[]) и facing-дефолты. connections[]/staircases[] уже сданы. Новый чат: /impl-structure-pojo; для §6.3 — dedicated /impl-rooms-pojo."
---

# source-command-impl-structure-pojo

Use this skill when the user asks to run the migrated source command `impl-structure-pojo`.

## Command Template

# Имплементация: POJO-срезы структурного генератора (по entry-point-pojo §6)

Это **явная просьба писать код** (срезы §6 плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo-done.md`](../plans/entry-point-pojo-done.md) — **§6 инвентарь** (что чинить, по файлам/строкам); §1–2 — паттерн `EntryPoint` как образец; §4 — найденные расхождения.
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) §3.6 (entry_point — сделано), §3.7 (connections: поля, `door_height`, запрет `staircase`), §3.7b (staircases).
3. [`docs/tz_staircase_generation.md`](../../docs/tz_staircase_generation.md) — поля `staircases[]` / ladder.
4. Образец реализации (уже в коде): `dataModel/locations/structure/room/entryPoint.py`, `dataModel/locations/structure/enums/entryAccessType.py`, `StructureTemplate._validate_entry_points`, `roomFactory` parse → `GenerationError`.
5. Правила (нарушение = стоп): `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (**один срез за заход**: отчёт → «ок» мастера → следующий), `project-context.mdc` (DAG / backend / commit / schema = только `0001`).

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

Перевести оставшиеся `list[dict]` домены `StructureTemplate` на sub-POJO по паттерну `EntryPoint`: parse на границе (`StructureTemplate` model_validator — import-strict; factory/builder — повторный `model_validate` → `GenerationError`), потребители читают typed-поля, литералы defaults уходят в `Field`/`DefaultOnWire`/`StrictEnumOnWire`. Попутно чинятся баги §6.5 плана.

## Жёсткие запреты

- **Не трогать структуру `levels`/`rooms`/`staircases`/`connections` как `list[dict]`** (POJO-D-16) — POJO только на под-словарях и на границе.
- Не менять wire-ключи и не вводить алиасы (`height` **не** алиас `door_height` — ТЗ §3.6 прямо запрещает).
- Не reopen EntryPoint (E1–E3 сделаны и проверены — §3 плана).
- Не трогать `structureOrientation.py` сверх замены `entry.get(...)` на typed-поля — файл WIP шага 3c основного плана (untracked); координировать с мастером.
- Не DAG `application/engine/nodes/`. Не стартовать backend. Не коммитить, пока мастер не скажет. Не `0002_*.sql`.
- Не менять поведение генерации (порядок RNG, порядок connections/staircases, fallback-семантику) — только typed-чтение + перечисленные баги §6.5.
- Не расползаться: `rooms[]` целиком (6.3) — только по явному «ок» мастера после 6.1/6.2.

## Порядок срезов

| # | Срез | Что | Статус |
|---|---|---|---|
| 0 | **E4** — docs sync + sweep | `tz_building_generator.md`: wire-ключ `door_height`, поля ratio/max; §286 форсинг | ✅ фактически закрыт вместе с 6.1 (docs + sweep 8 ERROR) |
| 1 | **6.1** `RoomConnection` POJO | `roomConnection.py`, typed-потребители, баги `door_height`/archway frame | ✅ **сдано 2026-09-29** — §6.1 статус. NB: `passage_type` **не** reject — коерсится в `doorway` + ERROR на границе (решение мастера) |
| 2 | **6.2** `StaircaseSpec` POJO | `staircaseSpec.py` + `ShaftSize`, typed-потребители, `embed_at` v1 | ✅ **сдано 2026-09-30** — §6.2 статус; A/B fingerprint 13 stdlib идентичен |
| 3 | **6.3** `RoomDef`/`LevelDef`/`SizeSpec`/`ShapeParams` | весь `room_def`/`level_def`; range-литералы `[3,3]`/`[2,3]`/`[1,1]`, `"any"`, `count=1`, `or`-falsy `z_height`, `attach_wall or "both"` | ⬜ **следующий** — dedicated команда `/impl-rooms-pojo` |
| 4 | **6.4** facing-дефолты | `builder.py` NORTH, `shared.py` SOUTH, `shapes.py` SOUTH — по ТЗ strict vs POJO-default | ⬜ после 6.3 |

Каждый срез: dataModel (POJO + валидаторы + экспорт) → `StructureTemplate` model_validator → потребители → тесты → отчёт мастеру. Не объединять срезы в один заход.

## Проверки на каждый срез

- `python -m unittest tests.test_entry_point tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing` + новые тесты среза
- `python -m compileall -q app tests`
- grep `.get("` по потребителям домена — пусто
- Sweep generate по 13 `structures_templates/base/*.json` с capture `logger.error` — не хуже baseline (36 ERROR pre-existing, §7 п.11 основного плана)
- Детерминизм: generate×2 идентичен (как `test_deterministic_ids`)

## Стиль

Минимум файлов, один срез за заход. Не рефакторить соседние домены «заодно». Pydantic-конвенции — как `entryPoint.py` (`StrictOnWire`/`DefaultOnWire`/`constrained_field`, `extra="forbid"`, frozen). После среза: что сделано / какие литералы убраны / что осталось.

## Старт

Прочитай план §6 и §1–2. Срезы E1–E4, 6.1 (`RoomConnection`), 6.2 (`StaircaseSpec`) **сданы** — образцы в коде и статус-строки в плане. Следующий — **6.3** (`/impl-rooms-pojo` — dedicated команда, только по «ок» мастера), затем **6.4** facing-дефолты.
