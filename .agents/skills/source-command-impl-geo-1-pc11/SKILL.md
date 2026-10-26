---
name: "source-command-impl-geo-1-pc11"
description: "Имплементирует PC-11 плана geo-1-designed-water.md: L2 consumer cutover — build_tile_surface_state и detailed/entry callers на bundle refs (fine_z_overrides/sparse_fine_hydro/landcover facts из typed envelopes); parent light SoT и fine-detail recipe неизменны. Входы закрыты: PC-0…PC-10. Новый чат: /impl-geo-1-pc11."
---

# source-command-impl-geo-1-pc11

Use this skill when the user asks to run the migrated source command `impl-geo-1-pc11`.

## Command Template

# Имплементация: GEO-1 PC-11 — L2 consumer cutover на bundle refs

Это **явная просьба писать код** (шаг PC-11 плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/geo-1-designed-water.md`](../plans/geo-1-designed-water.md) — **единственный SoT**. Обязательные разделы: §7 PC-11 (тело шага) и DONE-блоки PC-9/PC-10 (что уже switched, карта методов PC-9 строк ~7062-7070 — тот же caller chain), §6.31-E/F (bundle slots, ledger PC-11), §6.20 §4–5 (L0/L2 — согласованные представления одной планировки, revision compatibility), §6.26 (producer→consumer поля, ловушка `coarse_relief_z`), §6.27 (suites/commands), §6.10 (фиксированный порядок pre-river базы — контекст, не задача этого шага).
2. [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) — §compose, parent light SoT/patch precedence.
3. [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) — L0/L2, read path, WP-PERF-22 parent light.
4. [`docs/tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) — §Surface planning/cache, multi-pass skeleton.
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc) — materializer не повторяет placement/selection/planning
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc) — frozen POJO — единственный SoT
   - [`.cursor/rules/folder-composition.mdc`](../rules/folder-composition.mdc) — **materialize/ = 11 файлов, refine/fine = 10, refine/detailed = 14, pack/bake = 16 — все на лимите или выше; новых modules НЕТ, helpers в existing owner files; WARN в чат**
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc) — TerrainBatchOrchestrator ~200 строк, держать <300
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не backend-старт, не коммит

План важнее догадок. Противоречие план↔ТЗ↔код — остановиться и спросить мастера.

## Scope этой команды

**Только PC-11 — L2 consumer cutover.** PC-12 (приёмка) — вне scope. GEO-1 algorithms не активируются; HY-RIV-1 (§6.10 fine source search, `fineSurfaceBase` split) — отдельный трек, **не** делать попутно.

Ledger: `terrainBatchOrchestrator.py::build_tile_surface_state` + named detailed/entry callers — цепочка `worldSurfaceMaterializationOrchestrator::materialize_pack_detailed` → `packDetailedBakeOrchestrator` → `fineTerrainRefineOrchestrator.refine_rect/refine_queued_chunk` → `FineChunkRunner.refine_rects` → `fineTilePrep.prepare_fine_tile`; `entryRefineOrchestrator` scene/path; `chunkRefineWorker.drain_*`; `_run_refine_phase`; debug route `map.py`. Перед кодом сверить с актуальным caller ledger PC-0/PC-9 — `save_z_slice`/`plan_bootstrap_tiles` не догадывать, проверить по плану.

## Что уже есть — не переписывать

- `SurfacePlanBundle` — typed envelopes с coherence-проверкой; `prepare_captured_bundle(view, planning, wait, resolve_ctx)` уже возвращает bundle (PC-9).
- `HydrologyPlan.fine_z_overrides` — **полный sampled output** post-river (не только beds); `sparse_fine_hydro` — для hard corridor merge; оба tuple rows → request-local dict.
- `HydrologyPlan.coarse_hydro/coarse_surface_z`, `terrain_base.surface_z`, `climate_local.anchors` — факты для landcover `FactConsumerContext` вместо legacy `surface.*`.
- Parent light — persisted L0 SoT (`require_parent_light`); upsample/terrain/facing carry, `ParentLightRefinePolicy`, hills, gap analysis, region paint recipe — неизменны («зёрна fine detail/parent light storage остаются прежними», §6.31-F).
- `to_legacy_context`/`planning/legacy/surfaceTerrainContext.py` — transitional view для unconverted consumers; не удалять.

