# World Pack migration — living checklist ✅ DONE

Source TZ: [`docs/tz_world_pack_storage.md`](../docs/tz_world_pack_storage.md)  
Fix backlog (post-review): [`world-pack-fixes-done.md`](world-pack-fixes-done.md)

## Layers

| Layer | Status | Notes |
|-------|--------|-------|
| L1 dataModel/worldPack | done | wire POJOs, merge_layers, WP-10 |
| L2 Pack I/O | done | TileCodec, Writer/Reader, zstandard |
| L3 Facade | done | MapCellQueryFacade, loading-progress |
| L4 Orchestrators | done | L0 bake, L2 refine, pack materialize routes |
| L5 Schema cutover | done | map_cell_patches, drop map_cells |
| L6 Import/bake | done | levels, pack/import, bake CLI |
| L7 Cleanup | done | deprecation warnings, CI gate script |

## Post-impl (2026-07-10)

- [x] L1–L7 code complete
- [x] WP-FIX FIX-01…30, FIX-32/33 — см. [TZ § WP-FIX](../docs/tz_world_pack_storage.md)
- [x] WP-FIX-DEBT DEBT-2…5, 8, 9; DEBT-1 read path — см. [TZ § WP-FIX-DEBT](../docs/tz_world_pack_storage.md)
- [x] MERGE-9 debug routes → facade (L0 coarse tile render; legacy write routes отдельно)
- [x] DEBT-6 settlement footprint → `locationTerritoryVolumes` + assembler `footprint_side_fine`
- [x] DEBT-7 path heading (MERGE-5)
- [ ] MERGE-8 LRU decode
- [ ] DEBT-1 write PK policy (документировать merge-on-upsert)

## Smoke (master)

- [ ] `POST /worlds/{uid}/map/pack/bake?mode=light`
- [ ] `GET /worlds/{uid}/map/loading-progress`
- [ ] Recreate local DB after schema change
- [ ] WP-A9 spawn ≤ 30s (manual)

## Out of scope

- DAG node wiring (gate with master)
- starter_characters[] / npcs[] bundle
- Frontend SSE progress (WP-15)
