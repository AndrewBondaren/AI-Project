# source-command-impl-mixed-shape-params

Use this skill when the user asks to run the migrated source command `impl-mixed-shape-params`.

## Command Template

# Имплементация: срез 6.10 — `shape_params` по выбранной форме (смешанный shape_type-массив)

Это **явная просьба писать код** (срез 6.10 плана entry-point-pojo — зафиксирован 2026-10-01). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo-done.md`](../plans/entry-point-pojo-done.md) — **§6.10** (scope среза), статусы 6.1–6.9 (сданы).
2. Код: `room/roomFactory.py` — `_resolve_shape` (~строка 26: `rng.choice(raw)` для массива), `_resolve_shape_params` (~строка 67: ветки по `room_def.shape_type` — **объявленному** значению), порядок вызовов в `instantiate_level_rooms` (~строки 130–140: shape → size → params → `resolve_stem_wall` постпроход); `shapes.py` — `room_footprint` dispatch (~строка 174: дефолты `arm_width=width//3`, `arm_corner="northeast"` при пустых params); `dataModel/locations/structure/room/roomDef.py` `_conditional_fields` (~строка 85: `shape_params` обязательны если `"l_shape"`/`"t_shape"` **в массиве** — authored params гарантированно есть).
3. Правила: `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (один срез → отчёт → «ок» мастера), `project-context.mdc` (не стартовать backend, не коммитить).

## Цель

При `shape_type` — смешанном массиве (напр. `["l_shape", "rectangle"]`), выбранная `rng.choice` форма получает свои `shape_params`. Сейчас params резолвятся только для скаляра/одноэлементного массива → выбранная L/T из смеси получает `{}` → молчаливые дефолты footprint (`width//3`, `"northeast"`) при валидных authored params.

## Спецификация

- `_resolve_shape_params` принимает **выбранный** `ShapeType` (результат `_resolve_shape`), ветвится по нему: `ShapeType.L_SHAPE` → arm_*; `ShapeType.T_SHAPE` → stem_*; иначе `{}`.
- **Порядок вызовов и rng-draws не менять**: `_resolve_shape` (choice) → `_resolve_size` (randint ×N) → `_resolve_shape_params` (corner `"any"` → choice, диапазоны → randint). Новые draws появляются только когда смешанный массив выбрал L/T — раньше этот путь был багован (`{}`), поток для него не определён.
- Для скаляра `"l_shape"`/`"t_shape"` и массива `["l_shape"]` поведение бит-в-бит то же (chosen == declared).
- `resolve_stem_wall` постпроход (строки ~139–141) сохранить — после params-резолва, только если `stem_wall` в params.
- Если выбранная форма L/T, а спека неполная (защита на случай обхода валидатора — например конструирование RoomDef напрямую) — `logger.error` + существующие footprint-дефолты, генерация живёт. Это уже не должно случаться через wire (валидатор режет), но defensive ERROR — по доктрине.

## Границы среза

- Только `roomFactory._resolve_shape_params` + его вызов + тесты.
- **Не трогать:** `shapes.py` footprint-дефолты (останутся защитой последнего рубежа), `_resolve_shape`, `SizeShapeResolver`, `ResolvedStemWall`, валидатор `RoomDef`, все leftovers (EmbeddedShaftPlacer и пр.).
- Stdlib содержит массивы только `["square","rectangle"]` (kitchen в `5a1f2b3c`, `6b2f3c4d`) — L/T в смесях нет → **A/B fingerprint обязан остаться идентичным**.
- Не DAG, не backend, не коммит, не `0002_*.sql`.

## Проверки

- Полный suite: `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations tests.test_room_def tests.test_attach_any tests.test_wall_opening_spec` + новые тесты
- Новые тесты: смешанный массив выбрал `l_shape` → `arm_width/arm_depth/arm_corner` из спеки (проверка footprint, не дефолтов); выбрал `rectangle` → params `{}` и rng-поток не потреблён params-фазой; скаляр `l_shape`/`t_shape` — неизменно; `"any"` corner/wall — rng-выбор работает; generate×2 идентично; шаблон не мутируется
- `python -m compileall -q app tests`; `git diff --check`
- A/B fingerprint 13 stdlib (`.local/rooms_pojo_sweep.py`-техника, артефакты `.local/mixed_shape_{before,after}.json`) — **идентичен**, те же 8 ERROR

## Старт

Прочитай §6.10 плана, `roomFactory._resolve_shape`/`_resolve_shape_params` и `shapes.room_footprint`. Отчёт: что меняется, rng-порядок сохранён, что вне среза; статус-строка в §6.10.