## Жёсткие запреты (собранные подводные камни)

- **`coarse_relief_z` — ловушка имени (повтор из PC-10)**: в fact consumers это `terrain_base.surface_z` (pre-1.4 base), НЕ `ReliefPlan.surface_z` (post-relief pre-river). Подмена = неверные relief facts для region eligibility.
- **Не менять порядок операций** в `build_tile_surface_state`: parent-light upsample+clamp → `fine_z_overrides` (clamp `base ± z_band`) → terrain/facing carry → region paint → hills → hydro corridor merge → gap analysis. Ни reorder, ни «оптимизация».
- **Нет второго planning/re-capture**: drains/queued chunks/scene/path переиспользуют уже захваченный bundle entry-шва; `prepare_captured_bundle`/`prepare` внутри refine-цепочки не вызывать.
- **Parent light — persisted SoT**: L2 НЕ восстанавливает light base из `bundle.relief.light` — upsample идёт из persisted parent tile. Ревизия parent light должна быть согласована с bundle того же capture; несоответствие = stale, через существующий publication/revision guard (PC-9), не новый механизм.
- **Атомарная замена параметра**: `ctx: SurfaceTerrainContext` → typed bundle refs (или один typed L2 input) во **всей** цепочке callers разом; смешанный режим «где-то ctx, где-то bundle» = два источника истины. Поля, нужные landcover facts, передаются typed, а не через legacy view.
- **Нет live reads для плановых данных**: `ctx.fine_z_overrides`/`sparse_fine_hydro`/`local_field`/`coarse_*` — только из typed payloads. Domain recipe reads (`terrain_with_hills`, `world_seed`, `world_z_min/max`, `run_gap_analysis`) — fine-detail recipe, сохраняются; если спорно — сверить с планом, не решать молча (drift между capture и materialize).
- **Не трогать wilderness/city caches**: landcover region paint + `region_state_snapshot` — свой домен со своим state; мигрировать его planning — не этот шаг.
- **Mill/grades/halo**: `overlay_grid_neighbor_halos` работает на `TileSurfaceState`, не на ctx — соседние states от того же bundle/revision; `relief_templates_by_uid` (милльные ReliefTemplate bodies) ≠ `MountainTemplateInput` — не смешивать.
- Нет `Any`, raw dict, cast, synthetic defaults; payloads не мутировать (tuple → request-local dict).
- Не DAG, не backend-старт, не коммит, не SQL. Publication guard (PC-9) не дублируется.

## Приёмка (Done по §7)

- L2 читает planning result/revision: `fine_z_overrides`/`sparse_fine_hydro`/landcover facts — из typed envelopes; detailed/entry callers несут bundle refs.
- Detailed/entry baseline равен (кроме явно зафиксированных baseline delta); порядок tiles не меняет результат.
- HIT/MISS equality; stale revision отклоняется существующим guard; climate/terrain/hydro consistency между L0/L2 одного capture.
- Consumers suite §6.27 (`test_l0_l2.py`, `test_revisions.py`, `test_no_second_truth.py`) зелёный; пять обязательных regression suites + detailed_bake/parent_light_refine/fine_terrain_refine_parallel OK; pyright valid0/negative exact.
- City/location caches нетронуты; folder counts без новых файлов, WARN выдан.
- DONE-запись в плане по формату предыдущих PC-шагов.

## Старт

Прочитай §7 PC-11 + §6.31-E/F + §6.20 §4–5 + карту методов PC-9 (~строки 7062-7070), сверь цепочку `surface_ctx` по коду (`grep SurfaceTerrainContext` в materialize/pack/refine), составь список точек чтения legacy-полей (`fine_z_overrides`, `sparse_fine_hydro`, `local_field`, `coarse_*`) и их typed-замены в bundle, затем реализуй cutover по ledger. Отчёт: сделано/файлы/проверки/baseline delta → ждать «ок».
