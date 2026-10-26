# source-command-impl-orientation-facing

Use this skill when the user asks to run the migrated source command `impl-orientation-facing`.

## Command Template

# Имплементация: orientation-runtime-facing — поворот runtime facing-полей (техдолг B5)

Это **явная просьба писать код** (план `orientation-runtime-facing` — согласован 2026-10-02). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/orientation-runtime-facing.md`](../plans/orientation-runtime-facing.md) — **весь план** (3 шага: ТЗ → код → тест).
2. Код: `backend/app/application/worldData/generators/structure/structureOrientation.py` — `StructureOrientation.apply` (~строка 45, цикл по `rooms` после origin/bbox); `backend/app/application/worldData/generators/structure/room/roomInstance.py` — поля `_RoomInstance`: `facing: str | None`, `embedded_entry: Facing | None`, `attach_wall: AttachWall`, `entry_point`/`back_entry_point: EntryPoint | None`; `backend/app/dataModel/locations/structure/room/entryPoint.py` — `EntryPoint` **frozen pydantic**, `wall: StrictOnWire[Facing]` (кардинальная валидация).
3. ТЗ: `docs/tz_building_generator.md` §9 «Ориентация (вариант B)» (~строки 2016–2027) и §8.6 (~1548) — контракт поворота; сейчас там перечислены cells/passages/origin, runtime facing-поля не упомянуты.
4. Правила: `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `code-gates.mdc` (один шаг → отчёт → «ок» мастера), `project-context.mdc` (не стартовать backend, не коммитить).

## Цель

Инвариант: **поворот здания поворачивает всю онтологию**. Вход на юге + поворот 90° CW → метаданные говорят «восток». Сейчас `apply` поворачивает cells/passages/origin, но facing-поля `_RoomInstance` остаются в авторском фрейме (латентный баг — безвредно только потому, что apply последний шаг и поля не сериализуются).

## Спецификация

Порядок — строго по плану:

### Шаг 1 — ТЗ

В `tz_building_generator.md` §9 блок «Ориентация (вариант B)» дописать: единый проход поворота покрывает runtime facing-поля размещённых `_RoomInstance` — `entry_point.wall`, `back_entry_point.wall`, shaft `facing`, `embedded_entry`, `attach_wall` (кардиналы; `both`/`any` инвариантны). После поворота все facing-поля — в мировом фрейме; авторский фрейм сохраняется только в немутированном `StructureTemplate`.

### Шаг 2 — код (`structureOrientation.apply`)

В цикле по `rooms` (после origin/bbox/extra_cells):

- `entry_point.wall` / `back_entry_point.wall`: `EntryPoint` frozen → `room.entry_point = room.entry_point.model_copy(update={"wall": self.facing(ep.wall)})`. `ep.wall` не бывает `None` (StrictOnWire + кардинальный валидатор), но защитный `is not None` допустим.
- `room.is_shaft`: `room.facing` (`str`) → `self.facing(room.facing).value`; `room.embedded_entry` (`Facing`) → `self.facing(room.embedded_entry)`. `None` пропускать.
- `room.attach_wall`: поворачивать **только кардиналы** (`north/south/east/west`) → `AttachWall(self.facing(room.attach_wall.value))`; `BOTH`/`ANY` без направления — не трогать.

### Шаг 3 — тест

`tests/test_structure_orientation.py` уже существует — расширить его (не создавать дубль). Кейсы:

- `main_entrance` на южной стене + `facing=west` → после `apply`: `entry_point.wall == Facing.WEST`, shaft `facing`/`embedded_entry` повёрнуты тем же `orientation.facing()`.
- `attach_wall=BOTH`/`ANY` остаются собой; кардинал поворачивается.
- `facing=None`/`embedded_entry=None` — пропуск, не падает.

## Границы среза

- **Не трогать:** `StaircaseSpec.facing` (authored, шаблон не мутируется), `StructureTemplate` (wire), `display_facing` (OQ-14, v2), порядок фаз в `generate()`.
- Поворот только XY-facing; Z/материалы/uid без изменений.
- Не DAG, не backend, не коммит, не `0002_*.sql`.

## Проверки

- Полный suite: `python -m unittest tests.test_entry_point tests.test_entry_point_runtime tests.test_room_connection tests.test_staircase_spec tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes tests.test_c24_district_packing tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_debug_structure_rotations tests.test_room_def tests.test_attach_any tests.test_wall_opening_spec` — зафиксировать фактический baseline-объём на старте.
- `python -m compileall -q app tests`; `git diff --check`.
- A/B fingerprint 13 stdlib (`.local/rooms_pojo_sweep.py`-техника, артефакты `.local/orientation_facing_{before,after}.json`) — **идентичен** (поля в fingerprint не входят — проверить состав fingerprint в скрипте).

## Старт

Прочитай план целиком и `structureOrientation.py`. Шаги по одному с отчётом. Финал: статус в плане + B5 в `structure-technical-debt.md` → «Реализован» + короткая итерация-запись по формату существующих (`## Итерация B5 — <дата>`: файлы, решения, проверки).
