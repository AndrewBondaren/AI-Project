---
name: "source-command-impl-p3-declared-lakes"
description: "Имплементирует P3-срез W3: миграция legacy declared_lakes на общий placement-контракт — shoreline ring → intent → ResolvedWaterPlacement(kind=lake) через водный adapter; regression compatibility, без pipeline-wiring и carve (остаётся HY-12/3). По generator-placement.md чеклист W3. Новый чат: /impl-p3-declared-lakes."
---

# source-command-impl-p3-declared-lakes

Use this skill when the user asks to run the migrated source command `impl-p3-declared-lakes`.

## Command Template

# Имплементация: P3-W3 — legacy `declared_lakes` на общий placement

Это **явная просьба писать код** (один срез P3). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/generator-placement.md`](../plans/generator-placement.md) — **единственный SoT**: чеклист P3, строка **W3** («явная судьба legacy declared_lakes + regression compatibility»), общая приёмка срезов, решение A2+B1.
2. [`.cursor/plans/hy-12-sea-elevation-contract.md`](../plans/hy-12-sea-elevation-contract.md) — § «Единый механизм» (`DeclaredLake` нормализуется в `DeclaredBasin`-путь), § «Legacy-код» (`lakeSpecs`/`lakeBasinGenerator` — судьба), POJO-контракты `WaterBody`/`BasinKind`.
3. [`docs/tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) — § U25 (lake vs inland_sea по subtype; mismatch → warning + carve по edge type).
4. Кодовое состояние (сверить, не с памятью):
   - `application/worldData/placement/adapters/water.py` — `prepare_water_placements`/`resolved_water_placements`: сейчас `declared_basins` + `declared_coastlines`; `declared_lakes` **не подключён**
   - `adapters/coastlineShape.py` (`coastline_cells`, `_ring`), `adapters/waterShape.py` (`shape_cells`), `adapters/waterTypes.py` (`WaterPlacementContext`, `PreparedWaterEntry`, `WaterPreparationCode`)
   - `dataModel/placement/water.py` — `ResolvedWaterPlacement {placement, z_water_level, kind, liquid}` (liquid: `MaterialKey`)
   - legacy: `basins/lakeSpecs.py` (`extract_lake_specs` → `LakeSpec`), `basins/lakeBasinGenerator.py` (`carve_lake_interior`: `rim_z = max(land_shore z)`, `floor = max(0, rim_z − shelf − 1)`), `basins/basinKindResolver.py` (`resolve_lake_basin_role` — U25 subtype→role, mismatch → warning)
   - `dataModel/hydrology/declaredLake.py` (`location_uid`, `shoreline` ring), `lakes.py` (`HydrologyLakesPolicy.basin_depth=5`, `min_water_cells`), `worldHydrology.py` (`declared_lakes`, `default_lakes`)
   - тесты: `test_hydrology_declared_wire`, `test_hydrology_determinism`, `test_hydrology_hy12_contract`; fixture `world_test_004` (moon lake — дегенеративный контур)
5. Правила (нарушение = стоп): `contract-creation.mdc` (инвентаризация; `MaterialKey`/StrEnum), `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`, `code-gates.mdc`, `project-context.mdc` (не DAG, не коммит, **не стартовать backend**), `class-size-limit.mdc`.

## Границы среза (жёстко)

- **Только adapter-сторона:** `declared_lakes` → placement intent → `ResolvedWaterPlacement`. Общий resolver P2 уже реализован — собственный resolve не создавать.
- **Pipeline wiring НЕ делать** — production-вызов pre-1.4 прохода и consumer `basinSpecFactory`/`basinZ` — это HY-12 шаг 3.
- **Legacy materialize НЕ трогать:** `extract_lake_specs`, `lakeBasinGenerator`, `LakeSpec` продолжают работать как раньше; dual-path допустим пока HY-12/3 не переключил materialize. Никакого двойного carve.
- `DeclaredLake` wire-контракт не ломать: `location_uid` + `shoreline` ring остаются; расширения (напр. `liquid`) — только явным решением в этом срезе с записью в план, не молча.

## Контракт среза — закрыть явно

1. **Footprint:** `DeclaredLake.shoreline` — замкнутое кольцо → footprint = **interior** кольца (вода внутри). Переиспользовать существующую ring-геометрию (`coastline_cells`/`_ring` — closed-ветка) или polygon-rasterize через `topology`; unrolled, через шов. Дегенеративный контур (кольцо на grid-линиях, moon lake) — interior = сами клетки кольца, как в legacy `_resolve_interior` fallback.
2. **`kind`:** `LAKE`. U25 mismatch-семантика сохраняется как **notice** (`WaterPreparationCode`/issues-канал), не warning-in-code отдельного вида: subtype `inland_sea` на lake-shoreline → notice + `LAKE`; subtype `lake` на non-lake shoreline → notice + `LAKE`. Для subtype-lookup потребуется вход `location_uid → GeographicSubtype` — решить способ передачи в `WaterPlacementContext` (новое поле контекста или hydrology-side resolve) **по contract-creation**; фактическая классификация массой/уровнем остаётся `waterClassifier` (HY-12/4).
3. **`z_water_level`:** у `DeclaredLake` нет уровня — terrain-derived. Рекомендация: воспроизвести legacy семантику `rim_z = max(z land-кольца вокруг interior)` по `context.surface_z` (pre-carve) и записать её как `declared_level`/level записи; альтернатива pour-point/min-rim — если выбираешь её, **остановись и спроси мастера** (семантика отличается от legacy).
4. **`floor_z`:** `level − default_lakes.basin_depth`, валидация `z_min ≤ floor < level` — как у basin-ветки adapter'а.
5. **`liquid`:** `MaterialKey` = `"water"` (default) — `DeclaredLake` поля liquid не имеет; если считаешь расширение оправданным — только после отметки в плане.
6. **`placement_specificity`:** отсутствует у `DeclaredLake` → `None` (как у coastline) — правило политики в P1/ТЗ, не локальный литерал.
7. **`water_body_uid`/identity:** `location_uid` = source identity; auto-uid правила (`waterBodyIdentity`) применяются только к auto-tele, не к declared.

## Проверка

- Новые unit-тесты: lake ring → intent → `ResolvedWaterPlacement(kind=LAKE, level, cells)`; interior/exterior, дегенеративное кольцо, mismatch-notice, floor-валидация, wrapped-шов; детерминизм (перестановка входа).
- Регрессии: `test_hydrology_declared_wire`, `test_hydrology_determinism`, `test_hydrology_hy12_contract` + placement-наборы — без новых падений; legacy `generate_lakes` путь не затронут.
- `python -m compileall` changed modules; `git diff --check`.

## Done

- `prepare_water_placements` покрывает `declared_lakes`; resolved-записи корректны; legacy-ветка зелёная; чеклист W3 в `generator-placement.md` → `[x]` + краткая запись о принятых решениях (level/floor/kind/liquid/notice-канал).
- Не объявлять: production materialize, `LakeSpec` удалён, HY-12/3 закрыт. Шаг за заход, отчёт — жди «ок».
