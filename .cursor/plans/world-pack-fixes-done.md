# World Pack — fix backlog (code review) ✅ DONE

> **Канонический статус в ТЗ:** [`docs/tz_world_pack_storage.md`](../docs/tz_world_pack_storage.md) — § **WP-FIX**, § **WP-FIX-DEBT**, § **WP-MERGE** v2.

Source TZ: [`docs/tz_world_pack_storage.md`](../docs/tz_world_pack_storage.md)  
Related: [WP-MERGE](../docs/tz_world_pack_storage.md#merge-backlog-wp-merge), [migration checklist](world-data-storage-migration-done.md)

Результат ревью impl L1–L7 (smells, неявные контракты, хардкоды).  
**MERGE-*** в TZ — продуктовый merge backlog; **FIX-*** здесь — детальный чеклист агента (зеркало ТЗ).

## Статус impl (2026-07-10) — зафиксировано в ТЗ § WP-FIX

| ID | Статус |
|----|--------|
| FIX-01…02 | ✅ |
| FIX-03, FIX-11 | ✅ |
| FIX-04…09, FIX-12…30 | ✅ |
| FIX-10 | ✅ |
| FIX-31 | ⬜ P4 backlog |
| FIX-32/33 | ✅ |
| MERGE-5/6/8 | ⚠️ частично |
| DEBT-7 | ✅ |
| DEBT-6 | ✅ |

**Оставшееся:** DEBT-1 write PK, MERGE-8 LRU, smoke WP-A*, DAG intent wire.

---

## P0 — критичные

| ID | Фикс | Где | Что сделать | TZ |
|----|------|-----|-------------|-----|
| **FIX-01** | L2 terrain roundtrip | `mapCellToL2Wire.py`, `mapCellQueryFacade.py` | Не кодировать `system_terrain` в u8-hash. Хранить registry key или индекс в wire; при read — исходный ключ, не `terrain_{id}` | MERGE-4 |
| **FIX-02** | L2 material roundtrip | то же | Аналогично для `system_material` — убрать lossy `_stable_u8` или sidecar lookup в chunk | MERGE-4 |
| **FIX-03** | Location L2 координаты | `mapCellQueryFacade.py`, bake-path | Read: `lx/ly` относительно origin location volume. Write: вызывать `write_location_l2` при settlement refine | MERGE-3 |
| **FIX-04** | Background queue cx/cy | `l2RefineOrchestrator.schedule_tile_background` | Tile-local: `(rect.x_min - fine_bbox.x_min) // chunk_size`, как в `_refine_rects` | — |
| **FIX-05** | Background queue consumer | `chunkRefineQueue`, worker | Drain `pop_next` → `refine_rect` → persist; либо убрать enqueue до готовности воркера | MERGE-5 |
| **FIX-06** | `chunk_refine_jobs` wiring | repo + worker | Persist queue state в SQLite (WP-12 recovery), не только in-memory heap | — |

---

## P1 — merge и read-path

| ID | Фикс | Где | Что сделать | TZ |
|----|------|-----|-------------|-----|
| **FIX-07** | PLAYER_SCENE layer | `mapCellQueryFacade.py` | Слой `MapLayerKind.PLAYER_SCENE` в merge; scene chunks ≠ bg wilderness | MERGE-1 |
| **FIX-08** | Climate в merge | facade + `read_climate_coarse` | `temperature_base` / `rainfall` из climate blob + patch override | MERGE-2 |
| **FIX-09** | L0 без z-оси | `_l0_contribution` | Явный gate: L0 только surface band; иначе не отдавать L0 terrain на subsurface z | MERGE-6 |
| **FIX-10** | Фильтр по `layer_kind` | `PatchStoreService`, repo | Читать patches с учётом `layer_kind` | MERGE-7 |
| **FIX-11** | Location footprint hole | `l2RefineOrchestrator` | Cells внутри `inside_location_volume` исключены из wilderness, location L2 не пишется — закрыть bake | MERGE-3 |

---

## P2 — хардкоды и контракты

| ID | Фикс | Где | Что сделать | TZ |
|----|------|-----|-------------|-----|
| **FIX-12** | `fine_cells_per_map_cell or 3000` | facade, helpers | `world.fine_cells_per_map_cell` + POJO default, без литерала `3000` | — |
| **FIX-13** | `"plains"` fallback L0 | `mapCellQueryFacade` | Fallback из `WorldTerrainRegistry` / canonical POJO | — |
| **FIX-14** | `dominant_terrain_id` формула | `l0BakeOrchestrator` | Terrain из `surface_ctx`, не `(surface_z + 500) // 50` | — |
| **FIX-15** | Hydrology string match | `_l0_hydro_role` | Typed enum mapping вместо `"river" in name` | — |
| **FIX-16** | `getattr(world, "world_map_cells_per_tile")` | `l0BakeOrchestrator` | Прямое поле `world.world_map_cells_per_tile` | — |
| **FIX-17** | Manifest `world_map_cells_per_tile` | L0 bake, writer | Записывать в manifest при bake; facade читает оттуда | WP-10 |
| **FIX-18** | `worlds.terrain_pack_*` | bake finalize | После bake: `terrain_pack_path`, hash в SQLite | — |
| **FIX-19** | Pack root config | `WorldPackPaths.from_db_parent` | Опциональный `WORLD_PACK_ROOT` в config | — |
| **FIX-20** | `max_tiles=16` | routes, orchestrator | Default из POJO / world settings / query param (одно место) | — |
| **FIX-21** | `l0_cells` counter | `WorldPackWriter` | Reset или пересчёт при rebake, не только `+=` | — |
| **FIX-22** | Pack-level `content_hash` | manifest finalize | Root hash manifest при `save_manifest` после bake | — |
| **FIX-23** | Silent `FileNotFoundError` | facade | Лог / debug counter при missing L2 chunk | — |
| **FIX-24** | L0 sample fallback | `sample_l0`, `_l0_contribution` | Явный miss → None, не маскировать индексом | — |

---

## P3 — API и lifecycle

| ID | Фикс | Где | Что сделать | TZ |
|----|------|-----|-------------|-----|
| **FIX-25** | Dual endpoints | `map.py` | Canonical: `pack/bake` vs `materialize-stack?target=pack`; deprecate один | — |
| **FIX-26** | Anchor/tile selection | `packMaterializationOrchestrator` | Scene refine по явному `anchor_x/y`, не `locations[0]` + `tiles[0]` | — |
| **FIX-27** | Orchestrator lifecycle | `worldSurfaceMaterializationOrchestrator` | Shared `PackMaterializationOrchestrator` в container (живая queue) | — |
| **FIX-28** | `query_facade_factory` typing | `MapCellService`, container | Typed protocol вместо untyped callable | — |
| **FIX-29** | Docstring drift | `MapCellService`, deprecated paths | `map_cell_patches`, pack read path | — |
| **FIX-30** | `LoadingProgress` phases | `loadingProgress.py` | Enum/POJO для phase; корректный `l0_tiles_total` | WP-15 |

---

## P4 — wire / perf (backlog)

| ID | Фикс | Где | Что сделать | TZ |
|----|------|-----|-------------|-----|
| **FIX-31** | Binary wire вместо JSON | `tileCodec`, `packBlobWire` | Struct/binary layout для L0/L2 blobs | — |
| **FIX-32** | Codec version в manifest | manifest + `TileCodec` | Версия codec/payload для migration | — |
| **FIX-33** | zstd level config | `TileCodec` | Level из config/POJO, не hardcoded `3` | — |

---

## Рекомендуемый порядок

1. **FIX-01, FIX-02** — pack read даёт неверный terrain без этого  
2. **FIX-04** — быстрый bugfix queue coords  
3. **FIX-03, FIX-11** — location terrain end-to-end  
4. **FIX-05, FIX-06** — background refine (или временно отключить enqueue)  
5. **FIX-07, FIX-08** — merge P0 по TZ (MERGE-1, MERGE-2)  
6. **FIX-12–FIX-18** — хардкоды и sync с БД  
7. P3, P4 — по smoke / приёмке мастера  

**Связка с WP-MERGE:** MERGE-1 → FIX-07; MERGE-2 → FIX-08; MERGE-3 → FIX-03, FIX-11; MERGE-4 → FIX-01, FIX-02; MERGE-5 → FIX-05, FIX-06; MERGE-6 → FIX-09; MERGE-7 → FIX-10, FIX-15.

---

## Приёмка (smoke после P0)

- [ ] L2 roundtrip: bake chunk → `get_cell` → `system_terrain` совпадает с generator output  
- [ ] Location volume: cell внутри settlement не «дырявый» после refine  
- [ ] `schedule_tile_background` priority: tile `(gx≠0)` — центр chunk совпадает с метрами  
- [ ] WP-A9 spawn scene load ≤ 30s (master)  
- [ ] WP-A12 climate fields на scene без L2  
