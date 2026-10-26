# Plan: Relief extract → Mountain PassBuilder ✅ DONE

SoT: [`docs/tz_terrain_relief.md`](../../docs/tz_terrain_relief.md), [`docs/tz_mountain_architecture.md`](../../docs/tz_mountain_architecture.md), paint consumer [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) § Mountain.

**Итерации (мастер):** эта итерация = только план; код — отдельной итерацией по явной команде.

## Locked decisions

| # | Decision |
|---|---|
| Gate | **0. Relief extract** first, then PassBuilder |
| Saddle wire | only inside `MountainRangeSpec.saddles[]` (+ `saddle_rise_fraction`); no separate `declared_saddles` |
| Auto | **breaking** immediately after relief (no feature-flag); auto → `MountainSpec \| MountainRangeSpec` |
| Secondary U4 | **stub v1**: fixed smaller R/width + `TODO` → TZ U4 full `context→params` |
| U7 inset | default `0.30` all kinds + `TODO` in code → TZ |
| Facing | **architecturally correct persist in step 0** (not derive-only) |
| Schema | only `0001_initial.sql` + recreate DB; model+SQL same PR |
| Acceptance | pack ASCII + `relief_grade_*` / `column_span` logs (no topology debug HTTP) |

## Target architecture

### Domain split

```text
terrain/relief/          # OWN: SideKind, SideSpec, sideFill profiles, facing helpers
terrain/mountains/       # CONSUME relief; own Form/Kind/Range/PassBuilder/topology
terrain skeleton         # OWN: N_eff, gap, column fill (tz_terrain_generation)
```

### Facing persist (architecturally correct)

| Layer | Field | Notes |
|---|---|---|
| SQL `map_cells` | `system_facing` / `display_facing` | **already in 0001** — stamp on L0/apply when writing cells |
| Pack `FineTerrainColumnWire` | `system_facing: str \| null = null` | column-level (xy grade direction); not per-run |
| Pack `FineTerrainZRun` | no facing | run = z-band + terrain/material only |
| Renderer | optional later | acceptance does **not** require facing glyphs in ASCII v1 |

**Invariant:** facing is horizontal uphill direction for the column; stairs keep per-cell `map_cells.system_facing`; outdoor L2 pack uses column wire.

### Data flow (PassBuilder)

```text
ridge field → RidgeCandidate[] (placement, as-is)
        │
        ▼
MountainPassBuilder(candidates, policy, seed, reserved)
  PeakAssembler → SummitAnchor → SystemCluster
  per system:
    <2 peaks → MountainSpec
    ≥2 → Graph(Delaunay→MST) → SaddlePlacer → SpineSampler
         → RidgeSegmentBuilder(primary) → MountainRangeSpec(+peaks, saddles[])
  secondary: RidgeSegmentBuilder(spur|foothill) stub params → RangeSpecs
  RangeGapFilter vs reserved(declare+anchors)+auto → drop conflicting auto
        │
        ▼
merge (declared > anchors > auto) → materializer → formPipeline (U6) → apply
```

### Secondary stub (U4 v1)

```text
RidgeSegmentBuilder(context) → MountainRangeSpec
context = primary_mst_edge | spur_from_peak | foothill
# v1 stub: fixed scale vs primary (see open Q below)
# TODO(full context→params): docs/tz_mountain_architecture.md U4
```

---

## Implementation order

| Step | Layer | Work | Acceptance |
|---|---|---|---|
| **0** | **Relief extract** | `ReliefSideKind` / `ReliefSideSpec` in `dataModel/terrain/relief/`; move profile helpers; `FineTerrainColumnWire.system_facing`; mountains shim (`MountainSideKind` alias or thin wrapper); stamp facing on L0 apply when writing `map_cells`; R8 logs (`relief_grade_*`) | unit + DEBUG logs; pack dump still aligned ASCII |
| **1** | **PassBuilder POJO** | `MountainRangeStyle`; Range: `style`, `peak_spacing_m`, `peak_spacings_m`, `saddle_rise_fraction`, `saddles[]`; `MountainSaddleSpec`; policy/profile knobs; KindProfile inset/saddle; sync wire; **0001 only** + recreate DB if SQL columns needed (policy is JSON TEXT — likely wire-only) | `validate_schema` |
| **2** | **Runtime graph types** | `ridgeGraph/`: RidgeVertex, RidgeEdge, RidgeGraph, MountainSystem, RidgeSegmentContext | unit import/construct |
| **3** | **Topology assemblers** | PeakAssembler, SummitAnchor, SystemCluster (from `_spec_from_policy` / placement) | unit |
| **4** | **Topology builders + facade** | RidgeGraphBuilder, SpineSampler, SaddlePlacer, RidgeSegmentBuilder (**secondary stub** + `TODO` → TZ U4 full `context→params`), RangeGapFilter, `MountainPassBuilder.build(...)` | unit topology |
| **5** | **collect** | auto **breaking** via PassBuilder only; declare/anchors as-is | unit collect |
| **6** | **formPipeline compose** | U6 min: corridor → saddle modulate → peaks max-wins | unit compose |
| **7** | **Smoke** | fixture ≥2 peaks → Range; gap/saddle in logs; pack ASCII + `relief_grade_*` / `column_span` | `world-test-003` style smoke |

**Out of this backbone:** U8 noise, U9 cliff/ravine Spec, U10 summit materials.

---

## Locked decisions (from master)

| # | Decision |
|---|---|
| Gate | Relief extract **before** PassBuilder |
| Saddle wire | only `MountainRangeSpec.saddles[]` + `saddle_rise_fraction`; no `declared_saddles` |
| Auto | **breaking** right after relief; no feature-flag |
| Secondary U4 | stub v1 + `TODO` → full `context→params` (TZ U4) |
| U7 | inset `0.30` all kinds + `TODO` in code → TZ |
| Facing | architecturally correct **persist** in step 0 |
| Schema | `0001_initial` only + DB recreate; model+SQL same PR |
| Acceptance | pack ASCII + `relief_grade_*` / `column_span` logs |

---

## Questions (block coding start)

1. **Facing wire placement (recommend column):** `FineTerrainColumnWire.system_facing` (xy grade) vs per-run on `FineTerrainZRun`?  
   (`map_cells.system_facing` already exists — stamp on L0 apply.)
2. **Secondary stub scale:** fixed fraction of primary R/width — **0.5** OK?
3. **Smoke scope after PassBuilder:** same `world-test-003` tile `(-2,-2)` only, or also a fixture that forces ≥2 peaks → Range?
4. **Write plan file only this turn (done below); code next turn only after explicit «делай / имплементируй»?**  
   (your earlier rule: separate iterations — confirm still holds)

---

## Recommended defaults if unanswered

| Q | Default |
|---|---|
| Facing wire | **column-level** `FineTerrainColumnWire.system_facing` |
| Secondary stub | **0.5 ×** primary `radius_m` / `width_m` |
| Smoke | `world-test-003` `(-2,-2)` + one fixture path that yields Range (≥2 peaks) |
| Next iteration | plan file only now; code on explicit command |
