---
name: "source-command-impl-geo-1-pc10"
description: "Имплементирует PC-10 плана geo-1-designed-water.md: L0 consumer cutover — bakeContext и lightGrid contributors (relief/climate/mountain/ravine/hydro) на frozen plans из SurfacePlanBundle. Входы закрыты: PC-0…PC-9 (включая PC-8 R-разделение, PC-8C, PC-9A). Новый чат: /impl-geo-1-pc10."
---

# source-command-impl-geo-1-pc10

Use this skill when the user asks to run the migrated source command `impl-geo-1-pc10`.

## Command Template

# Имплементация: GEO-1 PC-10 — L0 consumer cutover на frozen plans

Это **явная просьба писать код** (шаг PC-10 плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/geo-1-designed-water.md`](../plans/geo-1-designed-water.md) — **единственный SoT**. Обязательные разделы: §7 PC-10 (тело шага), §6.30 (mountain contract — один layout на три consumers, смешанное состояние запрещено), §6.31-B/C/D/E (MountainLayout/LightReliefPlan/DeclaredWaterPaint схемы, bindings, ledger PC-10 в подразделе F), §6.26 (producer→consumer сравнение полей и ловушка `coarse_relief_z`), §6.29-M (DeclaredWaterPaint producer/consumer контракт), §6.27 (suites/commands PC-9…12).
2. [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) — §compose, §Coarse planning ↔ light compose: L0 consumer контракт.
3. [`docs/tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) — §Surface planning/cache (норматив PC-0), §PC-D1.
4. DONE-блоки PC-6W/PC-7/PC-8/PC-9A/PC-9 в плане — что уже frozen и куда подключаться.
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc) — materializer не повторяет placement/selection
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc) — frozen POJO — единственный SoT
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc) — инвентаризация → строгий тип
   - [`.cursor/rules/folder-composition.mdc`](../rules/folder-composition.mdc) — **`lightGrid/` = 11 файлов > 10 (лимит превышен, добавлять запрещено), `contributors/` = 10 (на лимите)** — новые modules только в existing owner files или по карте §5.4; WARN в чат до добавлений
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не backend-старт, не коммит

План важнее догадок. Противоречие план↔ТЗ↔код — остановиться и спросить мастера.

## Scope этой команды

**Только PC-10 — L0 consumer cutover.** PC-11 (L2, `build_tile_surface_state`) и PC-12 (приёмка) — вне scope. GEO-1 algorithms/autoresolve/policy не активируются. Publication guard (PC-9) не дублируется.

Ledger (§6.31-F): `worldMapBakeOrchestrator.py`, `lightGrid/bakeContext.py`, `contributors/{relief,climate,mountain,ravine}.py`, `contributors/hydro/{hydro,declaredBasins,declaredRivers,coarseOpenWater}.py` + `MountainMaskMaterializer` load/collect + `collect_mountain_entries_for_coarse` + `autoresolve_mountain_specs`.

## Что уже есть — не переписывать

- `ReliefPlan.light: LightReliefPlan` — `base_surface_z` (pre-mountain light base), `mountain_cells` (absolute z + facing), `ravine_cells` (absolute z, scope-independent), `ravine_terrain: TerrainKey`, `terrain_merge`.
- `ReliefPlan.mountain_layout: MountainLayout` — stamped entries + `MountainTemplateInput` + `world_pick` + `terrain_key`; покрывает всех трёх named mountain consumers.
- `HydrologyPlan.declared_paint: DeclaredWaterPaint` — `lakes/coastlines/segments/intents`; anchors уже разрешены в `FineXY` path.
- `HydrologyPlan.coarse_surface_z/coarse_hydro` — final post-river surface для coarse open water.
- `ClimatePlanSampler.sample(plan, gx, gy)` — pure sampler на frozen plan (PC-5/PC-8C).
- `SurfacePlanBundle` — typed envelopes с проверкой world/scope/phase/refs.
- `application/worldData/planning/legacy/surfaceTerrainContext.py` — transitional eight-field view; остаётся для unconverted consumers (settlement/road/landcover).

## Жёсткие запреты (собранные подводные камни)

- **Смешанное состояние selection запрещено**: все три named mountain consumers переходят на `MountainLayout` атомарно; нельзя часть — на layout, часть — на повторный selection.
- **Нет второго selection/stamp**: `MountainMaskMaterializer` в switched path не вызывает `load_declared/load_anchor_specs/autoresolve_specs/stamp` — получает layout; live World пути в нём нет.
- **Нет tile-scoped detection**: ravine не детектится по покрашенным клеткам тайла — только `light.ravine_cells` (frozen scope-independent set); partial re-bake обязан совпадать с full bake на пересечении tiles.
- **Absolute z, не дельты**: `mountain_cells`/`ravine_cells` — итоговые z+facing; не прогонять `resolve_mountain_surface_z`/`resolve_ravine_surface_z` повторно (double-rise/double-drop), `_base_z`-накопление не нужно.
- **`coarse_relief_z` — ловушка имени**: это pre-1.4 base, не post-relief. Light base — `light.base_surface_z`; `ReliefPlan.surface_z` (coarse post-relief) в light base не подставлять.
- **Z не зависит от успешности paint** — целевой §6.31-C устраняет legacy `system_terrain == policy_terrain` gate для elevation; baseline delta фиксировать явно.
- **Нет live reads для detection/geometry**: `pole.sample(world)`, `terrain_masks(ctx.world)`, `load_declared_hydrology(world, locations)`, `loc_map` по `route_location_uids`, re-check `autoresolve/enabled` — заменяются frozen refs. Paint остаётся tile-scoped.
- **Не пере-resolving intent anchors**: `IntentRiverPaint.path` — готовый FineXY; сохранить асимметрию widths (segments: dilation; intents: `width_wire` без dilation).
- **Open water — только final envelope**: `HydrologyPlan` (post-river), не routes-stage; `fine_z_overrides`/`sparse_fine_hydro` — PC-11, не трогать.
- **Не мутировать payloads / не кэшировать производные** в contributor instance между bake calls.
- **Не расширять eight-field view** новыми полями и не удалять `surface_planning` — unconverted consumers его используют.
- Порядок paint сохраняется: river corridors → lake/coastline → coarse open water; `_PRESERVE_DECLARED_RIVER` неизменен.
- Нет `Any`, raw dict, cast, string slot literals, synthetic defaults.
- Не DAG, не backend-старт, не коммит, не SQL. City/location caches не трогать.

## Приёмка (Done по §7)

- Contributors поимённо переведены на frozen inputs: RavineContributor, HydroContributor, MountainContributor + mountain materializer path.
- Light/full L0 baseline; HIT/MISS equality; **partial re-bake равен full bake на пересечении tiles** (ravine/hydro declared/mountains).
- Materialize только по bake request; edit без eager materialization.
- Consumers suite §6.27 (`backend/tests/planning/consumers`) зелёный; пять обязательных regression suites OK; pyright valid0/negative exact.
- Folder counts: в `lightGrid/` и `contributors/` новых файлов нет; WARN выданы.
- DONE-запись в плане по формату предыдущих PC-шагов.

## Старт

Прочитай §7 PC-10 + §6.30 + §6.31-B/C/D/E/F, сверь `bakeContext.py`/`worldMapBakeOrchestrator.py` с текущим кодом (могло уехать после PC-9), инвентаризируй поля `LightReliefPlan`/`MountainLayout`/`DeclaredWaterPaint` против потребностей каждого contributor (недостающее поле → расширение контракта через правку плана, не второй selection path), затем реализуй cutover по ledger. Отчёт: сделано/файлы/проверки/baseline delta → ждать «ок».
