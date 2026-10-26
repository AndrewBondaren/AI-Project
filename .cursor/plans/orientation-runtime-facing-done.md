# Orientation: поворот runtime facing-полей (техдолг B5) — выполнен

**Статус:** реализован 2026-10-03, шаги 1–3 завершены.

## Результат и проверки

- Шаг 1: ТЗ §9 описывает единый поворот runtime facing-полей в мировой фрейм.
- Шаг 2: `StructureOrientation.apply` копирует frozen EntryPoint с повёрнутой
  wall, поворачивает shaft facing/embedded_entry и кардинальный attach_wall через
  существующий CARDINAL_FACINGS; None, BOTH/ANY и неразмещённые комнаты сохраняются.
- Шаг 3: расширен существующий `backend/tests/test_structure_orientation.py`:
  четыре новых теста, четырёхоборотная идентичность с метаданными и проверки
  runtime-полей при полной генерации в четырёх направлениях. Шаблон не мутируется.
- Начальный baseline: 158 тестов, 1 expected failure, 1 ошибка импорта C24 из-за
  отсутствующего zstandard. Установлена объявленная в requirements.txt зависимость
  zstandard 0.25.0 в проектную .venv. Итоговый указанный skill suite: 183 теста OK,
  1 существующий expected failure; orientation suite: 9 тестов OK.
- `python -m compileall -q app tests` и `git diff --check` прошли.
- `.local/orientation_facing_{before,after}.json` идентичны: 13 stdlib templates,
  те же 8 ERROR, детерминизм ×2. Скрипт fingerprint включает только cells/passages
  и не задаёт facing; runtime-метаданные и реальный поворот проверены тестами.
- Логи: `.local/orientation_facing_tests.log`, `.local/orientation_facing_suite.log`.

Ниже сохранён согласованный план. B5 закрыт в `structure-technical-debt.md`.

**Источник:** `.cursor/plans/structure-technical-debt.md` B5 — латентный баг.

## Проблема

`StructureOrientation.apply` поворачивает клетки (`x/y`, `system_facing`,
`railing_sides`), passage-точки и `origin`/`bbox`/`extra_cells` комнат и шахт —
но facing-поля на `_RoomInstance` остаются в **авторском фрейме**:

| Поле | Тип | Сейчас после поворота |
|---|---|---|
| `entry_point.wall` | `Facing` | stale (ирония: именно оно вычислило угол) |
| `back_entry_point.wall` | `Facing` | stale |
| `facing` (shaft runtime, вкл. embedded-adjusted) | `str \| None` | stale |
| `embedded_entry` | `Facing \| None` | stale |
| `attach_wall` | `AttachWall` (кардиналы + both/any) | stale |

Инвариант: **поворот здания поворачивает всю онтологию** — вход на юге +
поворот 90° CW → метаданные говорят «восток», не «юг». Алгоритм расстановки
шахт читает `facing` — метаданные обязаны жить в том же фрейме, что и
геометрия. Сегодня безвредно лишь потому, что `apply` стоит последним и поля
не сериализуются (`_room_to_named_location` их не читает).

## Шаг 1 — ТЗ (tz_building_generator §9)

Дописать в блок «Ориентация (вариант B)» (~стр. 2020–2027): единый проход
поворота покрывает также runtime facing-поля размещённых `_RoomInstance`:
`entry_point.wall`, `back_entry_point.wall`, shaft `facing`, `embedded_entry`,
`attach_wall` (кардиналы; `both`/`any` инвариантны). После поворота все
facing-поля — в мировом фрейме; авторский фрейм сохраняется только в
немутированном `StructureTemplate`.

## Шаг 2 — код

**Файл:** `backend/app/application/worldData/generators/structure/structureOrientation.py`

В `StructureOrientation.apply` в цикле по `rooms` (после origin/bbox):

```python
for room in rooms:
    if not room.placed:
        continue
    ...existing origin/bbox/extra_cells...
    for ep in (room.entry_point, room.back_entry_point):
        if ep is not None and ep.wall is not None:
            # EntryPoint frozen → model_copy(update={"wall": self.facing(ep.wall)})
    if room.is_shaft:
        if room.facing:       room.facing = self.facing(room.facing).value
        if room.embedded_entry: room.embedded_entry = self.facing(room.embedded_entry)
    if room.attach_wall in CARDINAL_ATTACH_WALLS:  # north/south/east/west
        room.attach_wall = AttachWall(self.facing(room.attach_wall.value))
```

Контракт:
- `EntryPoint` — pydantic/frozen → `model_copy(update=...)`, не мутировать.
- `attach_wall` — поворачивать только кардинальные значения; `BOTH`/`ANY`
  без направления (инвариантны к повороту).
- `facing`/`embedded_entry` — `None` пропускать.
- Не трогаем: `StructureTemplate` (wire, не мутируется), `StaircaseSpec`
  (шаблонный authored facing — фрейм автора, читателей после поворота нет).

## Шаг 3 — тест

**Файл:** новый `test_structure_orientation.py` (или в существующий suite
orientation, если есть).

- Здание с `main_entrance` на южной стене + `facing=west` → поворот;
  assert: `entry_point.wall == Facing.WEST`, shaft `facing`/`embedded_entry`
  повёрнуты тем же `orientation.facing()`.
- `attach_wall=BOTH` остаётся `BOTH`; кардинал поворачивается.
- `facing=None` → `apply` не вызывается, поля нетронуты (существующее
  поведение `structureGeneratorService` не меняем).

## Проверка

- `python -m unittest` — полный suite без новых падений (baseline: N tests
  OK, 1 expected failure — зафиксировать фактическое число на старте).
- `python -m compileall` на изменённые файлы; `git diff --check`.
- A/B-фингерпринт 13 stdlib: идентичен (поля не входят в fingerprint —
  проверить `python .local/rooms_pojo_sweep.py <out>` ×2 или скрипт sweep).

## Done

- ТЗ §9 описывает поворот runtime facing-полей.
- `apply` поворачивает все facing-поля `_RoomInstance`; тест зелёный.
- B5 в техдолге → «Реализован» + короткая итерация-запись.

## Вне scope

- Поворот `StaircaseSpec.facing` (authored, шаблон не мутируется).
- `display_facing` (OQ-14, v2) — см. C3.
- Любые изменения порядка фаз в `generate()`.
