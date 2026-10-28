# GEO-1 G3-R — уточнение входного контракта — DONE

Статус: COMPLETE 2026-10-28; реализовано и проверено в G3-R после согласования мастером.
Дата: 2026-10-28. Основной шаг: [G3-R](./geo-1-designed-water.md#g3-r--площадь-области-генерации-от-домена-региона).

## Причина уточнения

На входе G3-R/§6.3 задавали prepare_terrain_regions → TerrainRegionsSnapshot.
Поздние §6.29-E/M задавали TerrainRegionPlan(snapshot, coverages), общий точный
span measure и RegionGeometryInput. Это более широкий контракт, чем два extent
POJO: coverage требуется для последующих union/budget операций без повторной
геометрической работы. Нельзя реализовать обе разные return signatures одного
entry point или молча выбросить coverages из результата.

§6.29-E задаёт union(tuple[RegionCoverage,...]) → RegionCoverage и
intersection/subtract. На RegionCoverage обязателен region_uid, но не задан
владелец результата операции над разными region_uid, включая пустой union.
§6.3 запрещает неоговорённый UID mint. Выбор UID первого operand был бы
неявным правилом identity и зависел бы от порядка входа.

Это уточнение сигнатур и owning paths; площадь/топология/процент воды,
authored defaults и production gate G10-A не переоткрываются.

## Согласованный единый контракт

### 1. Результат provider

prepare_terrain_regions(world: RasterWorld, *, snapshot_uid: EntityUid,
world_region_uid: EntityUid, inputs: TerrainRegionPlanningInput) → TerrainRegionPlan.

RasterWorld — существующий readonly protocol regionRasterContext.py с одним
world_uid. Caller передаёт coherent captured view, не raw world JSON.
Existing seed_root(world) остаётся единственным механизмом seed identity;
provider не дублирует его формулу. snapshot/world region UID передаются caller;
provider не создаёт новые identity.

TerrainRegionPlan содержит snapshot: TerrainRegionsSnapshot и
coverages: tuple[RegionCoverage,...]. Extents строго соответствуют measure.area
coverages; snapshot/coverages вычисляются за один проход. Water/budget consumers
получают plan.snapshot и нужную coverage, без повторного rasterize/shape.area.

TerrainRegionsSnapshot содержит world_uid, snapshot_uid, world_region|None и
regions tuple. regions не дублирует world_region. UID уникальны; world region
существует только при declared fixed bounds, берётся из resolved topology.bounds
с sphere even-width normalization. AABB при отсутствии authored bounds не
создаёт world_region. Неравные identity на consumption boundary — явная ошибка.

region_for(uid) → TerrainRegionExtent|None — lookup на snapshot.
require_terrain_region(snapshot, *, world_uid, snapshot_uid, region_uid) →
TerrainRegionExtent — application boundary: mismatch/missing приводит к
existing PlanBuildFailure + FieldPathError с domain enum code, не к bbox fallback.

### 2. Identity результатов coverage algebra

RegionCoverageMeasure.area(coverage) → int.
RegionCoverageMeasure.union(coverages, *, region_uid: EntityUid) → RegionCoverage.
RegionCoverageMeasure.intersection(a,b, *, region_uid: EntityUid) → RegionCoverage.
RegionCoverageMeasure.subtract(a,b, *, region_uid: EntityUid) → RegionCoverage.

Владелец результата всегда явно передаётся caller, в том числе для пустого union.
Это уже известный UID нужной generation region/source; implicit mint, случайный
UID, выбор первого operand и alias исходной геометрии не используются.
Площадь не зависит от UID или порядка operand; возвращаемые spans canonical.

### 3. Точная мера и общий predicate

Используется existing RegionShape + typed canonical coverage claim owners.
RegionGeometryInput и TerrainRegionPlanningInput — exact схемы §6.29-M;
SurfaceGridSettings и WaterAnchorInput переиспользуются из существующих модулей.
Не вводятся параллельные anchor/grid/shape contracts.

Из existing regionRasterizer._membership выделяется публичный geometry_membership
в том же файле. Старый _membership вызывает его, затем _density. Поэтому L0/L2
rasterizer сохраняет прежние результаты, а extent измеряет geometry до density.
Existing boundary_depth/smooth_field/seed channels переиспользуются.

Span conversion выполняется по integer-index membership: bbox intervals,
row conversion ellipse/polygon/corridor; anchor_radius разрешается по ready
anchor в существующую shape. Noised boundary проверяется тем же predicate с
amplitude bound для внутренней области. Canonicalization/dedup на wrapped/sphere
швах принадлежит WorldTopology; fine topology получается existing fine_topology.
Нет fine-world array, wet-cell count, shape.area() estimator или отдельной
формулы bbox площади у water consumer. Existing claim coverage поступает до
paint-density и измеряется как готовые canonical spans.

### 4. Границы G3-R/G10-A

По §6.29-J G3-R — contracts-only/pure implementation с isolated typed tests.
Active SurfacePlanningAssembler.prepare, waterPlacementPass и SurfaceHeightmap
не переключаются и не получают optional parameter с молчаливым старым fallback.
Их target wiring выполняется одним G10-A switch через TerrainRegionPlan и
Geo contracts. Source owner refs сохраняются; graph cycle checks и registration
выполняются existing planning machinery на owning provider composition boundary.
Provider не распознаёт post-hydro deps по строковым префиксам contract_id.

## Точные owning paths для реализации G3-R после согласования

- dataModel/terrain/regions/__init__.py — namespace.
- dataModel/terrain/regions/terrainRegionExtent.py — TerrainRegionExtent и
  RegionExtentIssueCode; strict nonnegative fine-cell² area, EntityUid.
- dataModel/terrain/regions/terrainRegionsSnapshot.py — snapshot и TerrainRegionPlan.
- dataModel/terrain/regions/coverageGeometry.py — CoverageSpan/RegionCoverage.
- dataModel/terrain/regions/regionPlanningInput.py — RegionGeometryInput,
  TerrainRegionPlanningInput; existing shapes/grid/anchors/PlanRef.
- application/worldData/generators/terrain/regions/__init__.py — namespace.
- .../regions/coverageMeasure.py — единая canonical interval algebra.
- .../regions/shapeCoverage.py — точный scan conversion/shared predicate adapter;
  не placement resolver, не source identity owner.
- .../regions/regionExtent.py — prepare_terrain_regions и consumption identity/lookup guard.
- application/worldData/masks/regionRasterizer.py — extraction geometry predicate
  без изменения density, seed, claim competition или L0/L2 sampling.
- tests/geo1/regions/{__init__,test_coverage,test_extent,test_membership}.py;
  existing test_region_rasterizer.py; typing planning fixtures/config.

Счёт файлов: новые dataModel/terrain/regions — 5; application terrain/regions — 4;
tests/geo1/regions — 4. Existing masks — 12→12 непосредственных файлов (WARN);
там меняется существующий модуль, новые файлы не добавляются.

## Проверки и done

Small bounded brute-force сравнивается с тем же geometry predicate для всех
shape kinds, edge noise, negative/unrolled coordinates и всех topology modes.
Проверяются seam alias dedup, density independence, claim spans, anchors,
coarse→fine² units, sphere normalized world extent, missing fixed bounds,
empty regions, world/snapshot mismatch и explicit unresolved lookup.
Union/intersection/subtract проверяются на overlapping/disjoint intervals,
empty input и перестановках operand с явной result identity.
Full/partial requests не изменяют plan; provider не принимает tile clipping.
Existing rasterizer tests подтверждают unchanged L0/L2 paint.

Done: один terrain-owned exact measure и plan snapshot; typed consumer получает
готовый extent без своей геометрии. Active production wiring остаётся G10-A.

G3-R IMPLEMENTED/VERIFIED (2026-10-28): 262 tests (192 GEO-1 + 52 cascade + 18 rasterizer),
positive typing 280 файлов — 0 ошибок; negatives planning 107/107, cascade 19/19.
Full cascade-check сохраняет 16 baseline registry errors. Source owner ref проверяется
по world identity; graph cycle checks/codec registration выполняются owning composition в G10-A.
