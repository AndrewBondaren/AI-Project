# Relief development plan ✅ DONE

**SoT:** [`docs/tz_terrain_relief.md`](../../docs/tz_terrain_relief.md) § [Порядок имплементации](../../docs/tz_terrain_relief.md#порядок-имплементации-anti-slice).  
**Debt:** [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md) § R36i-T.  
**Updated:** 2026-08-17.

Do not duplicate wave tables here — follow TZ.

## Current focus

**Pipeline v2:** [план реализации](./relief-pipeline-v2-done.md) (R41 discover в воркере). Live sample/stitch до пула — **deprecated**, пока слой 3 не в `compute_rect`.

**R36u/v/w ✅** · **Post-R36w GradeFormation apply ✅** ([план](./detailed-grade-volume-canal-done.md)).  
Wave A–D / L0 ribbon — historical (T-8). Шов `full_bake` · halo `grid_neighbor` · T-10 ✅.

**Later — Wave E** (R36r / R36o / Q4 / R36f/k / UI R30). Не блокирует v2. BAR-1 вне. T-3c — слой 6 плана v2.

## Waves done

R36 §7–9/8c · canal wire+resolve · bake split · Wave B–D (L0, then deleted T-8) · **R36u** · **R36v** · **R36w** catalog · FineChunkRunner layers · seam/halo/T-10 · **Post-R36w** volume z + canal on detailed.

## Gates

DAG nodes off-limits · schema only `0001` · generators pure · no shared heightmap mutate from pool workers · R36t anchors.
