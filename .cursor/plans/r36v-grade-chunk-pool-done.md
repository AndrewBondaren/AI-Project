# R36u-T-11 / R36v — grade in `FineChunkRunner` pool ✅ DONE

SoT: [`docs/tz_terrain_relief.md`](../docs/tz_terrain_relief.md) **R36v / C26**. Debt: **R36u-T-11**.

## Target

Replace tile-wide serial `generate_detailed_grade` (before pool) with:

```text
surface (serial)
  → pool: sample fine-edge seeds per ColumnRect (seed ∈ rect; halo = read)
  → stitch O(seeds): one segment → one uid
  → pool: materialize assigned seeds + column fill + persist_chunk
  → merge instances by uid → persist_relief_grades (upsert, merge cell_refs)
```

No new orchestrator. No L0 candidates. Same helper for later `modify_terrain` (`rects` / bounds).

## Layers

| Piece | Change |
|---|---|
| `detailedGradeSample` | Optional `rect` + `halo`; iterate bounds only; filter `seed ∈ rect` |
| `detailedGradeGenerate` | Split: sample rect → merge/stitch/plan → materialize rect; keep `generate_detailed_grade` facade |
| `detailedGradeMaterialize` | One instance per segment (R36v); optional inherited uid |
| `gradeInstanceFactory` | Optional explicit `grade_uid` |
| `FineChunkRunner` | Two pool passes; load existing pack uids for late chunk |
| `persistReliefGrades` | `replace_world=False` → union `cell_refs` on upsert |

## Late chunk

Read already-written wilderness columns → `system_grade_uid`. Exactly one neighbor uid → inherit; 0 or 2+ → mint. Upsert, no second object.

## Tests

- Sample respects rect (no seed outside; halo read)
- Two rects stitch → one uid
- Existing facade `generate_detailed_grade` still stamps
- Late inherit: neighbor uid reused

## Out of scope

T-10 `road_shoulder`, DAG `modify_terrain` node, L0 compose, mask/hydro/facing/z carry.

## Status

Implemented (R36v two-pass). **Stitch target superseded by R36w** — SoT [`docs/tz_terrain_relief.md`](../docs/tz_terrain_relief.md) § Grade в detailed_bake. Impl ⬜ until master asks.
