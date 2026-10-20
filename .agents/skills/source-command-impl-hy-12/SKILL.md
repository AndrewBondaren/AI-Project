---
name: "source-command-impl-hy-12"
description: "Имплементирует HY-12: declare морей = elevation-бассейн (declared_basins[] + BasinKind + z_water_level на водоём), level-fill z < z_water_level, merge/spill уровней через priority-flood, derived shore, реки на waterline. По плану hy-12-sea-elevation-contract.md. Новый чат: /impl-hy-12."
---

# source-command-impl-hy-12

Use this skill when the user asks to run the migrated source command `impl-hy-12`.

## Command Template

# Имплементация: HY-12 — declare морей = бассейн в elevation

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/hy-12-sea-elevation-contract.md`](../plans/hy-12-sea-elevation-contract.md) — **единственный SoT**: целевой контракт (POJO), архитектура/пути, таблица алгоритмов, алгоритм разрешения уровней (переливы, union = система с наследованием уровня), открытые вопросы → шаг 1, шаги 1→6. Не отклоняться.
2. [`.cursor/plans/topo-1-domain-consumers.md`](../plans/topo-1-domain-consumers.md) — родительский трек; строка «↳ реки» закрывается шагом 5.
2a. [`.cursor/plans/generator-placement.md`](../plans/generator-placement.md) — общий placement (P0–P3); **шаг 3 HY-12 заблокирован до P2 + водный adapter P3** (жёсткая зависимость, решение мастера — вариант A: carve только через resolver, обходного пути нет). Шаги 1–2 идут параллельно с P0/P1.
2b. [`.cursor/plans/hydrology-water-systems.md`](../plans/hydrology-water-systems.md) + [`entity-lifecycle.md`](../plans/entity-lifecycle.md) — соседние домены; HY-12 их **не реализует** (поставляет физические факты для W3).
3. [`docs/tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) § SeaBasinGenerator, § Ocean bathymetry, § U15, § Pass 1.4/1.5, § U3/U25 (озеро vs inland_sea). Шаг 1 — пересмотр declare-раздела этого файла.
4. [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md) — строки HY-12, HY-8, HY-BATH-1, HY-7, HY-10, TOPO-1.
5. Кодовое состояние (сверить с кодом, не с памятью — HY-11 resolved, домен существует):
   - `dataModel/topology/` — `WorldTopology`, `topologyGeometry.py` (`neighbors4_unrolled`, `dist2`, `nearest_on_segment`, `centroid`, `canonical_frame`), `fineTopology.py`
   - `dataModel/hydrology/` — `worldHydrology.py`, `declaredCoastline.py`, `declaredLake.py`, `mapCellHydrology.py` (`water_body_uid`, `deepening_index`, `role`), `seas.py` (`HydrologySeasPolicy`)
   - `generators/hydrology/` — `shore/waterSideFootprint.py`, `shore/deepeningBandCarver.py`, `basins/seaBasinGenerator.py`, `basins/oceanBasinGenerator.py`, `basins/seaLevelPolicy.py` (сейчас `resolve_z_sea() = 0` хардкод), `basins/basinKindResolver.py`, `autoresolve/proceduralSeaAutoresolve.py`, `rivers/riverNetworkPlanner.py` (`_neighbors8`), `rivers/riverSpecs.py`, `load/buildHydrologyMasterInput.py`, `load/loadDeclaredHydrology.py`
   - `dataModel/spatial/regionShape.py` — footprint-механика + `edge_noise`
   - `reliefObjects/depressionDetect.py` — локальные минимумы (озёра)
   - тесты: `backend/tests/hydrology_fixtures.py`, `test_hydrology_hy2.py`, `test_hydrology_hy5a.py`, `test_hydrology_hy11.py` (бaseline регрессий — hy2/hy5a писаны под paint-модель, переписываются по плану)
   - fixture: `fixtures/world_test_004.json`
6. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc) — инвентаризация перед новым полем; `str`-поля только с пометкой в ТЗ
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не коммитить, **не стартовать backend**
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Целевой контракт (кратко — SoT в плане)

**Declare = carve elevation, вода = следствие уровня.** У каждого водоёма свой `z_water_level` (`z_sea` → `default_water_level` = океанский дефолт).

Pipeline: **declare → P3 adapter → placement-pass** (отдельная фаза: после terrain base + anchors, до Pass 1.4 — B1; coastline-footprint = bounded downhill по pre-carve z / петля по `water_side`) → `ResolvedWaterPlacement` → **`basinSpecFactory`** (гидрология: record → `BasinSpec` — A2) → очередь Pass 1.4 → **basin carve = relief object** (`terrain/reliefObjects/bathymetry/basinZ.py` — дно океана = домен рельефа, гидрология z не пишет; абсолютная запись — идемпотентно) → **компоненты впадин** с `z_water_level = min(declared, pour_point)` → **level fill** `z < z_water_level` строго → **merge = система** (`S.level = min(max declared, min_rim_z)`, дети наследуют уровень каскадом по `PHYSICAL_MERGE`-предкам и сохраняют uid — слитое тело = родительская система; superseded → warning, факт в паре `declared_level`/`z_water_level`) → **derived SHORE** (land-сосед воды, `z = level` — суша) → **реки** устье на waterline + **waterfalls** (отдельная механика `hydrology/waterfalls/` — перелив через отвесный перепад: ступень русла / sill бассейна / authored drop).

