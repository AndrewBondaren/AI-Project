# R36u: relief grade writer → detailed_bake geometry ✅ DONE

Agent pointer for migration. User plan: `r36u_relief_migrate_4c24dbb8.plan.md`.

## Scope lock

**Только outdoor relief grade.** Не трогать parent-light L2: terrain mask carry (`system_terrain` only), hydro hard corridor, facing upsample, `surface_z` upsample. Grade uid ≠ mask carry.

## Target

Single-writer relief geometry: [`FineChunkRunner`](backend/app/application/worldData/pack/refine/fineChunkRunner.py) → `detailedGradeGenerate` → `TileSurfaceState.surface_grade_uid` → columnFill → FineTerrain.

## Legacy ↔ target

See [`docs/tz_generator_technical_debt.md`](../docs/tz_generator_technical_debt.md) § Legacy L0 grade — inventory (R36u migrate off).

| Legacy | Target |
|---|---|
| L0 ribbon contributors | `pack/refine/detailedGrade*.py` |
| `upsample_grade_uid_from_parent_light` | removed; detailed generate |
| L0 `world-grade` ASCII | omit |
