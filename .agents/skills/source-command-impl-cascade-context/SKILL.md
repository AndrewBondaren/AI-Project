---
name: "source-command-impl-cascade-context"
description: "Имплементирует план cascade-context-resolution: LocationContext + extend() движок + проводка economic_tier по цепочке settlement→district→area→building→room со stamp на NL. Новый чат: /impl-cascade-context."
---

# source-command-impl-cascade-context

Use this skill when the user asks to run the migrated source command `impl-cascade-context`.

## Command Template

# Имплементация: каскадный резолв параметров локаций

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/cascade-context-resolution.md`](../plans/cascade-context-resolution.md) — **контракт, порядок шагов, проверки**; не отклоняться. S0 закрыт — решения мастера не пересогласовывать.
2. [`docs/tz_cascade_context.md`](../../docs/tz_cascade_context.md) — целиком (цепочка, `Cascade`/`CascadeLevel`/`DefaultPolicy`, `extend`, persist, кейсы §8).
3. [`docs/tz_economic_tier.md`](../../docs/tz_economic_tier.md) §4 (каскад с area/range), §9 (поля).
4. [`docs/tz_locations.md`](../../docs/tz_locations.md) — семантика `named_locations.system_economic_tier` («null → наследует от parent»).
5. Существующий код точек потребления: `generators/utils/tierResolver.py`, `utils/materialResolver.py`, `structure/structureGeneratorService.py` (4 вызова), `structure/room/roomFactory.py`, `structure/passages/wallOpening.py`, `assemblers/settlementAssembler`, `assemblers/areaAssembler/structureAreaAssembler.py` (`_place_building`), `settlementOutdoor/settlementOutdoorExtract.py`, `structureContext.py` (`building_band`).
6. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — атомарность шагов
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — DAG / backend / commit / schema = только `0001`
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

`LocationContext` с `Cascade`-аннотациями + один generic `extend()`;
единственный v1-параметр `economic_tier` резолвится по канонической
цепочке `world → settlement → district → area → building → room`,
stamp `system_economic_tier` на каждой NL цепочки, потребители
структуры читают `ctx.economic_tier` вместо `TierResolver`.

## Жёсткие запреты

- Не удалять `TierResolver` — у оставшихся city-вызовов `# TODO: перенести на LocationContext`.
- Не переводить потребители settlement/district-уровня (барьеры, дороги, стены) на ctx — follow-up.
- Не трогать `foundationBuilder`/`roofBuilder` и `or`-цепочки материалов — параметры вне scope v1.
- Не добавлять поля `LocationContext` сверх `economic_tier`, `level`, `provenance` — новые параметры отдельным решением.
- Не делать walker вверх по `parent_location_uid` — звенья подаёт caller.
- Не новые authored-поля, wire-ключи, schema-изменения. Не `0002_*.sql`.
- Не DAG `application/engine/nodes/`. Не стартовать backend. Не коммитить.
- rng — только `Random(_make_seed(world_uid, scope_uid, "tier"))` от caller'а, один раз на scope; не свой `Random()` в resolver'е.
- Не менять фильтрацию `planner/economic.py` (range там — отбор шаблонов, не каскад).

## Порядок — строго по шагам плана

S1 (baseline-тесты) → S2 (dataModel: `CascadeLevel`, `Cascade`,
`LocationContext`) → S3 (`context/cascadeLink` адаптеры + `extend()` +
`EmptyLink`) → S4 (проводка caller'ов; если дифф не ревьюится — S4a/S4b
по плану) → S5 (приёмка + пометки).

**Правило мастера:** каждое сообщение мастера после отчёта = приступать
к следующему шагу, **если** в нём нет фидбека по ревью кода. Фидбек —
сначала обработать, шаг не начинать.

После каждого шага: что сделано / файлы / проверки (чем прогнал) / что
осталось / что сознательно не тронуто. Один шаг за заход — без исключений.

## Приёмка (из плана)

- Детерминизм ×2 на seed; effective tier идентичен во всех 4 фазах
  структуры и per-room — один резолв.
- WARNING при пустой цепочке (median); без WARNING при authored tier.
- Валидация уровней: повтор/пропуск/выше → ошибка.
- Кейсы tz_cascade §8.1–8.4 на объектах dataModel (не raw dict).
- U-гейт structure (список тестов — в плане §Проверки) — геометрия
  неизменна; допустимые diff только effective tier и (Q3) геометрия
  band-шаблонов.
- `grep TierResolver` в `generators/structure/` и `materialResolver` —
  пусто; city-вызовы с TODO остаются.
- compileall изменённых модулей, `git diff --check` после каждого шага.

## Старт

Прочитай план целиком + перечисленные файлы потребления. Затем шаг S1.
