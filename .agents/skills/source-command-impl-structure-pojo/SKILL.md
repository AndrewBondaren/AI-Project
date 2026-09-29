---
name: "source-command-impl-structure-pojo"
description: "Имплементирует следующие POJO-срезы структурного генератора по плану entry-point-pojo §6: RoomConnection (connections[]), StaircaseSpec (staircases[]), RoomDef/LevelDef/SizeSpec/ShapeParams, facing-дефолты + фиксы найденных багов. Новый чат: /impl-structure-pojo."
---

# source-command-impl-structure-pojo

Use this skill when the user asks to run the migrated source command `impl-structure-pojo`.

## Command Template

# Имплементация: POJO-срезы структурного генератора (по entry-point-pojo §6)

Это **явная просьба писать код** (срезы §6 плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo.md`](../plans/entry-point-pojo.md) — **§6 инвентарь** (что чинить, по файлам/строкам); §1–2 — паттерн `EntryPoint` как образец; §4 — найденные расхождения.
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) §3.6 (entry_point — сделано), §3.7 (connections: поля, `door_height`, запрет `staircase`), §3.7b (staircases).
3. [`docs/tz_staircase_generation.md`](../../docs/tz_staircase_generation.md) — поля `staircases[]` / ladder.
4. Образец реализации (уже в коде): `dataModel/structure/room/entryPoint.py`, `dataModel/structure/enums/entryAccessType.py`, `StructureTemplate._validate_entry_points`, `roomFactory` parse → `GenerationError`.
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

| # | Срез | Что | Баги из §6.5 | Готово когда |
|---|---|---|---|---|
| 0 | **E4** — docs sync + sweep | `tz_building_generator.md`: wire-ключ `door_height`, поля ratio/max; §286 форсинг | — | docs sync; validator-sweep по 13 stdlib не хуже baseline §7 п.11 основного плана |
| 1 | **6.1** `RoomConnection` POJO | `dataModel/structure/building/roomConnection.py` (или `room/`): `from_room`/`to_room` StrictOnWire, `passage_type` StrictEnumOnWire {doorway, archway} (staircase → reject), `door_height`, `frame_material`, `step_material`, `width`; потребители `doorway.py`, `archway.py`, `builder.py`, `layoutEngine.py` читают typed | `doorway.py:41` `height`→`door_height`; `archway.py:64` frame ← `floor_material` → `wall_material` (ТЗ §606); `room_z_offsets.get(…,0)` — решить reject/keep с мастером | grep `conn.get(` в passages/layoutEngine пустой; тесты doorway/archway |
| 2 | **6.2** `StaircaseSpec` POJO | `staircase_id` (один дефолт вместо 6 мест), `staircase_type`, `stops`, `step_material`, `on_the_edge`, `in_a_room`, `outside`, `size`, `facing`; ladder-поля `is_movable`/`has_trapdoor`/`near_wall`/`has_walls`/`open_wall_shaft`/`closed_exit`; потребители `builder.py`, `shaftFactory`, `shaftPlacer`, `corridorTrimmer`, `verticalLadder`, `service` | `verticalLadderValidator.py:132` `passage_height=2` → дефолт мира | grep `sc.get(`/`sc_entry.get(`/`entry.get(` по staircase-домену пустой |
| 3 | **6.3** `RoomDef`/`LevelDef`/`SizeSpec`/`ShapeParams` | **только по «ок» мастера** — больший scope: весь `room_def`/`level_def` | range-литералы `[3,3]`/`[2,3]`/`[1,1]`, `"any"`, `count=1`, `or`-falsy `z_height`, `attach_wall or "both"` | wire-контракт зафиксирован; roomFactory без `.get` |
| 4 | **6.4** facing-дефолты | `builder.py:154` NORTH, `shared.py:50` SOUTH, `shapes.py:108/168` SOUTH — по ТЗ решить strict vs POJO-default | — | решение мастера записано; дефолты в POJO или strict |

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

Прочитай план §6 и §1–2, ТЗ §3.7/§3.7b, текущий `entryPoint.py` как образец. Начни с **E4** (если мастер не закрыл) затем **6.1**.
