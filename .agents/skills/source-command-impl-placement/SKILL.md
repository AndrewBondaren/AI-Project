---
name: "source-command-impl-placement"
description: "Имплементирует общий placement всех объектов генератора (P0–P3): инвентарь потребителей, typed-контракт dataModel/placement/, общий resolver application/worldData/placement/, adapters по инвентарю (водный первым — разблокирует HY-12 шаг 3). По плану generator-placement.md. Новый чат: /impl-placement."
---

# source-command-impl-placement

Use this skill when the user asks to run the migrated source command `impl-placement`.

## Command Template

# Имплементация: общий placement всех объектов генератора

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/generator-placement.md`](../plans/generator-placement.md) — **единственный SoT**: целевая архитектура (`dataModel/placement/` + `application/worldData/placement/`), шаги P0→P3, решение A2+B1. Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) § Placement priority — SoT приоритета: `placement_specificity` → площадь → `region_uid`, опора→зависимый.
3. [`docs/tz_runtime_world_edit_policy.md`](../../docs/tz_runtime_world_edit_policy.md) — runtime/preview основа resolver'а.
4. [`.cursor/plans/hy-12-sea-elevation-contract.md`](../plans/hy-12-sea-elevation-contract.md) — главный потребитель: контракт `ResolvedWaterPlacement`, coastline → basin, водный adapter P3 разблокирует его шаг 3.
5. [`.cursor/plans/plan-dependency-graph.md`](../plans/plan-dependency-graph.md) — место трека в карте.
6. Кодовое состояние (сверить с кодом, не с памятью):
   - `dataModel/topology/` — `WorldTopology`, `topologyGeometry.py` (сервисы соседей/метрики — обязательны, raw adjacency запрещён)
   - `dataModel/spatial/regionShape.py` — footprint-механика (`bbox`/`ellipse`/`polygon`/`anchor_radius`, `edge_noise`; `CORRIDOR` — добавляется в HY-12 шаг 2, при отсутствии не реализовывать самому)
   - существующие точки placement: masks/regions (`application/worldData/masks/`, `regions/`), landcover-сравнение (`coverageResolver`), declare hydrology (`loadDeclaredHydrology`), runtime/worldEdit код
   - `dataModel/placement/`, `application/worldData/placement/` — **целевые папки, пока не созданы**
7. Правила (нарушение = стоп):
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc) — инвентаризация перед новым полем; `RegistryKey`/StrEnum; `str` только с пометкой в ТЗ
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не коммитить, **не стартовать backend**, не создавать `0002_*.sql`
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Зафиксированные решения (кратко — SoT в плане)

- **B1 — позиция resolver'а:** отдельный placement-pass в pipeline — после terrain base heightmap + anchors, до Pass 1.4 (relief spec-apply). Все домены резолвятся одним согласованным проходом на одном снапшоте. Контракт P2: «resolve завершён к моменту spec-apply».
- **A2 — выход adapter'а доменно-нейтрален:** adapter производит resolved-record (`ResolvedWaterPlacement {footprint_cells, z_water_level, kind, liquid, source_uid}` — пример воды), **не** доменный spec. Маппинг record → spec живёт у потребителя (`hydrology/basinSpecFactory`). Resolver/adapter не импортируют доменную физику (bathymetry и т.п.).
- Coastline — контракт создания воды: приоритет **0**, если воды не вышло. Способ достроения footprint и связь с `placement_specificity` согласуются совместно с HY-12 шагом 1 в P1. Цикл «сначала вода, чтобы разместить контракт воды» запрещён.
- Resolver **не** делает carve/fill, persist, lifecycle, собственный повторный REF-W resolver.

## Порядок шагов (по плану, один за заход)

0. **P0 — инвентарь потребителей.** Аудит `dataModel/{locations,terrainMasks,hydrology}/`, `worldData/{masks,generators}/`, jsonValidation contracts. Выход: проверяемый migration inventory — producers, вход/выход, ограничения, опоры, defaults; отдельный список ещё не реализованных объектов. Код не меняется.
1. **P1 — общий typed контракт.** `dataModel/placement/` POJO + ТЗ: intent semantic/absolute, identity, footprint, specificity, опоры/ограничения, resolved/unresolved, диагностика, wire missing/null/full/patch политика. Незаданные решения не заменять defaults.
2. **P2 — общий resolver.** `application/worldData/placement/`: prepared input → deterministic resolve → typed result. Проверки: перестановка входа, опоры, specificity/площади, UID tie, permitted overlap, absolute conflict, full/partial bake, runtime/preview parity.
3. **P3 — adapters по инвентарю, атомарными срезами.** **Первый срез — водный adapter** (declared basin/coastline) — разблокирует HY-12 шаг 3. Локальное paint-сравнение не удалять, пока его ответственность не покрыта общим контрактом. Остальные домены — по чеклисту P0; трек не закрывается без полного инвентаря.

## Жёсткие запреты

- Не создавать resolver внутри доменов-потребителей (hydrology и др.) — только общий.
- Не делать carve/fill/persist/lifecycle в resolver; не выбирать доменный spec на выходе adapter'а.
- Ни одного raw adjacency/евклида на мировых координатах — только `dataModel/topology` сервисы.
- Не расширять молча: миграция всех consumers — только по инвентарю P0 срезами.
- Не DAG-ноды, не schema `0002_*.sql`, не коммит, не старт backend. Класс ≤300 строк.

## Приёмка

- `python -m unittest` — placement наборы + регрессии мигрированного среза; `python -m compileall`; `git diff --check`.
- Детерминизм: перестановка входа → тот же результат; tie-break по контракту P1.
- После P3-вода: HY-12 может потреблять `ResolvedWaterPlacement` — шаг 3 разблокирован.
- План → `-done` только после закрытия полного инвентаря миграции; частичное состояние фиксировать чеклистом в плане.

## Старт

Прочитай план + `tz_map_light_bake.md` § Placement priority. Начни с **P0 — инвентаря**: отчёт таблицей (consumer → путь → вход/выход → опоры → статус), код не трогать.
