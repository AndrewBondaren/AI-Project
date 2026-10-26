---
name: "source-command-impl-wilderness-5b"
description: "Имплементирует шаг 5b плана wilderness-regions-mechanic: LandcoverMaterializer плагин LANDCOVER (load_declared/load_anchor_specs/autoresolve_specs/collect/materialize/apply) + autoresolve-модули seedGrid/claim/mergeSublocations; declared без climate-veto, declared_without_suitability warning. Входы закрыты: 2, 3, 4 (RegionRasterizer → topology), 5a (CoverageResolver). Новый чат: /impl-wilderness-5b."
---

# source-command-impl-wilderness-5b

Use this skill when the user asks to run the migrated source command `impl-wilderness-5b`.

## Command Template

# Имплементация: wilderness-5b — `LandcoverMaterializer` + autoresolve

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):**
1. Шаг 4 — `RegionRasterizer` (`rasterize_light`, claim-членство) в `masks/regionRasterizer.py` (→ значит и topology 1–2).
2. Шаг 5a — `CoverageResolver` + `RegionFacts` + fact consumers.
3. Шаг 2 — Specs/`LandcoverDeclareEntry`; шаг 3 — `region_uid`-формула.
Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **5b** (цель/ТЗ/файлы/проверка); §5 **#4** (seed-решётка `(sx,sy)`, джиттер, claim `w=f(dist)+шум`, `max_radius`, слияние одно-видовых seed'ов → регион + саблокации через `Facing`, canonical min = `region_uid`), **#6** (hydro-индексация в общий слой — `declared_*` + cell roles в region entries; владение init у hydro), Declaration без veto. Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § **MaskDomain materialize** (протокол плагина: `load_declared`/`load_anchor_specs`/`autoresolve_specs`/`collect`/`materialize`/`apply`), § Регионы покрытия › **Autoresolve**, › **Declaration и suitability** (`declared_without_suitability` warning).
3. [`docs/tz_flora.md`](../../../docs/tz_flora.md) — FL3c: A∧B veto только для autoresolve-кандидатов.
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc) — ни один класс > 300 строк (в проверке плана)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/generators/terrain/` — существующие materializer-плагины (mountains и др.) по протоколу `MaskDomainMaterializer` — образец оркестрации, не копия логики.
- `backend/app/application/worldData/masks/regionRasterizer.py` — `rasterize_light`/`rasterize_fine`, claim-членство (шаг 4). Здесь claim — **оркестрация** над готовой функцией.
- `backend/app/application/worldData/regions/` — `CoverageResolver`, `RegionFacts`, `factConsumers` (шаг 5a): вид seed'а = resolver на контексте seed.
- `backend/app/ids/deterministicIds.py` — `seeded_u01`/`seeded_index` + каналы `UidKind.REGION`; `seed_root(world)`; формула `region_uid` (шаг 3): declared `name`, anchor `anchor_uid`, autoresolve `seed_xy`, canonical min.
- `MaskDomainId.LANDCOVER` — единый домен; `FORESTS`/`PLAINS` + `default_*` — transitional (10b), здесь **не удалять и не дублировать**.
- `dataModel/spatial/facing.py` — `Facing` для меток саблокаций («Северный»/«Южный»).
- Hydrology `declared_*` + cell roles — индексируются в region entries (общий слой #6); hydro init не трогается.

## Скоуп шага 5b — строго по плану §4

- `backend/app/application/worldData/generators/terrain/landcover/` — новый пакет:
  - `materializer.py` — `LandcoverMaterializer` по протоколу плагина `LANDCOVER`: `load_declared` (из `WorldTerrainMasks.declared_regions`), `load_anchor_specs`, `autoresolve_specs`, `collect` (`default_collect` + резолв `AnchorRadiusShape` anchor→центр + state-lookup из `region_states` — чтение, не запись), `materialize` (Spec→footprint через `RegionRasterizer`; чистый, без world-зависимостей), `apply` (paint + `region_uid`; tie-break — `regionPrecedence`, шаг 2b).
  - `autoresolve/seedGrid.py` — seed-решётка `(sx,sy)` мировых координат + джиттер `seeded_u01(seed_root(world), REGION, channel="seed", sx=, sy=)`; шаг сетки — масштаб региона (knob).
  - `autoresolve/claim.py` — оркестрация: вид seed'а через `CoverageResolver` на seed-контексте; claim `w=f(dist)+шум` (`channel="claim"`), `max_radius`; обход — `topology.neighbor`.
  - `autoresolve/mergeSublocations.py` — связная компонента seed'ов одного вида в пределах `max_radius`-графа → **один регион**; каждый seed — саблокация (uid от своего seed, `Facing` относительно региона, наследует specificity); `region_uid` = canonical min `seed_xy`.
  - **Declared/anchor — без climate-veto:** `current_type = entry_type` стартовое; declared forest при B=∅ → `logger.warning` `landcover | declared_without_suitability | region_uid=… entry_type=forest`, paint выполняется; autoresolve forest при B=∅ → не ставится (veto FL3c через resolver).
  - Hydro-индексация: `declared_*` + cell roles → wilderness region entries со статусом (чтение, не переписывание hydro init).
- Юнит/smoke по приёмке ниже.

- **Не в шаге 5b:** wiring в `run_mask_domain`/contributor (шаг 6), L2 (7), manifest entries (8), `region_states` запись (9), `StateChangeConsumer` (10a), cutover `FORESTS`/`PLAINS` (10b). Materializer готовится к подключению, но подключается в 6.

## Жёсткие запреты

- Решётка в **мировых** координатах, не по тайлам — одинаковое множество seed'ов при partial и full bake (bake-scope не входит в seed/claim формулы).
- Нет своих рандомов/`mod`-обходов — каналы + `topology.neighbor`/`canonicalize`.
- `materialize(spec, scale)` чистый: резолв anchors и state-lookup — только в `collect`.
- Домены не назначают тип: вид seed'а — через `CoverageResolver`, не if-цепочка.
- Hydro init/роли не переписываются — только индексация в entries.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 5b)

- `python -m compileall backend/app` — чисто; ни один класс > 300 строк.
- Materialize на тест-мире: контур органический (edge_noise + claim-шум); **partial bake == full bake по клеткам** (seed/claim не зависят от scope).
- Declared forest в arid-зоне красится + `declared_without_suitability` в логе; autoresolve там же леса не ставит (veto).
- Merge: соседние seed'ы одного вида → один `region_uid` (canonical min), саблокации с uid от своего seed'а и `Facing`.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь все блокер-условия, сверь протокол `MaskDomainMaterializer` по существующему плагину (mountains), покажи карту пакета `landcover/` (файлы + публичные сигнатуры materializer/collect/autoresolve) до первой правки.
