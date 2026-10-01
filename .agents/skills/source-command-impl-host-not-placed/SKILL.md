# source-command-impl-host-not-placed

Use this skill when the user asks to run the migrated source command `impl-host-not-placed`.

## Command Template

# Имплементация: срез 6.8 — host-not-placed WARNING → ERROR

Это **явная просьба писать код** (срез 6.8 плана entry-point-pojo — зафиксирован 2026-10-01). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo.md`](../plans/entry-point-pojo.md) — **§6.8** (scope среза), статусы 6.1–6.7 (сданы).
2. Код: `layoutEngine._layout_mode_b` — точка `logger.warning("layout mode_b | host=%r not placed — skipping %d attached room(s)")` (~строка 408); `structureGeneratorService._layout_rooms` — upstream fixed-point фильтр невалидных `attach_to` (комнаты с отвалившимся хостом отсекаются раньше); доктрина ERROR — см. `roomFactory` (`wall_openings` substitutions → `logger.error`) и `_attach_wall_substitution` → runtime-лог.
3. Правила: `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc` (один срез → отчёт → «ок» мастера), `project-context.mdc` (не стартовать backend, не коммитить).

## Цель

Комната с `attach_to` на хост, который не размещён (не влез по геометрии / отвалился на более ранней стадии), — authored-ошибка конфигурации → `logger.error`, не `logger.warning`. Генерация продолжается (мир остаётся играбельным — доктрина §6.4).

## Спецификация

- `layoutEngine._layout_mode_b`: `host is None or not host.placed` → `logger.error` вместо `logger.warning`, текст сообщения сохранить/уточнить (формат централизованного транскрипта — как у остальных ERROR: «Structure … room … — причина» или текущий строковый стиль mode_b; единообразие с соседними сообщениями важнее).
- Проверить grep'ом, нет ли второго места с той же семантикой (host missing / host not placed) в `layoutEngine`/`structureGeneratorService` — если есть, покрыть тем же срезом и упомянуть в отчёте.
- **Не трогать:** «no space» варнинги (`skipped — no x-space`, `no space` mode_a) — это геометрический fit, не authored-ссылка; fixed-point фильтр `attach_to`; всё остальное.

## Границы среза

- Одна точка логирования (+ найденные близнецы) + тест. Никаких изменений логики размещения.
- stdlib-фикстуры кейс не триггерят → A/B fingerprint и счётчик ERROR обязаны остаться идентичными.
- Не DAG, не backend, не коммит, не `0002_*.sql`.

## Проверки

- Полный suite: `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations tests.test_room_def tests.test_attach_any tests.test_wall_opening_spec` + новый тест
- Новый тест: `attach_to` на неразмещённый хост → ERROR в транскрипте (`assertLogs`/`generation_world_log`), attached-комната не размещена, generate завершается; уровень именно ERROR, не WARNING
- `python -m compileall -q app tests`; `git diff --check`
- A/B fingerprint 13 stdlib (`.local/rooms_pojo_sweep.py`-техника, артефакты `.local/host_not_placed_{before,after}.json`) — **идентичен**, те же 8 ERROR

## Старт

Прочитай §6.8 плана и `_layout_mode_b`. Отчёт: какие точки сменили уровень, что вне среза; статус-строка в §6.8.
