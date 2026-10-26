# R36u post-impl debt (R36u-T) ✅ DONE

Registry: [`docs/tz_generator_technical_debt.md`](../docs/tz_generator_technical_debt.md) § **R36u post-impl smells**.

**Scope lock:** только outdoor relief grade. Не трогать: terrain mask carry (`system_terrain`), hydro hard corridor, facing upsample, `surface_z` upsample. Grade uid ≠ mask carry.

## Status (2026-08-13)

| ID | Status |
|---|---|
| T-1…T-9 | resolved (T-9 residual: `meter_grade_cell_blocked`) |
| T-11 | resolved (R36v pool + stitch) |
| T-10 | deferred in [`tz_terrain_relief.md`](../docs/tz_terrain_relief.md) R36u |

## Fix order

1. ~~**R36u-T-1** (P0) — импорты в `detailedGradeGenerate.py`~~
2. ~~**R36u-T-2** — `plan_seed_volume` + cardinal deltas → `generators/terrain/relief/`~~
3. ~~**R36u-T-3** — persist `grade_instances` на detailed path~~
4. ~~**R36u-T-4** — templates на FineTerrain / entry refine~~
5. ~~**R36u-T-5…T-9**~~; ~~**T-8**~~ ✅; **T-10 later** (`road_shoulder` meter)

Не трогать: `upsample_terrain_from_parent_light` / facing / hydro merge.
