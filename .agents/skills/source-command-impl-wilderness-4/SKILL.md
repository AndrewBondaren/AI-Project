---
name: "source-command-impl-wilderness-4"
description: "Имплементирует шаг 4 плана wilderness-regions-mechanic: RegionRasterizer — shape/claim → frozenset[LightCellRef] (L0) и set[Coord] (fine), seam через topology.canonicalize, обход seed-решётки через topology.neighbor. Блокер: surface-topology шаги 1–2 (WorldTopology). Входы закрыты: 2 (RegionShape). Новый чат: /impl-wilderness-4."
---

# source-command-impl-wilderness-4

Use this skill when the user asks to run the migrated source command `impl-wilderness-4`.

## Command Template

# Имплементация: wilderness-4 — `RegionRasterizer`

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (оба):**
1. `backend/app/dataModel/worldPack/wire/worldTopology.py` с `WorldTopology` (`canonicalize`, `neighbor`) — сдан surface-topology.md шагами 1–2. **Здесь не создаётся** — владелец другой план. Нет → стоп, доклад мастеру (или сначала запустить трек surface-topology).
2. `RegionShape`/`EdgeNoise` из шага 2 в `dataModel/spatial/regionShape.py`. Нет → стоп.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **4** (цель/ТЗ/файлы/проверка); §5 #4 (seed-решётка/claim — обход через `topology.neighbor`), #5 (L0/L2: одна shape → два rasterize, L2 поточечно в fine-координатах), #7 (edge_noise применяется **здесь**, не в `contains`). Не отклоняться.
2. [`.cursor/plans/surface-topology.md`](../../../.cursor/plans/surface-topology.md) — контракт `WorldTopology`: `canonicalize` (seam-координаты), `neighbor` (обход по режимам), режимы `planar`/`wrapped`/`sphere`. Знать сигнатуры — использовать, не переизобретать `mod`.
3. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **RegionShape** (resolution-independent SoT), › Autoresolve (claim-функция `w = f(dist) + seeded-шум`, `max_radius`), › L0/L2.
4. [`docs/tz_terrain_generation.md`](../../../docs/tz_terrain_generation.md) — § Форма мира (seam-семантика после surface-topology шага 1).
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/masks/footprint.py` — `LightCellRef` (тип клетки L0); `MaskFootprint` — контракт materialize для L0, **не** обобщать на fine-сетку.
- `backend/app/dataModel/spatial/regionShape.py` — `RegionShape` union, `contains(x,y)`/`bbox()`/`area()` чистые (без шума) — вход из шага 2.
- `backend/app/dataModel/worldPack/wire/worldTopology.py` — `WorldTopology` после surface-topology 1–2 (предусловие); `wrap_owner_and_other` — идиома canonical owner (использовалась в #4 для `region_uid` минимального seed — контекст, не код).
- `backend/app/ids/deterministicIds.py` — `seed_rng`/`seeded_u01` + каналы (`channel="edge"`, `channel="claim"`, `channel="density"`) — шум берётся отсюда, своего рандома нет.
- `dataModel/spatial/facing.py` — `Facing` (контекст для саблокаций, в этом шаге не используется).

## Скоуп шага 4 — строго по плану §4

- Новый `backend/app/application/worldData/masks/regionRasterizer.py` — растеризация `RegionShape` **одной** геометрии в **две** сетки:
  - L0: `rasterize_light(shape, world, spec_ctx) -> frozenset[LightCellRef]` — membership = `contains` в light-координатах ∧ `edge_noise`-маска (`seed_rng(seed_root(world), REGION, channel="edge", uid=…, x=, y=)`), decay от геометрического края;
  - L2/fine: `rasterize_fine(shape, world, spec_ctx) -> set[Coord]` — та же формула в метровых координатах (поточечно — контур чёткий, не лесенка L0);
  - **density** (`spec.density < 1.0`): `channel="density"` маска — применяется здесь, внутри footprint;
  - **claim** (autoresolve, вход — seed-точки + `max_radius`): растеризация по `w = f(dist) + claim-шум` (`channel="claim"`), обход соседей — `topology.neighbor`, граница — мир, не тайлы. Claim-**оркестрация** (seed-генерация, merge саблокаций) — шаг 5b; здесь только функция членства/растр по уже заданным seed'ам;
  - **seam**: все координаты через `topology.canonicalize` — shape у шва красит обе стороны при `wrapped`; при `planar` клетки за краем отсутствуют (`neighbor → None`).
- Обход ограничен `shape.bbox()` (канонизированным) + `max_radius` для claim — скан не по всей карте.
- Pure: никакого I/O, записи в клетки, логирования warn по умолчанию — вернуть множества; диагностика — на вызывающих (шаги 5b/6/7).
- Юнит-тесты по приёмке ниже.

- **Не в шаге 4:** `CoverageResolver` (5a), `LandcoverMaterializer` и autoresolve-оркестрация seed/merge (5b), paint в `system_terrain`/`region_uid` (6/7), `MaskFootprint` интеграция (6), topology сам (surface-topology).

## Жёсткие запреты

- Одна формула членства на обе сетки — разные геометрии для L0/L2 запрещены (иначе контур на L2 ≠ L0, это и есть баг, который лечим).
- Нет своего wrap/`mod % width` — только `topology.canonicalize`/`topology.neighbor`.
- `edge_noise`/`density`/`claim` — только через каналы `UidKind.REGION` + `seed_root(world)`; никакого `random()`/`bake_seed`.
- `contains`/`bbox`/`area` в `regionShape.py` не править — шум применяется растеризатором, shape чистый.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 4)

- `python -m compileall backend/app` — чисто.
- Юнит: та же `RegionShape` → обе сетки (fine-множество покрывает те же координаты при даунскейле); `edge_noise` даёт органический край (не шахматка, детерминистичен по повтору).
- При `world_topology_mode=wrapped` seam-регион красит оба края (координаты canonicalize совпадают на левом/правом краях); при `planar` клетки за границей не возвращаются.
- Claim: две клетки с одинаковым входом → одинаковое членство независимо от scope обхода; кап `max_radius` соблюдён.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь оба блокер-условия (если `WorldTopology` нет — доложи мастеру, что нужен трек surface-topology), сверь сигнатуры `canonicalize`/`neighbor` с контрактом surface-topology, покажи API `rasterize_light`/`rasterize_fine`/claim до первой правки.
