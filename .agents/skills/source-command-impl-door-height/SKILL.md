# source-command-impl-door-height

Use this skill when the user asks to run the migrated source command `impl-door-height`.

## Command Template

# Имплементация: срез 6.9 — `door_height` auto-resolve по ТЗ (убрать clamp)

Это **явная просьба писать код** (срез 6.9 плана entry-point-pojo — ТЗ исправлено решением мастера 2026-09-30, код отложен). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo-done.md`](../plans/entry-point-pojo-done.md) — **§6.9** (таблица «сейчас → надо», контракт общего резолвера), статусы 6.1–6.8 (сданы).
2. [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) — §505–543 (entry `door_height`: авто-резолв, формула, «явное ниже предела → авто-резолв, не clamp»), §627 (connections: тот же резолв, `z_height = min(from_room.z_height, to_room.z_height)`), §186–188 (`door_height_ratio` default 0.75, `door_height_max` default 5 на `StructureTemplate`).
3. Код: `passages/entry.py` (`_resolve_entry_height` — clamp `max(height, passage_height)` применён и к явному), `passages/doorway.py:41` (`max(conn.door_height or passage_height, passage_height)`), `passages/builder.py` (`build_passages` уже принимает `template`, вызов `_build_doorway` ~строка 104), `dataModel/locations/structure/building/roomConnection.py` (`conn.door_height`), `entryPoint.py` (`ep.door_height`), `DEFAULT_DOOR_HEIGHT_RATIO/MAX` — найти где объявлены.
4. Правила: `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (один срез → отчёт → «ок» мастера), `project-context.mdc` (не стартовать backend, не коммитить).

## Цель

Привести код к ТЗ: явное `door_height` используется только если `>= world.default_passage_height`; иначе отбрасывается и считается авто-формула — не clamp до предела. Для connections формула идёт от `min(z_height)` двух комнат.

## Спецификация (решения мастера — не менять)

```text
resolve_door_height(z_height, explicit, passage_height, ratio, cap):
    if explicit is not None and explicit >= passage_height:
        height = explicit                       # явное валидное — как есть
    else:
        if explicit is not None:
            → substitution-поведение: ERROR «door_height=<x> ниже passage_height=<p> — auto-resolve»
        height = z_height - 1            if z_height <= 3
               = min(floor(z_height * ratio), cap)  иначе
        height = max(height, passage_height)    # floor — ТОЛЬКО для авто-результата
    validate: passage_height <= height < z_height → иначе GenerationError
```

- **Одна общая функция** (например `resolve_door_height` в `passages/` или рядом с обоими потребителями) — не копия формулы. `entry.py` вызывает с `z_height=room.z_height`; `doorway.py` — с `z_height=min(fr.z_height, to.z_height)`.
- `doorway.py` должен получить `template` — прокинуть из `build_passages` (он уже принимает `template` kwarg).
- Runtime-валидация верхней границы `door_height < z_height` применяется и для connections — к `min(fr,to).z_height` (проём живёт в стене обеих комнат).
- ERROR при отброшенном явном `door_height` — централизованный `logger.error` в generation-транскрипт, текст в стиле соседних сообщений; генерация продолжается.

## Границы среза

- Только `entry.py`, `doorway.py`, общий резолвер, plumbing `template`, тесты.
- **Не трогать:** `archway` (нет `door_height` на wire — frame-высота отдельная), `corridorConnector` (свой `min(z_height - 1, passage_height)` — другая семантика), `heightChecker`, ступени лестниц, `wall_openings`.
- Ни одна stdlib-фикстура не содержит `door_height` (grep → 0) → A/B обязан остаться идентичным.
- Не DAG, не backend, не коммит, не `0002_*.sql`.

## Проверки

- Полный suite: `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations tests.test_room_def tests.test_attach_any tests.test_wall_opening_spec` + новые тесты
- Новые тесты: явный `door_height` ниже предела → авто-формула + ERROR (entry и connection); явный валидный → как есть; connection с разными z_height → формула от min; `door_height >= min_z` → GenerationError; generate×2 детерминизм; шаблон не мутируется
- `python -m compileall -q app tests`; `git diff --check`
- A/B fingerprint 13 stdlib (`.local/rooms_pojo_sweep.py`-техника, артефакты `.local/door_height_{before,after}.json`) — **идентичен**, те же 8 ERROR

## Старт

Прочитай §6.9 плана, ТЗ §505–543 и §627, `_resolve_entry_height` и `_build_doorway`. Отчёт: где общий резолвер, что изменилось в поведении, что вне среза; статус-строка в §6.9.
