# source-command-impl-attach-any

Use this skill when the user asks to run the migrated source command `impl-attach-any`.

## Command Template

# Имплементация: срез 6.6 — `attach_wall: "any"` резолв по позиции лестницы

Это **явная просьба писать код** (срез 6.6 плана entry-point-pojo — дизайн согласован мастером 2026-09-30). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo-done.md`](../plans/entry-point-pojo-done.md) — **§6.6** (решения A1–A5 — контракт среза), статусы 6.1–6.4 (сданы).
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) — модал-B правило «any» (~§1667): комнаты на стороне, противоположной лестнице; решённый вопрос §15. Замечание: ТЗ пишет `staircase.position` — поле старой connection-схемы; маппинг на новую схему зафиксирован в §6.6 плана (A1: `sc.facing`).
3. Код: `layoutEngine._layout_mode_b` (~строка 374: `Facing(attach_wall)` → except → auto-detect), `structureGeneratorService._layout_rooms` (передача staircases), `staircase/shaftPlacer.py` (`AdjacentShaftPlacer`: shaft ставится в направлении `sc.facing` от fr_room-стопа), `passages/corridorTrimmer.py` (`_build_corridor_to_staircase` — образец маппинга corridor→staircase по stops), `utils/deterministicIds.py` (`scoped_rng`).
4. Правила: `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (один срез за заход → отчёт → «ок» мастера), `project-context.mdc` (не стартовать backend, не коммитить).

## Цель

`attach_wall="any"` у группы комнат, прикрепляемых к коридору (`attach_to` → room с `room_type=="corridor"`), выбирает сторону по лестнице в коридоре, а не чередованием обеих сторон.

## Спецификация (решения мастера — не менять)

```text
occupied = { sc.facing | sc ∈ staircases, corridor.room_id ∈ sc.stops,
             sc.facing задан, есть shaft этого sc на z_offset уровня }
sides    = осевые стороны хоста: N/S если corridor.depth >= corridor.width, иначе E/W
free     = sides \ occupied_nормированные_к_оси   # intercardinal → ближайшая осевая
if   len(free) == 1:              attach_wall = free[0]
elif len(free) == 2:              attach_wall = scoped_rng.choice(sides)   # обе свободны
else (обе заняты/нет лестницы):   attach_wall = scoped_rng.choice(sides)

scoped_rng(building_uid, corridor.room_id, str(z_offset), AttachWall.ANY.value)
```

- `sc.facing` — сторона, куда Adjacent-плейсер ставит шахту от коридор-стопа; facing `None` → лестница не занимает сторону (в occupied не входит).
- Несколько лестниц легальны — union занятых сторон; несвободность ≠ конфликт.
- `"any"` на **некоридорном** хосте — сохранить текущее чередование (правило коридор-специфично, A4).
- Стороны — по фактической оси хоста, не фиксированный n/s (A5).
- Коридор без лестницы → rng по оси (как ТЗ «staircase-connection отсутствует»).

## Границы среза

- Только `_layout_mode_b` + plumbing (staircases/definitions уже есть в `_layout_rooms` — прокинуть). Никаких изменений StaircaseSpec/shaftPlacer.
- Поведение на `"any"`-шаблонах меняется — это и есть фикс; stdlib-фикстуры `"any"` не содержат (проверено grep) → A/B обязан остаться идентичным.
- **Не трогать:** EmbeddedShaftPlacer (stub), host-not-placed WARNING→ERROR, mixed-array L/T, остальные leftovers §6.3/§6.4.
- Не DAG, не backend, не коммит, не `0002_*.sql`.

## Проверки

- Полный suite: `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations tests.test_room_def` + новые тесты среза
- Новый тест: шаблон с corridor + staircase (facing=north) + attach_wall="any" → все attached комнаты на южной стороне; без лестницы → детерминированный выбор (scoped_rng), generate×2 идентичен
- `python -m compileall -q app tests`; `git diff --check`
- A/B fingerprint 13 stdlib (`.local/rooms_pojo_sweep.py`-техника) — **идентичен**, те же 8 ERROR

## Старт

Прочитай §6.6 плана, ТЗ-правило ~§1667, `_layout_mode_b` и `AdjacentShaftPlacer`. Отчёт: что резолвится, какие стороны, что вне среза; статус-строка в §6.6.
