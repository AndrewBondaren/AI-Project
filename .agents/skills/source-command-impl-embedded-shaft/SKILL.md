# source-command-impl-embedded-shaft

Use this skill when the user asks to run the migrated source command `impl-embedded-shaft`.

## Command Template

# Имплементация: срез 6.11 — `EmbeddedShaftPlacer` (embed_in/embed_at)

Это **явная просьба писать код** (срез 6.11 плана entry-point-pojo — решения v1 зафиксированы 2026-10-01). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши. Срез крупнее предыдущих — это фича (размещение), не багфикс; держи diff компактным.

## Прочитать до первой правки

1. [`.cursor/plans/entry-point-pojo.md`](../plans/entry-point-pojo.md) — **§6.11** (контракт + решения v1 — не менять без уточнения мастера).
2. [`docs/tz_staircase_generation.md`](../../docs/tz_staircase_generation.md) — §2 `in_a_room`/`embed_in`/`embed_at` + TODO-блок (снять после реализации); §1 stops-модель; `tz_building_generator.md` §673–675 (wire-поля).
3. Код: `staircase/shaftPlacer.py` (stub + `AdjacentShaftPlacer`/`EdgeMountedShaftPlacer` как образцы), `structureGeneratorService._place_level_shafts` (~563: `placer.place(shaft_fr, fr_room, placed_on_level)`; `fr_room` = `stops[0]`, host = `embed_in` — lookup по `placed_on_level`), `passages/builder.py` ~163–178 (z_lo archway shaft↔fr_room через shared wall), `cellBuilder.py` (pass2 пропускает `is_shaft`, pass3 красит периметр — **разметка работает без правок**, угловая шахта внутри хоста сама даёт стены и слияние), `utils/deterministicIds.scoped_rng`.
4. Правила: `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `plan-before-code.mdc`, `project-context.mdc` (не стартовать backend, не коммитить).

## Цель

`in_a_room: true` размещает shaft внутри комнаты `embed_in` (на уровне `stops[0]`): `embed_at` intercardinal-угол (две стороны шахты сливаются со стенами хоста) или `center` (столб-атриум, стены на всех 4 сторонах). Шахта вырезает footprint из interior хоста.

## Спецификация (решения v1 — зафиксированы в §6.11)

```text
host = placed room with room_id == sc.embed_in на z_lo
     | нет такого → logger.error + fallback: самая большая placed-комната на z_lo (ТЗ)
embed_at:
  intercardinal → origin: угол host — внешние стороны шахты НА периметре хоста
                  (общие стены не дублируются — footprint-клетки совпадают)
  center        → origin: центрирован в interior хоста
  отсутствует   → scoped_rng(building_uid, sc.staircase_id, "embed_at").choice(4 угла)
fit: host.interior вмещает shaft footprint (угол: 2 стороны на периметре хоста;
     center: весь footprint внутри interior, минимум 1 клетка до стен)
  → не влезает: logger.error + fallback AdjacentShaftPlacer
```

- **z_lo archway (вход):** сторона, обращённая к центру interior хоста; для `center` — `scoped_rng(..., "embed_entry")`. ⚠️ `builder.py` ~165 строит arch `shaft↔fr_room` по shared wall — для embedded general-случая (`embed_in ≠ stops[0]`) shared wall с fr_room может не быть: arch должен идти к **host**. Минимально-инвазивно: при `sc.in_a_room` цель z_lo-арки = host room. Если `embed_in == stops[0]` — поведение совпадает с текущим.
- Shaft origin считается от host.origin, placed/fit — против `placed_rooms` уровня; overlap с другими комнатами = ошибка размещения (как fit-fail → fallback).
- Multi-level: `shaft_list[1:]` уже наследуют origin вертикально (`_place_level_shafts` строки 593–595 — переиспользуется без правок). Pass-through сквозь комнаты верхних этажей — ТЗ TODO, **вне среза**.

## Границы среза

- Только: `EmbeddedShaftPlacer.place`, host/embed_at резолв, z_lo-arch target при `in_a_room`, тесты, снятие TODO-блока из staircase §2.
- **Не трогать:** cellBuilder (механика уже работает), `AdjacentShaftPlacer`/`EdgeMountedShaftPlacer`, upper-level host-семантику (ТЗ TODO), `corridorTrimmer`, остальные leftovers.
- Ни одна stdlib-фикстура не использует `in_a_room` (проверить grep'ом) → A/B обязан остаться идентичным.
- Не DAG, не backend, не коммит, не `0002_*.sql`.

## Проверки

- Полный suite (список как в §6.10: 16 модулей + `test_attach_any`/`test_wall_opening_spec` + новые) 
- Новые тесты: embed_at угол → footprint на углу хоста, стены не дублируются; `center` → столб с 4 стенами; `embed_at` omitted → deterministic scoped_rng выбор (generate×2 идентично); host не вмещает → ERROR + adjacent fallback; `embed_in` отсутствует → ERROR + largest-room fallback; arch на z_lo присутствует к host; shared-wall слияние; шаблон не мутируется
- `python -m compileall -q app tests`; `git diff --check`
- A/B fingerprint 13 stdlib (`.local/rooms_pojo_sweep.py`-техника, артефакты `.local/embedded_shaft_{before,after}.json`) — **идентичен**, те же 8 ERROR

## Старт

Прочитай §6.11 плана, staircase §2 (embed-контракт), `shaftPlacer.py`, `_place_level_shafts` и builder-арку ~165. Отчёт: решённые кейсы (host/embed_at/fit/arch), что вне среза; статус-строка в §6.11 + снять TODO из ТЗ.