Перед кодом шаг 1 **обязан** закрыть открытые вопросы плана в ТЗ (coastline-без-бассейна + связь с `placement_specificity` совместно с P1, identity источники, sphere-fold, объём `V ≈ A_water × Δz` простым телом — интегралы только для отдельного домена локальной физики игрока).

## Порядок шагов (по плану, один за заход)

1. **ТЗ** — `tz_terrain_hydrology.md`: declare-раздел → бассейн/уровень/fill/shore/merge; закрыть открытые вопросы; дегенераты.
2. **POJO** — `declaredBasin.py`, `enums/basinKind.py`, `enums/waterSide.py`, `waterBody.py` (+`liquid`/`declared_level`/`parent_system_uid`), `DeclaredCoastline += kind/liquid/closed/water_side`, `regionShape.py += CORRIDOR` (path+width, rasterize через `topology.dist`), `WorldHydrology += declared_basins/default_water_level`, `MapCellHydrology += z_water_level`, `seaLevelPolicy` resolve из скаляра, fixture.
3. **basin carve = relief object** — **заблокирован до P2 + водный adapter P3**. `terrain/reliefObjects/bathymetry/`: `basinSpec.py`, `floorProfile.py` (piecewise shelf→slope→abyss по kind), `distanceField.py` (multi-source BFS), `basinZ.py`; dispatch в `applyReliefObjectsZ.py`; cap `bands.max`; до fill и river pass.
4. **level fill + компоненты + shore** — `hydrology/water/`: `levelFill.py`, `componentLabel.py`, `waterBodyResolver.py`, `waterClassifier.py`, `shoreDerive.py`; классификация ocean/inland_sea/lake (на торе — по уровню/массе, не по краю); merge = union-система с наследованием уровня детьми.
5. **реки** — устье `z < z_water_level` ИЛИ open-water роль; `_neighbors8` → домен (`neighbors8_unrolled` при отсутствии).
6. **coarse smoke** — `world_test_004` + declared basin → footprint/z/уровень/роли/shore в coarse heightmap + hydro index, через шов на wrapped; re-bake детерминирован. L0 render — только диагностика до HY-10; backend через мастера.

## Жёсткие запреты

- Оркестрация — внутри `generators/hydrology/` (`waterBodyAssembler.py`, `riverNetworkAssembler.py`, facade = `hydrologyGeneratorService`); **не** в `assemblers/` — там settlement-домен. Per-kind классы (`OceanAssembler`/`SeaAssembler`) запрещены — один assembler, параметр `BasinKind`.
- Не реализовывать HY-9 (формы берега), HY-10 (band→L0 — только минимальная проводка ролей если требует smoke), HY-7 (прецеденс горы — после), COV-1, неоднородное дно (DepressionSpec внутри воды).
- **Не реализовывать placement resolver, водные системы, lifecycle** — соседние планы (P0–P3, W0–W3, L0–L3); HY-12 поставляет физические факты, не их инфраструктуру. Собственный placement resolver в `generators/hydrology/` не создаётся.
- Не трогать климат/рельеф/горы/локации — свои треки TOPO-1 (дно бассейна — `terrain/reliefObjects/bathymetry/` — единственное разрешённое расширение в relief).
- Carve — только абсолютный z и только через общий resolver (жёсткая зависимость шага 3 от P2+P3); запрещён дельта-carve и обходной прямой carve из declare.
- Ни одного raw adjacency/евклида на мировых координатах — только `dataModel/topology` сервисы.
- Не DAG-ноды, не schema `0002_*.sql`, не коммит, не старт backend. Класс ≤300 строк.

## Приёмка

- Новые тесты (carve planar/wrapped, fill `z < z_water_level`, `z = level` = суша, merge-уровни, puddle-порог, река→waterline) зелёные; baseline без новых падений.
- `compileall`, `git diff --check`; grep raw-neighbors по `generators/hydrology/` → 0.
- Smoke: водоём по форме footprint в render; отчёт шагов.
- HY-12 → `resolved`; план → `-done`; статусы HY-8/HY-BATH-1 обновлены в реестре.

## Старт

Прочитай план HY-12 + `tz_terrain_hydrology.md` § SeaBasinGenerator/Ocean bathymetry + `seaLevelPolicy.py`. Затем шаг 1 (ТЗ) — сначала закрыть открытые вопросы мастером, если они не решены в ТЗ.
