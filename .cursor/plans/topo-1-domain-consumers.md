# TOPO-1 — топология как домен: все генераторы на швах

**Трек:** системный. **Долг:** TOPO-1 в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md).
**ТЗ:** [`tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) § Форма мира / `world_topology_mode` (`WorldTopology` — «единая точка lookup для seam, halo, транзита, растеризации регионов, pathfinding/дистанций, hydrology/z-continuity и climate field на краях»).

## Проблема

`world_topology_mode` default = `wrapped` — мир декларируется тором, но **генерируется planar почти везде**. `WorldTopology` существует, seam-пары на L0 пишутся (`worldSeam`/`gridNeighborHalo`), региональные маски заворачиваются (`fine_topology`) — а вся генерация контента обходит домен сырой смежностью/евклидовой метрикой. На 5×5 мире ~60% клеток — края: это не edge case, а половина карты.

## Целевое состояние

- `dataModel/topology/` — доменный корень: `WorldTopology`, `WorldBounds`, `WorldTopologyMode`, `topologyGeometry` (unrolled metric/centroid/rasterize).
- Ни один генератор не использует raw `neighbors4`/`dist_euclidean`/«край = void» на мировых координатах — только сервисы домена.
- Потребитель не ветвится по mode (мастер-принцип: домен владеет геометрией шва).

## Карта консьюмеров (инвентарь по коду)

| Домен | Точки разрыва | Статус | Трек |
|---|---|---|---|
| **Маски/landcover** | `regionRasterContext.fine_topology`, `rasterize` `canonicalize`, `smooth_field` | ✅ проводной — эталон | — |
| **Pack seam/halo** | `worldSeam.py`, `gridNeighborHalo.py` | ✅ пишется | — |
| **Гидрология (моря, HY-11)** | Unrolled flood + canonical passability, доменная метрика/centroid, canonical rasterize, топологический sea-autoresolve | ✅ HY-11: 233 теста и light/full HTTP smoke world_test_004, вода на gx=+2 | **HY-11** — домен + первый консьюмер закрыты |
| **↳ реки** | D8 через `topologyGeometry`, canonical IO/локальная развёртка поворотов, mouth по resolved waterline; wrapped seam и sphere fold проверены | ✅ HY-12/5 (2026-10-21) | Шаг 5 HY-12; финальная coarse-приёмка — шаг 6, динамические системы — W/L |
| **Климат** | `ClimatePoleField.sample` → `dist_euclidean` к полюсам; зоны-полосы обрываются на шве (COV-1 пересечение) | ❌ | план при постановке |
| **Рельеф** | `relief/discover/*` (apron, fronts, rim, seam), `reliefObjects/depressionDetect` | ❌ | план при постановке |
| **Горы** | `terrain/mountains/geom.py`, `sideFill`, `rangeSideFill` | ❌ | план при постановке |
| **Локации** | anchors/pins — планарные позиции; settlement/district «neighbor» — внутренний граф, не мировая топология | ❌ | план при постановке |

## Очередь треков

1. ✅ **Домен**: корень `dataModel/topology/` + unrolled-сервисы — HY-11 выполнен.
2. ✅ **Морская гидрология** — [HY-11](hy-11-topology-domain-geometry-done.md) — HTTP smoke на реальном мире выполнен; river D8/waterline выполнены шагом 5 HY-12 (2026-10-21).
3. **Климат** — pole blend через `topology.dist2` (план отдельно).
4. **Рельеф/горы** — discover/fill через домен (план отдельно).
5. **Локации** — позиционирование/claims через `canonicalize` (план отдельно).

## Связанные планы и долги

| Артефакт | Связь |
|---|---|
| [hy-11-topology-domain-geometry-done.md](hy-11-topology-domain-geometry-done.md) | **дочерний трек** — домен-сервисы + гидрология-консьюмер |
| [hy-6-coastline-water-side-done.md](hy-6-coastline-water-side-done.md) | prerequisite ✅ — water-side контракт + `passable`-шов |
| [coastline-forms.md](coastline-forms.md) | спайн через шов — потребитель `rasterize`/метрики домена (HY-9) |
| HY-10 (band в L0) | band через шов — координация с `tz_world_pack_storage` § Шов мира L0 |
| HY-8 (вода-уровень) | `passable`-предикат и topology-lookup — одна точка расширения flood |
| [hy-12-sea-elevation-contract-done.md](hy-12-sea-elevation-contract-done.md) | declare-бассейн: footprint + level-fill через домен; шаг 5 закрывает «↳ реки» |
| COV-1 (бритвенные границы) | пересечение: climate-полосы на шве — после подключения климат-трека |

## Новые связи гидрологии (2026-10-20)

[Общий placement](generator-placement.md) использует домен топологии для геометрии размещения; HY-12 — для carve/fill и устьев. [Водные системы](hydrology-water-systems.md) потребляют подтверждённые соединения после HY-12, не выводят связь по raw adjacency или bbox. [Lifecycle](entity-lifecycle.md) не владеет геометрией и не зависит от WorldTopology. Полная карта: [plan-dependency-graph.md](plan-dependency-graph.md). Закрытие строки «↳ реки» означает готовность геометрии/устья, а не реализацию динамической системы или lifecycle.

## Жёсткие запреты трека

- Ни один консьюмер не реализует собственный wrap/евклид на мировых координатах — найденный = баг-дубль (как HY-11).
- Новый сервис топологии — только в домене (`dataModel/topology/`), не в консьюмере.
- Каждый домен — свой план и свой smoke; общие сервисы не меняются под консьюмера без правки ТЗ.
