---
name: "source-command-impl-cascade-migration"
description: "Имплементирует план cascade-migration: перевод потребителей economic_tier на LocationContext/extend() по слоям (M1–M6), удаление TierResolver и building_band, затем параметры M7–M10. Новый чат: /impl-cascade-migration."
---

# source-command-impl-cascade-migration

Use this skill when the user asks to run the migrated source command `impl-cascade-migration`.

## Command Template

# Имплементация: миграция потребителей на каскадный движок

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/cascade-migration.md`](../plans/cascade-migration.md) — **единственный SoT по шагам**: инвентарь старых точек, M1–M6, форма шага параметра, M7–M10, проверки. Не отклоняться.
2. [`.cursor/plans/cascade-params-matrix.md`](../plans/cascade-params-matrix.md) — сверочная матрица параметров (родитель/наследник по уровням).
3. [`docs/tz_cascade_context.md`](../../docs/tz_cascade_context.md) — §4 (движок/`extend`), §6 (stamp на NL), §7 (потребители), §8 (кейсы).
4. [`docs/tz_economic_tier.md`](../../docs/tz_economic_tier.md) §4 (каскад), §9 (поля).
5. [`docs/tz_locations.md`](../../docs/tz_locations.md) — семантика `named_locations.system_economic_tier`.
6. Движок **уже существует и покрыт тестами** — не писать заново:
   - `backend/app/dataModel/cascade/` — `cascadeSpec`, `cascadeGraph`, `cascadeVerify` (generic);
   - `backend/app/dataModel/locations/context/` — `scopeLevel`, `cascadeParams` (`ECONOMIC_TIER`), `locationContext`;
   - `backend/app/application/worldData/context/` — `cascadeLink` (`Link`/`EmptyLink`), `contextResolver` (`extend`);
   - `backend/tests/test_context_extend.py`, `test_location_context_contract.py`.
7. Код старых точек — по инвентарю плана (§«Текущие точки старой логики»).
8. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — атомарность шагов
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — DAG / backend / commit / schema = только `0001`
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)
   - [`.cursor/rules/pojo-world-row-wire.mdc`](../rules/pojo-world-row-wire.mdc) — «обход движка запрещён»

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

Все точки потребления `economic_tier` читают `ctx.economic_tier` из
`LocationContext`, построенного `extend()` на границах scope. Старые
логики (`TierResolver`, `building_band`-проводка, внутренний резолв
`resolve_room_materials`) удаляются физически, не помечаются.

## Правило размещения (любые каскадные работы)

- **Механизм один, домен-нейтрален, дублировать запрещено.** Он живёт в
  `dataModel/cascade/` и `application/worldData/context/`. Новый домен
  не получает свой `cascadeGraph`/`extend` — механизм не копируется.
- **Домен объявляет только своё:** ось, `Cascade`-параметры,
  `CascadeChannel` на полях POJO, контекст-модель, привязки.
- Новый параметр (M7+) — `Cascade` + каналы + поле контекста +
  привязки; enum оси, граф и движок не трогаются.

## Жёсткие запреты

- `TierResolver` удаляется **только в M6** — до него точечно заменять
  вызовы, файл целиком не трогать.
- Не переводить потребители сверх шага своего параметра: `city_size` —
  в M7, `settlement_density` — в M8, `wall/floor_material` — в M9,
  `dominant_material` — в M10. В M1–M6 — только `economic_tier`.
- Обход движка запрещён: локальные `or`-цепочки, ручное наследование,
  свой median/rng/«ближайший к городу» в консьюмере — баг. Новая точка
  наследования — новый канал/звено, не код в консьюмере.
- Stamp `system_economic_tier` на NL — только при отсутствии
  authored-значения (Q4 плана).
- rng — только `Random(_make_seed(world_uid, scope_uid, "tier"))` от
  caller'а, один раз на scope.
- Не новые authored-поля, wire-ключи, schema-изменения. Не `0002_*.sql`.
- Не DAG `application/engine/nodes/`. Не стартовать backend. Не коммитить.
- Не менять фильтрацию `planner/economic.py` (range там — отбор
  шаблонов, не каскад).

## Порядок — строго по шагам плана

M1 (settlement ctx у skeleton, 3 сайта `TierResolver`) → M2 (district +
area ctx до `StructureContext`, stamp district NL, Q4) → M3 (structure:
`generate_from_template(ctx)`, фазы, room ctx) → M4 (materialResolver +
wallOpening — консьюмеры) → M5 (debug `EmptyLink`, NL stamps, §8.4) →
M6 (зачистка: `tierResolver.py`, `building_band`, acceptance).

Дальше — только по отдельной команде мастера: M7 `city_size` → M8
`settlement_density` → M9 `wall/floor_material` → M10
`dominant_material`, каждый по общей форме шага параметра.

**Правило мастера:** каждое сообщение мастера после отчёта = приступать
к следующему шагу, **если** в нём нет фидбека по ревью кода. Фидбек —
сначала обработать, шаг не начинать.

После каждого шага: что сделано / файлы / проверки (чем прогнал) / что
осталось / что сознательно не тронуто. Один шаг за заход — без исключений.

## Приёмка (из плана)

- Детерминизм ×2 на seed; effective tier идентичен во всех фазах — один
  резолв на scope.
- WARNING при пустой цепочке один раз на scope; без WARNING при
  authored tier.
- Кейсы tz_cascade §8.1–8.4 на POJO-фикстурах; persist + перегенерация
  (§8.4): stamped NL не перебивается повторным резолвом.
- После M6: `grep -rn "TierResolver\|building_band" app` — пусто;
  `tierResolver.py` удалён; `tz_economic_tier.md` §8 обновлён под
  `LocationContext`; полный прогон backend-тестов.
- compileall изменённых модулей, `git diff --check` после каждого шага.

## Старт

Прочитай `cascade-migration.md` целиком + файлы точек из инвентаря.
Затем шаг M1.
