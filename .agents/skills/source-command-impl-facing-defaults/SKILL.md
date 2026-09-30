# source-command-impl-facing-defaults

Use this skill when the user asks to run the migrated source command `impl-facing-defaults`.

## Command Template

# Имплементация: POJO-срез 6.4 — изолированные facing-дефолты

Это **явная просьба писать код** (срез 6.4 плана entry-point-pojo — последний POJO-срез). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo.md`](../plans/entry-point-pojo.md) — **§6.4** (три места), статусы §6.1–6.3 (сданы — образцы), §4 расхождения.
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) §3.5b (`stem_wall`/`arm_corner` — default `"any"` на wire), §3.6 (`entry_point.wall` required), staircase `facing` — [`docs/tz_staircase_generation.md`](../../docs/tz_staircase_generation.md).
3. Образцы сданных срезов: `dataModel/structure/building/{roomConnection,staircaseSpec,levelDef}.py`, `dataModel/structure/room/{roomDef,shapeParams,entryPoint}.py`, `StructureGeneratorService._resolve_{connections,staircases,levels}` — паттерн границ и логирования.
4. Правила (нарушение = стоп): `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (один срез за заход), `project-context.mdc` (не стартовать backend, не коммитить без явной команды).

## Контекст состояния (факт после 6.3)

Три места из инвентаря §6.4 с актуальным состоянием:

| Место | Код | Факт |
|---|---|---|
| `passages/shared.py:50` | `parse_facing_or_default(direction, default=Facing.SOUTH)` в `_exterior_cells_on_wall` | Единственный caller — `entry.py:61` с `ep.wall`, а `EntryPoint.wall` = `StrictOnWire[Facing]` cardinal (никогда None/мусор). **Дефолт мёртвый** → сузить сигнатуру до `Facing`, убрать parse/default. Чистая уборка, поведение нулевое |
| `shapes.py:108` + `:168` | `stem_wall` → `Facing.SOUTH` (`parse_facing_or_default` + `p.get(..., SOUTH.value)`) | После 6.3 `ShapeParams.stem_wall` = `Literal[..., "any"]` default `"any"`; `"any"` → `rng.choice(cardinal)` в `roomFactory._resolve_shape_params`. SOUTH здесь — **двойной consumer-дефолт** (`dataModel-no-hardcode`) + прикрытие известного бага: смешанный массив `shape_type` с `t_shape` не резолвит params → stem_wall отсутствует |
| `passages/builder.py:151` | `_shaft_ref.facing` → `default=Facing.NORTH` | `_shaft_ref` — shaft `_RoomInstance`, `facing` ← `StaircaseSpec.facing` (optional по wire — шахте легально без facing). NORTH — внутренняя геометрическая конвенция выбора оси для arch width, **не wire-дефолт** |

## Что решить и сделать

- `shared.py`: типизация `direction: Facing` + удалить дефолт (мёртвая ветка).
- `shapes.py`: `stem_wall` на этом уровне обязан быть cardinal (контракт `roomFactory`): заменить silent SOUTH на явную ошибку внутреннего контракта (`UnsupportedShapeError`/`ValueError` с контекстом) **или** оставить защитный дефолт — вопрос мастеру, если ТЗ молчит о внутренних границах. Смешанный массив L/T — **не чинить здесь** (отдельный зафиксированный leftover, меняет RNG).
- `builder.py`: решить по ТЗ staircase — `facing` optional или required для шахты; если optional легитимен → NORTH зафиксировать как документированную внутреннюю конвенцию (комментарий/ТЗ), не wire-фолбэк; если required → StrictOnWire в `StaircaseSpec` (осторожно: меняет import-контракт 6.2 — эскалация мастеру, не самостоятельно).
- Доктрина (как 6.3): documented default → тихо; подмена заданного автором → ERROR на границе `StructureGeneratorService`; POJO не логируют.

## Жёсткие запреты

- Не менять RNG-поток: `rng.choice` на `"any"` остаётся в `roomFactory`, порядок вызовов неизменен.
- Не чинить смешанный `shape_type`-массив с L/T и `attach_wall="any"` — задокументированные leftovers §6.3.
- Не трогать staircase-семантику `facing` (embed/shaft placement — отдельные TODO).
- Не DAG `application/engine/nodes/`. Не backend. Не коммит. Не `0002_*.sql`.

## Проверки

- `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations tests.test_room_def` (+ новые тесты среза если есть)
- `python -m compileall -q app tests`
- A/B fingerprint `sha256(cells+passages)` по 13 `structures_templates/base/*.json` — идентично (техника: `.local/rooms_pojo_sweep.py` — backup → `git checkout HEAD -- <файлы>` → sweep → restore)
- grep: `parse_facing_or_default` с литеральными дефолтами в `generators/structure/` — по итогу только легитимные (если остаются — с обоснованием)

## Старт

Прочитай план §6.4, ТЗ §3.5b/§3.6, три места кода выше. Решение по каждому месту зафиксировать в отчёте; спорное — вопрос мастеру до правок.
