# AI RPG Platform — global characterization

**Date:** 2026-09-03  
**Purpose:** Self-contained brief for an external reviewer / other LLM.  
**Not a product pitch.** Evaluate architecture, thesis consistency, and engineering density — not “can a player finish a session.”

**Onboarding (what the product is, layers, invariants):** [`.cursor/plans/llm-project-description-2026-09-03.md`](./llm-project-description-2026-09-03.md). This file is the *scorecard*; that one is the *handoff*.

**How this document was compiled:** code + domain TZ (`docs/tz_*.md`) + git history + working tree as of 2026-09-03. Prior brief: [`.cursor/plans/project-characterization-2026-08-15.md`](./project-characterization-2026-08-15.md) (relief scores 2026-08-17). Official living snapshot `docs/tz_project_snapshot.md` is still v1.3 (2026-08-17); **numbers below supersede it** where they conflict.

**Author time split (stated by the project owner, still matches git mass):** ~1 month closing the DAG runtime, then generators / pack bake, then (this window) relief v2 + outdoor settlement etalon. Calendar age of the git repo: **2026-05-09 → 2026-09-02** (~3.8 months, 316 commits, essentially one author). HEAD at compile: `0342edb` (`city tz`, 2026-09-02). Working tree on 2026-09-03 also has uncommitted city/outdoor/connections TZ (C22 packing contracts) — spec ahead of packing code.

---

## 0. How to evaluate this (read first)

Score these axes. Do **not** score “playable vertical slice” as the primary grade — `scene_narration` is a **conscious blocker**, not an accidental gap.

| Axis | Question |
|---|---|
| Thesis | Is “engine+geometry are SoT, LLM renders facts” actually encoded in the runtime, or only in docs? |
| Engine as framework | Is the DAG a real game-engine dispatcher (compile / phase / repair / replan) or a thin agent loop? |
| World substrate | Is bake a real job (immutable pack + LOD) or debug scripts pretending to be a world? |
| Callers | Are generators a library with multiple callers, or glued to HTTP? |
| Data contracts | Is `dataModel/` actually SoT, or are there parallel literals? |
| Scope risk | Two products in one repo (world compiler + validation-first GM). Is the split coherent? |
| 2026 positioning | Chat-as-world vs NPC-overlay vs LangGraph-GM vs validation-first RPG engines |

**Do not treat as failure:** missing player narration, missing world editor UI, DAG nodes not yet wired to bake (explicit gate), multiplayer spec-only, C22 packing still on the old AABB path.

**Do treat as framework issues:** Apply does not commit world state; EventBus is SSE-only; many `TaskType` values have no graph; `shared_context` is still an untyped dict; engine graph frozen while the compiler grew.

---

## 0.1 Delta since 2026-08-15 / §8.1 2026-08-17

This window is **compiler + outdoor city**, not GM.

| Changed | Was (Aug 15/17) | Now (Sep 3) |
|---|---|---|
| Commits / HEAD | 282 · `450c0f5` world-seam | 316 · `0342edb` city tz |
| Engine / chat | 74 files / 2 920 · chat 96 | **Unchanged** (DAG still gated) |
| Generators | 290 / 21 290 | 332 / 25 313 |
| Pack | 101 / 9 406 | 112 / 10 515 |
| Tests | 78 / 9 032 | 95 / 15 517 — still almost no DAG tests |
| `dataModel/` | 212 / 7 370 | 223 / 8 702 |
| `db/` | 70 / 2 240 | 77 / 3 686 (`bulkSql`, `locationEntryPoint`) |
| Frontend | 24 / 879 | 37 / 1 572 — still a player shell |
| Docs | 41 / 20 833 | 47 / 23 782 — relief split into generate / consume / v1 archive / code-debt |
| Relief v2 | Live writer 7/10; shore stub; System not emitted; v1 sample still in tree | **ShorePlugin body ✅ · T-3c System emit ✅ · v1 sample/stitch cut ✅ · 8-slot sidecar · hills.** Writer **8/10**. Occupancy fill **R41-T-25 still open**. GM consume still **3/10** |
| Outdoor city | lazy settlement → `map_cells`; persist split | **`SettlementOutdoorOrchestrator`** writes pack city-structure + SQL tree via debug HTTP. **C21** (plot `ground_z` / threshold) in generate. **C22** packing = TZ/plan; code still AABB overlay |
| Road layouts | brief overstated “grid/organic/radial/…” live | **Only `grid` is implemented**; organic / radial / cul-de-sac / courtyard raise `NotImplementedError` |
| Callers | DAG (not bake) · debug HTTP · tests | Same, plus **locations `generate-settlement`** → outdoor orchestrator (still debug HTTP, not DAG) |

**Did not move:** `scene_narration` blocker; DAG gate G1–G5; PatchApplier still state-merge only; EventBus still SSE; most `TaskType` enum-only.

---

## 1. One-paragraph thesis

This is an **AI RPG simulation platform**, not a chat frontend with a lorebook. Two audiences: a **world master** authors rules and registries (JSON import now, editor later); a **player** picks a world and a character and talks to an AI GM. The GM is not allowed to invent geometry or engine keys. Canonical truth is SQLite + an immutable **World Pack** (LOD bake) +, for authored cities, a **pack city-structure layer** (`l.{uid}.settlement.zst`) distinct from the Patch Store. The LLM proposes structured JSON; the engine validates and (in target design) commits. Procedural terrain/settlement/structure is a **pure generator library**. The chat DAG is the intended production caller; today bake, refine, and outdoor materialize are invoked through **permanent debug HTTP harnesses**.

Product analogy used in-repo: Foundry VTT + AI GM + procedural world. Closest 2026 AI-RPG family: validation-first engines (Orchestrated Reality PDVA, MnesOS Director/Narrator, LlamaBrain, Project Lunar) **plus** a DF/Civ-class world compiler that those peers do not have.

---

## 2. Calendar and intensity

| Fact | Value |
|---|---|
| Git root | `2026-05-09T13:59:28+03:00` — `Init project` (already a dump, not empty hello-world) |
| Last commit at snapshot | `2026-09-02T00:15:20+03:00` — `city tz` (`0342edb`) |
| Commits | 316 |
| Authors | AndrewBondaren 306, Andrew 10 (same person in practice) |
| Monthly | 2026-05: 74 · 06: 90 · 07: 91 · 08: 60 · 09 (to the 2nd): 1 |
| This window | 34 commits after `450c0f5` (2026-08-14 → 2026-09-02): relief v2, hills, pack slots, outdoor pack v1, city TZ |
| Owner split | ~1 month DAG runtime, ~2 months generators / pack bake, then ~2.5 weeks **relief v2 + outdoor etalon** with the DAG frozen |

Apparent architectural density is still far above four calendar months of a typical LLM-chat hobby repo. Same explanations as August: (a) pre-existing thesis (system/display, N+1, skeleton-first, validation-first), (b) heavy agent-assisted implementation, (c) almost all new mass in world-gen after the DAG machine was closed. **The engine line count did not move in this window** — that is a design fact (gate), not neglect.

---

## 3. Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.14, FastAPI, aiosqlite, SSE |
| Frontend | React 19, Vite 8, Electron 42, CSS Modules, feature-slices |
| LLM | `LLMRouter`: local Qwen, OpenAI, Anthropic |
| DB | SQLite, **one** migration `0001_initial.sql` (recreate, no incremental ALTER) |
| Schema sync | `validate_schema` at lifespan vs dataclasses (~23 types in `_models`, including `LocationEntryPoint`) |
| Bulk writes | `app.db.bulkSql` — one batch size, one `executemany` loop (map cells, relief grades, persist heartbeat) |

**Layer rules (enforced in Cursor rules, mostly held in code):**

- Generators: pure materialize. No LLM payload, no HTTP, no SQL.
- API: transport only. Debug map / location routes delegate to orchestrators; they are not a second engine.
- Persist: services / orchestrators / (future) DAG nodes — not inside generator functions.
- `dataModel/` Pydantic is the only contract for fields/defaults; no parallel `_DEFAULT_*` literals.
- Engine nodes (`application/engine/nodes/`): **gated**. Agent must not wire new DAG nodes until the owner closes generator smoke (G1–G5 in `tz_world_generation_dag.md`). Gate **not lifted**.

---

## 4. Code mass (2026-09-03, physical lines, no `__pycache__`)

| Area | Files | Lines | Δ vs Aug 15 | Role |
|---|---|---|---|---|
| `worldData/generators/` | 332 | 25 313 | +42 / +4 023 | Pure world-gen library |
| `docs/*.md` | 47 | 23 782 | +6 / +2 949 | Domain TZ (product spec, not agent TODOs). Relief v1 archived out of the live SoT |
| `backend/tests/` | 95 | 15 517 | +17 / +6 485 | Pack / relief / hydrology / outdoor extract / C21 — **still almost no engine DAG tests** |
| `worldData/pack/` | 112 | 10 515 | +11 / +1 109 | Immutable pack bake / refine / read + grade sidecars |
| `dataModel/` | 223 | 8 702 | +11 / +1 332 | Pydantic SoT (grade slots/rays, hills, settlement wire, shore kinds) |
| `db/` | 77 | 3 686 | +7 / +1 446 | Repos + models + `bulkSql` |
| `application/engine/` | 74 | 2 920 | **0** | DAG runtime — frozen this window |
| `jsonValidation/` | 15 | 2 002 | 0 / +58 | Import/runtime resolve |
| `api/` | 19 | 1 733 | 0 / +83 | HTTP |
| `frontend/src` | 37 | 1 572 | +13 / +693 | Player shell (CSS + location-select chrome; not a world editor) |
| `application/chat/` | 4 | 96 | **0** | Turn wrapper |

**Read the imbalance as a design fact, not a bug:** the world compiler is now four months of mass; the GM loop is a closed machine with almost no content nodes; the player UI is still a thin Electron/chat shell. Tests doubled on the compiler side, which **worsens** the inverted pyramid relative to the GM thesis.

Backend routes (`backend/app/api/routes/`): `chat`, `sessions`, `settings`, `worlds`, `locations` (now outdoor materialize), `characters`, `races`, `perks`, `map`, `connections`, `seed`, `debug`, `reliefTemplates`.

DB dataclasses include: `world`, `namedLocation`, `mapCell`, `gameSession`, `sessionScene`, `sessionPending`, `player`, `npc`, `message`, `state`, `faction`, `race`, `world_perk`, `connectionNode/Edge/EdgeCell`, `locationLevel`, `locationPassage`, **`locationEntryPoint` (new)**, `buildingTemplate`, `reliefTemplate`, `reliefGradeInstance/System`, `chunkRefineJob`, `sessionSummary`.

---

## 5. Product roles and data pattern

**Master** sees N+1 registries and `system_*` keys. **Player** must not.

Pattern (`docs/project_data_storage_tz.md`):

| Prefix | Owner |
|---|---|
| `system_*` | Engine refs, formulas, validation. Stable snake_case |
| `display_*` | UI and LLM prose |

Two kinds of N+1: (1) world registries (`worlds.*_registry` — new types), (2) instance field suffixes `_1`, `_2`. Same validator is intended for JSON import and a future world-editor UI.

LLM is supposed to receive `display_*` and lore, never guess `system_*`.

Authored outdoor city is **master write** into pack (`CITY_STRUCTURE`), not a player-turn patch. Gameplay mutations stay in the Patch Store (`tz_settlement_outdoor.md` C1; pack WP-3 clarification).

---

## 6. Engine — framework as coded

Spec: `docs/tz_engine_flow.md`. Runtime: `application/engine/`. **No engine files changed 2026-08-14 → 2026-09-02.** The description below is the same machine as the August brief, restated so this file stays self-contained.

### 6.1 Turn

```
ChatService.handle_message
  pending_repo.upsert                    # crash recovery
  LLMExecutionEngine.run(task_type, message, session)
    for pass in session.max_passes:
      GraphCompiler.compile(state)       # filter NODE_REGISTRY by TaskType
      DAGExecutor.execute(plan, state)
      _apply_task_transition             # intent → new TaskType or gate next_task_type
      break unless requires_replan
    PatchApplier.apply(state)            # after all passes
    ResponseResolver.resolve(state)      # TaskType → output node id
  message_repo.create_turn + narrative   # on success
  pending_repo.delete
```

Optional `task_type` on `ChatRequest` skips intent detection. SSE: `NodeStatusEvent`, `ThinkingEvent`, `ResultEvent`, `ErrorEvent`, `CancelledEvent`. Cancel stores `SessionSnapshot` (`node_results`, `node_status`, `task_type`, original message).

### 6.2 Compile model (not LangGraph)

`GraphCompiler` does **not** store a hardcoded graph per quest.

1. `precompile()` instantiates all registered nodes once.
2. `compile(state)` filters with `RuleEngine` (today: `state.task_type in node.supported_tasks`).
3. Split: `PythonNode.phase == pre_llm` | `LLMNode` | other Python → post_llm.
4. Kahn levels inside each Python phase (parallel via `asyncio.gather`).
5. LLM nodes bucketed by **temperature ASC**; each bucket is **one aggregated** `client.chat()` whose JSON object is keyed by node id. Strict schema: inlined `$ref`, `additionalProperties: false`, all properties required.

Replan changes `task_type` and **recompiles**. That is a task dispatcher, not a two-node Director/Narrator graph.

### 6.3 Phase invariants

| Phase | Who | May replan? | Notes |
|---|---|---|---|
| `pre_llm` | Python | **Yes** — only place | Declared `PythonNodeError` with `requires_replan` / `next_task_type`. Undeclared error = bug. Two gates on one parallel level = `RuntimeError` (replan conflict). `skip_on_replan=False` re-runs DB gates on later passes. |
| `llm` | LLM groups | No; **repair** instead | Same `messages[]`. `RepairOrchestrator` appends error-code DSL patches. Exhaustion → `RuntimeError`. |
| `post_llm` | Python | **Policy: never** | Not fully enforced: `NodeRunner` can still set `requires_replan` if a post_llm node raises that error type. |

### 6.4 LLM contract stack

- Per-node: `dsl` file under `backend/app/dsl/`, `contract_json` Pydantic, `validator`, `dsl_patches: error_code → extra dsl file`.
- Global instruction `dsl/llm_group.txt`: one JSON object, keys = node ids, no prose.
- `LLMValidator`: `ContractValidator` then node validator.
- Providers without system role: single user message with full payload.

**DSL files on disk (still 6):** `llm_group.txt`, `intent_detection/intent_detection.txt`, `intent_detection/repair_confidence.txt`, `context_snap_gatherer/context_snap_gatherer.txt`, `character_generation/character_generation.txt`, `analysis_reasoning/analysis_reasoning.txt`.

Intent node **declares** patches `repair_tone`, `repair_missing_intent`, `repair_confidence`; only `repair_confidence.txt` exists. Context-snap `dsl_patches` keys also lack files. The **mechanism** is real; the **patch library** is thin.

### 6.5 TaskType (29 values)

Technical: `INTENT_DETECTION`, `SCENE_INIT`, `SCENE_START_LOCATION_SELECT`.

User-facing families (enum only except where noted): scene (narration / combat / change_location), character training, character generation, five `GENERATE_*_EVENT`, five `*_ANALYSIS`, crafting, six player actions (sleep/rest/sneak/detect/run/climb).

**Live pipeline:** `INTENT_DETECTION` → gate `SCENE_INIT` | `SCENE_START_LOCATION_SELECT` → intended `SCENE_NARRATION` | combat | change_location | local analysis. Terrain lazy chain is registered on those scene tasks. **No LLM node** is registered for them.

`ResponseResolver._OUTPUT_NODE` already maps `SCENE_NARRATION` → `"scene_narration"`. That node is **not** in `nodes/__init__.py`. Intent can return `scene_narration_render`; resolver then says the task finished with no result. This is documented as an **intentional** blocker until bake/scene contracts stabilize (`tz_project_snapshot.md` §5.5). Do not propose an interim narration slice as the next default step.

### 6.6 Registered nodes (import = register)

**LLM (2):** `context_snap_gatherer` (t=0.2, deps `check_scene`), `intent_detection` (t=0.2, deps gatherer). Same temperature → one aggregated call. Contracts: `ContextSnapContract`, `IntentDetectionContract`.

**Python scene:** `check_scene` (gate: missing scene → `SCENE_INIT`; no `location_uid` → `SCENE_START_LOCATION_SELECT`), `scene_init`, location-select nodes.

**Python terrain (pre_llm, scene tasks):**

```
check_scene → check_terrain → eager_terrain
                            → lazy_terrain → lazy_settlement
               eager/lazy  → terrain_context → terrain_summary
                                            → resolve_weather
```

`terrain_context` still writes `shared_context["terrain"]` (typed `TerrainContext` on `ExecutionState` is TZ-only: `tz_engine_node_context.md`). `eager_terrain` still loads `map_cells`, not pack L0. `lazy_settlement` is **not** the outdoor pack orchestrator.

**Python climate:** `generate_climate`, `recalculate_climate` — **registered with empty `supported_tasks`**, so `RuleEngine` never selects them on a chat turn. `resolve_weather` is live on scene tasks.

**Stub:** `prepare_context` (`PrepareAnalysisContextNode`) — empty tasks.

### 6.7 PatchApplier — honest PDVA

`tz_ideas.md` ID-12 **accepted:** the pass loop is named Plan–Diff–Validate–Apply (Orchestrated Reality, arXiv:2606.16014).

As coded:

| PDVA | Code | Caveat |
|---|---|---|
| Plan | Compiled node set + DSL payload | Not an LLM-written plan object |
| Diff | Full JSON section per node id | Not JSON Patch against world entities |
| Validate | Pydantic contract + node validator + repair | No “ID exists in DB” domain validator wired yet |
| Apply | `pending_patches` → merge into `ExecutionState.node_results` | **Does not write SQLite / pack.** World writes happen inside Python `execute()` via repos (e.g. lazy settlement `insert_bulk_ignore`) |

Closest analog Apply (OR paper) commits content-hashed JSON deltas to canonical world state. That is **not** what `PatchApplier` does today. Outdoor etalon writes (pack + SQL) happen in `SettlementOutdoorOrchestrator`, outside PDVA.

### 6.8 EventBus

`application/events/eventBus.py`: `ContextVar` + `asyncio.Queue` for **this HTTP request’s SSE**. Not a persistent world event bus. Lazy simulation, witness graph, essential-NPC background LLM all assume a world bus (`tz_lazy_simulation.md`, `tz_multiplayer.md`). Those are spec.

### 6.9 ChatService

96 lines. Unchanged. No scene logic. Engine owns control; chat owns turn persistence and pending crash recovery.

---

## 7. World pack bake — real job, debug caller

Spec: `docs/tz_world_pack_storage.md`, `docs/tz_map_light_bake.md`, `docs/tz_terrain_relief.md`, `docs/tz_settlement_outdoor.md`.

**This is not “generators only exist as debug scripts.”** Bake is an orchestrated job. HTTP is explicitly a **debug harness**; production caller is supposed to be DAG nodes after gate G1–G5.

`map.py` module docstring (current):

- Production materialization → engine DAG (not these routes).
- `POST …/map/pack/bake?mode=light|full|detailed` — L0 / detailed L2.
- `POST …/map/refine-from-entry` / `schedule-chunk-refine` — gameplay-shaped L2 from an entry point (still invoked via debug HTTP today).
- Legacy `generate-surface` / `materialize-stack` write routes: **removed**.

`locations.py` (new this window): `POST …/locations/{uid}/generate-settlement` and batch `generate-settlements` → `SettlementOutdoorOrchestrator`. Same pattern: thin HTTP over an orchestrator, **not** a second engine, **not** DAG.

### 7.1 Jobs

| Job | LOD | Scope | Role |
|---|---|---|---|
| `light_bake` | L0 world map + climate coarse + location skeletons | location ∪ declared hydro tiles | Minimum pack for map + player entry. SLO in TZ: bake light ≤ 2 min typical world |
| `full_bake` | Same L0 pipeline | entire `world_bounds` | Master / CI offline fill |
| `detailed_bake` | L2 | `scope=location\|wilderness` | Offline warm-start of fine terrain / grades |
| Entry refine (WP-13) | L2 from spawn outward | scene volume | Gameplay hot path **by design**; currently debug HTTP → `EntryRefineOrchestrator` |
| Outdoor materialize | Pack **city-structure** + SQL tree | one settlement uid (or C16 selectors) | Authored etalon **after** land bake. Not a fourth bake mode. Debug HTTP today |

Product UX (TZ, non-negotiable): first LLM reply ≤ 30 s p95 from spawn; must not block on full L2. While a fine chunk is missing, narration/mechanics should use **L0 + L1 + patches**.

Storage thesis: OLTP `map_cells` cannot hit cold-load ≤ 5 min (millions of INSERT). Target is **immutable World Pack** (mmap / zstd tiles) + **Patch Store** (SQLite deltas). Pack + LOD together; LOD without pack is rejected as insufficient. Authored city is a **pack layer**, not OLTP occupancy-flood and not Patch Store.

### 7.2 Orchestrators (code)

- `PackMaterializationOrchestrator` — L0 light/full body; climate coarse; relief grade persist; tile planner; finalize pack on world row.
- `WorldMapBakeOrchestrator` — compose light grid → writer. Contributors: terrain paint, hydro, relief, mountain, ravine, road, settlement, climate, landcover. World seam copy across tile edges (commit 2026-08-14).
- `PackDetailedBakeOrchestrator` — L2 detailed.
- `FineTerrainRefineOrchestrator` / `FineChunkRunner` / persist — parallel chunk refine. Grade path: mill → paint → one fill → pack sidecar (`pack_cell_slots` / `slots[8]`).
- `EntryRefineOrchestrator` — from entry anchor. On-demand mill/paint this window.
- `ClimatePackBakeOrchestrator` — coarse climate in pack.
- **`SettlementOutdoorOrchestrator`** — generate layout → extract tree → pack `l.{uid}.settlement.zst` + SQL (`named_locations`, connections, levels, entry points). C19 protocol: encode tmp → SQL tx → `os.replace`.
- Read: `PackReadContext`, `PackDebugReadFacade`, `PackRenderReadFacade`, ASCII/grid renderers (`tz_pack_ascii_render.md`). Dump reads sidecar codes; occupancy validator is **dev-only** (`DEBUG_GRADE_SLOT_VALIDATE=1`).

Light grid is a **binding L0 blueprint** (not a preview). Fine terrain / outdoor grades live at L2 (`surface_grade`, `grade_n`). City structure is a separate pack layer above `location_terrain`, below patches.

### 7.3 Caveats (bake exists, not finished)

- DAG is **not** the bake or outdoor caller yet (gate).
- Hydrology **is** a generator used from bake — not an empty stub. Completeness vs TZ (bathymetry stub modules remain) is a domain caveat.
- Some WP-13 helpers (`tile_cross` / `location_entry` kinds) still open; debug/light bake often uses `session_start`.
- Parallel workers: `free_cores` still a caller-boundary stub in places; determinism G4 is a gate item.
- Player chat does **not** yet consume pack L0 or Grade as scene facts (`terrain_summary` still biome-key flavored; `eager_terrain` talks `map_cell_repo`).
- Grade occupancy algorithm for a full 8-slot cell (**R41-T-25**) is **open**; leftover-pack helpers remain for locked tests (RELIEF-TD-4).
- `packBakeLog.py` is a god **module** (~1158 lines) — logging debt, not a second bake engine.

---

## 8. Generator library (the mass after the DAG closed)

Hierarchy (`tz_assembler_hierarchy.md`):

```
SettlementAssembler
  └── DistrictAssembler
        └── StructureAreaAssembler          # C21: ground_z + threshold (door/gate/parcel_edge)
              └── StructureAssembler (registry: building, ruins, resourceExtraction, vastHull)
                    └── StructureGeneratorService  # interior box
                          └── StructureInteriorAssembler  # no TZ; furniture/NPC later
```

**Semantic-first:** `economic_tier` is intent (“poor district”), not a pile of literals. Materials, lighting, roads, barriers, building templates resolve through registries (`TierResolver`).

| Domain | Entry | Status (honest) |
|---|---|---|
| Terrain surface | `TerrainGeneratorService`, passes: surface / gap / column fill | Live; pack L0 compose sits on this |
| Relief / grades | `generators/terrain/relief/discover/*` + L2 `GradeFormation`; templates in `relief_templates/` | **Live writer = v2 (R41).** Mill Q1/Q2 → pack 8 slots → SQL Instance. ShorePlugin body live; ravine live; T-3c `ReliefGradeSystem` emit live; v1 sample/stitch **removed**. Open: **R41-T-25** full 8-slot occupancy. Product scores: §8.1 |
| Hills | `generators/terrain/hills/` | **New this window.** Placement + raster; tests `test_open_land_hills.py` |
| Mountains | peak/ridge/saddle/sideFill | Live enough to stamp L0 |
| Hydrology | `HydrologyGeneratorService.apply` | Live generator, used in bake; shore paint tests added; not “empty stub” |
| Climate | `ClimateOrchestratorService`, runtime assembler | Live math; pack coarse bake; engine `generate_climate` node dead (empty tasks) |
| Roads | `DistrictRoadGenerator` | **`grid` only.** `organic` / `radial` / `cul_de_sac` / `courtyard` → `NotImplementedError` (C22 plan does not implement them) |
| Structure interiors | rooms, passages, some staircases | Deterministic generator live; several staircase builders still `NotImplementedError` (straight, spiral, shaft, movable ladder) |
| Settlement layout | `SettlementGeneratorService` → assembler phases A–F | Live layout. **C21** plot z/threshold in `StructureAreaAssembler` (tests `test_c21_plot_ground_z.py`). Organic footprint / z-topology G–H incomplete. Ruins/extraction/vastHull assemblers still `NotImplementedError` |
| District packing | `planner/areaSlots.py` | **Still AABB overlay + full grid.** Target C22 (2D bin, two-pass, street frame after priority) = TZ + [`.cursor/plans/c22-district-packing-migration-done.md`](./c22-district-packing-migration-done.md); **code not migrated** (plan status: to agree, no code until owner says) |
| Outdoor etalon | `SettlementOutdoorOrchestrator` | **Live via debug HTTP.** Pack city-structure + SQL tree (districts, buildings, levels, entry points). DAG / `lazy_settlement` still the old `map_cells` path |
| Barriers | perimeter/cells | Partial; settlement vs district `PerimeterBarrier` instances specified in TZ (C22); district barrier cells TODO |
| Flora / ores / caves | mostly stubs or thin | Not the center of gravity |
| Construction (player build) | TZ | Not in DAG |

**Coordinates (NC-1):** `WORLD_SURFACE_GRID` vs `WORLD_FINE_GRID` vs `LOCATION_FINE_GRID`. Conversion only via `generators/coordinates/convert.py`. This window added `columnSurface`, `gridRay`, `approachZ` for C21.

**Skeleton-first:** world create/import writes `NamedLocation` skeleton + footprint occupancy; first entry is supposed to materialize settlement geometry. **Two persist stories now coexist:** DAG `lazy_settlement` still writes some cells via repo; master/debug outdoor writes pack city-structure + SQL names. That split is documented, not accidental — and it is a **scene-facts vs pack** risk until session start uses the outdoor orchestrator.

**Allowed callers of the same library** (`tz_world_generation_dag.md`): (1) Engine DAG — not yet for bake/outdoor, (2) Debug HTTP — **current** (map bake **and** locations generate-settlement), (3) In-process unit tests — 95 modules, concentrated on pack/relief.

Template packs: domain roots must not mix. Relief library: `relief_templates/` → SQL `relief_templates`. Buildings: `structures_templates/` (convention; scale when that TZ is touched).

### 8.1 Outdoor relief grade — product axis (updated 2026-09-03)

This is part of **World substrate**, not a second product. Score it as a **discrete-grid grade entity** for an AI GM (one uid, one θ, occupancy, 8 pack slots per cell). Do **not** score it as Gaea / Unity landscape / erosion art — wrong league.

August 17 said: world substrate stays 8/10; it is not a 9 until shore/System/v1-cut **and** the turn reads pack Grade. **First conjunct happened. Second did not.**

| Axis | Aug 17 | Sep 3 | Note |
|---|---|---|---|
| Live v2 writer (R41 discover) | **7/10** | **8/10** | ShorePlugin, T-3c System emit, v1 cut, 8-slot sidecar, hills. Held off 9 by **R41-T-25** occupancy + leftover-pack dual path for locked tests |
| v1 occupancy path | **4/10** | **removed** | Layer 7 cut 2026-08-18 (`sample`/`stitch`/`planned` gone) |
| L2 volume apply (`GradeFormation`) | **~8/10** | **~8/10** | Shared, closed; not a second ribbon planner. Do not fork |
| Vs public discrete-grid grade models | **~8/10** | **~8/10** | Distinctive: occupancy + ray seam + plugin body + face catalog + 8-slot sidecar. Weak: 1D extrusion across W, diag W=1, occupancy holes (T-25) |
| Vs landscape / erosion tools | **N/A** | **N/A** | Wrong product class |
| Grade facts on a player turn | **3/10** | **3/10** | Entity exists; dump/debug can see slots; `terrain_summary` still biome keys; `scene_narration` gated |
| Master authoring of grade | **8/10** | **8/10** | Templates + pick + seeded bake. No editor UI |

**World substrate overall stays 8/10.** Compiler-side density is why that 8 is no longer “relief incomplete”; it is not a 9 until (a) T-25 occupancy closes and (b) the turn reads pack Grade. Relief is still why the 8 is not a 6.

Spec: `docs/tz_terrain_relief.md` (generate SoT). Consume/dump: `docs/tz_terrain_relief_consume.md`. v1 bake archive: `docs/tz_terrain_relief_v1_superseded.md`. Code smells: `docs/tz_terrain_relief_technical_debt.md`.

### 8.2 Outdoor settlement etalon — product axis (new 2026-09-03)

Not relief. Not a fourth bake mode. Score as **authored city on an already-baked pack** for an AI GM (tree of names + plot graph), not as a city-builder UI.

| Axis | Score | Note |
|---|---|---|
| Orchestrator + pack city layer | **7/10** | `SettlementOutdoorOrchestrator` + C19 tmp→SQL→replace is a real etalon path. Debug HTTP caller. DAG unused |
| C21 plot z / threshold | **7/10** | Core P13 in `StructureAreaAssembler` + tests. Leftover C21-T\* (plaza stamp, packing vs final floor names) open |
| C22 district packing / façade | **3/10** | SoT locked in TZ (connections §5.1.3, city §6.3). Code still AABB + overlay grid. Plan exists, not implemented |
| SQL tree (district → building, levels, entries) | **6/10** | Extract + persist live; C20 role column (`front`/`service`) specified — SQL role may still be catching up |
| City facts on a player turn | **2/10** | Same hole as Grade: etalon can exist on disk; scene nodes do not read it |

Do not grade C22 as “failed” — it is **spec-ahead**, owner has not authorized packing code.

---

## 9. JSON validation and authoring

`application/jsonValidation/` — POJO-first v1. `resolve` policy: import **strict → 422**, runtime **warn-only**. Line count barely moved (+58).

`worldSlices.py` is the registry of `worlds` master-data slices (climate scalars, terrain scalars, hydrology blob, relief templates/policy/obstacles/canals, materials, tiers, climate zones, weather, location types, city sizes, moods, district templates, building/barrier/room templates, connection types, road settings, lore, terrain masks, terrain categories, hills, …). Adding a world field = POJO + SQL column + slice row; not a new default table in a generator.

Gaps vs TZ: bundle races / perks / locations not fully in JV; C22 skeleton fields (`frontage_type_order`, `structure_counts`, `structure_priority`, settlement `perimeter_barrier`) are TZ-ahead of POJO (see C22 plan §1.2); world editor UI is a placeholder route.

---

## 10. Frontend (player shell)

Routes: `/` sessions → `/new` world → `/new/:worldId` character → `/chat/:sessionId` SSE chat. `/settings/backend` LLM. `/settings/world` **placeholder**.

~1 572 lines (was ~879). Growth is chrome (CSS modules, location-select message), not a master surface. Can: list sessions, pick world/character, stream node status / thinking / result, cancel. Cannot: world editor, map as a product UI, master registries, pack/grade inspector.

---

## 11. Idea registry vs code vs 2026 analogs

Internal registry: `docs/tz_ideas.md`. External peers cited there and still accurate in 2026:

- Orchestrated Reality (arXiv:2606.16014) — parameterized-action POMDP, PDVA, canonical JSON tree, narrative as observation `o = O(s)`.
- MnesOS — LangGraph Director / air-gapped Narrator, YARE deterministic rules, cartridge (`yare.yaml` + lore.md), BYOK.
- LlamaBrain — validation gate, authority hierarchy, author fallback prose.
- Project Lunar — witness filter, plot-lock, scene notebook, SSE narrator, NPC private minds.
- Omnia — patch merge, world tick, tiered NPC LOD.
- Mainstream chat-as-world: SillyTavern / Risu / AI Dungeon / NovelAI adventure (lorebook + summary/RAG; model **is** the world).
- NPC overlay: Inworld / Convai / NVIDIA ACE (LLM as character in an existing game).

| Idea | Status here | Peer |
|---|---|---|
| PDVA pass loop | Accepted + coded; Apply is state-merge | OR |
| Intent kind + structured params | `TaskType` + intent contract; most kinds have no graph | OR `a = (k, x_k)` |
| 3-phase compiled DAG + temp-batched LLM | **Runtime, distinctive, frozen this window** | Unusual vs 2-node LangGraph |
| Error-code repair DSL | Mechanism yes, files thin | Schema retry common; this patch map is not |
| SSE node telemetry + cancel/resume | Runtime | Lunar streams prose; job-like cancel is rarer |
| `dataModel` + N+1 + system/display | Runtime in data layer | MnesOS public_state vs system_notes |
| Generator library + pack bake | **Larger runtime** | Almost no 2026 AI-RPG peer; closer to DF/Civ + cook jobs |
| Outdoor Grade as discrete entity (R41) | **Live writer 8/10**; v1 gone; T-25 open | Almost no AI-RPG peer; **not** Gaea/landscape. Consumption on turn still 3/10 |
| Authored city on pack (not OLTP flood) | **New runtime** (orchestrator + city-structure layer) | Almost no AI-RPG peer; closer to a world compiler export |
| Director vs Narrator (ID-9) | Spec; phases exist, roles inside `llm` do not | MnesOS **core product** |
| Scene notebook (ID-4) | Spec; `shared_context` is the hatch | Lunar |
| Witness (ID-3) | Spec | Lunar witnessed-by |
| Beliefs / rumors (ID-1, ID-2) | Spec | AI RPG Engine presentation channels |
| Plot-lock (ID-5) | Spec; event TaskTypes exist | Lunar |
| Event graph hash + expand (ID-13) | Spec, **this project’s own** (not RAG, not lore) | OR hashes deltas; not the same protocol |
| Authority on patches (ID-8) | Spec; natural home `PatchApplier` | LlamaBrain |
| Preset cartridge + smoke (ID-6) | Import+JV; no manifest/smoke | MnesOS cartridge |
| Graceful fallback prose (ID-10) | Spec | LlamaBrain |
| BYOK (ID-11) | Deferred; router exists | MnesOS |
| Perception filters on geometry | TZ only | Almost no AI-RPG peer |
| NPC LOD / lazy sim | TZ only | Omnia; opposite of AI-Town |
| World snapshot / replay | Schema mentioned; runtime module missing | OR hashed state |
| RAG as primary memory | **Deferred (R-2)** | SillyTavern default |
| LLM-generated geometry | **Rejected (R-1)** | Some worldweaver toys |
| LLM every ambient NPC / AgentCity | **Rejected (R-3, R-5)** | Generative-agents papers |

---

## 12. What works end-to-end vs what is gated

| Loop | Status 2026-09-03 |
|---|---|
| Dev stack, session CRUD, chat SSE, cancel/resume skeleton | Yes |
| World/character JSON import (partial JV) | Yes |
| Intent LLM + repair | Yes |
| Scene gate (init / pick start location) | Yes |
| Pack **light/full/detailed bake** via debug HTTP | Yes, with caveats in §7.3 |
| Entry/chunk refine via debug HTTP | Yes; on-demand mill/paint |
| ASCII/grid pack render (developer dump) | Yes; dump reads `slots[8]` |
| Hydrology as generator inside bake | Yes (not empty) |
| Relief grades / detailed grade path | **Live v2 writer 8/10.** ShorePlugin, System emit, v1 cut. T-25 occupancy open. Scores §8.1 |
| Hills on open land | Yes (generator + tests) |
| Outdoor settlement etalon via debug HTTP | **Yes** — pack city-structure + SQL tree. C21 core yes. C22 packing no. Scores §8.2 |
| Terrain context into `shared_context` on scene tasks | Yes, if those tasks run — still `map_cells`, not pack |
| **Player narration turn** | **No** — no `scene_narration` node (conscious) |
| Bake / outdoor called from DAG / session start | **No** — gate |
| LLM reads pack L0 / Grade / city-structure as facts | **No** |
| World editor | Placeholder |
| Most TaskTypes | Enum only |
| Engine/DAG automated tests | Almost none (pyramid more inverted) |
| Interior furnishing | Not started |
| Multiplayer executor | Spec only |
| C22 district packing | TZ + plan only |

---

## 13. Framework holes (for a harsh reviewer)

1. **Apply ≠ world commit.** The validation-first thesis is incomplete until one applier owns canonical mutation (pack patches / SQL), including authority (ID-8). Outdoor etalon writes bypass PDVA entirely — correct for master bake, but it widens the two-writer story.
2. **`llm` phase has no Director/Narrator split.** Temperature groups exist; both live LLM nodes are the intent path.
3. **`shared_context: dict`.** Typed domain contexts are specified, not on `ExecutionState`.
4. **EventBus is SSE.** Cannot carry witness / essential NPC / lazy sim without a second bus.
5. **Registered ≠ live.** Empty `supported_tasks` on climate generate nodes; repair DSL map has missing files.
6. **Scene facts vs pack — now three sources.** Terrain DAG nodes (`map_cells`), pack bake (L0/L2/Grade), outdoor etalon (city-structure). Player path still reads the first. Drift risk went **up** this window because the second and third got more real.
7. **Test pyramid inverted relative to the GM thesis, worse than August.** 15.5k lines of tests sit on generators/pack; the DAG/repair/replan machine is almost untested and **did not gain tests** while the compiler did.
8. **Spec-ahead on C22.** District packing TZ is the live SoT; `areaSlots.py` is still AABB. A reviewer who diffs TZ vs `DistrictAssembler` will see a planned pipeline, not a lie, if they read the C22 plan status — but the gap is sharp.

---

## 14. Suggested verdict shape (for the evaluating model)

A fair summary, not a scorecard you must copy:

- **Thesis quality:** still rare in 2026 AI RPG (validation-first + geometric substrate). Internally consistent in docs and in layer rules. Outdoor etalon (pack city layer ≠ Patch Store) is the thesis applied to cities, not a third product.
- **Engine:** a real compiled runtime (ahead of typical LangGraph-RPG toys) with a thin **content** graph (only intent). Closing the DAG bought the machine, not the GM. **This window did not touch it.** That is discipline (gate), and also the bet getting more lopsided.
- **World:** four months bought an actual bake/refine/pack compiler plus a live outdoor-grade writer (8/10 in the discrete-grid league) plus an outdoor city etalon path. Still driven by debug HTTP. That is a world-compiler product, not a stub.
- **Outdoor grade:** v1 is gone; shore and System emit landed; 8-slot sidecar exists. Do not grade it as a landscape tool. It still does not feed the GM turn (3/10). T-25 occupancy is the honest remaining generate hole.
- **Outdoor city:** orchestrator + C21 are real; C22 packing is not. Same consumption hole as Grade, slightly worse (2/10) because even the debug path is new and the DAG still writes `map_cells`.
- **Risk:** Foundry + AI-GM + procedural world is studio-sized. The August verdict still holds, with a sharper edge: further months of bake **and** city etalon without (1) session start consuming the pack the bake already produces and (2) PDVA Apply owning world commits yield a strong world compiler with an unused GM machine. The compiler got **more** worth consuming. The consumer did not move.

**Conscious nos to respect:** no LLM geometry, no RAG-as-memory, no LLM-per-ambient-NPC, no interim `scene_narration` until the scene contract is stable, no agent-wired DAG nodes until owner lifts the gate, no C22 packing code until owner says «делай».

---

## 15. Primary files for a reviewer who will open the repo

| Path | Why |
|---|---|
| `docs/tz_engine_flow.md` | Pass loop, repair, invariants |
| `docs/tz_world_pack_storage.md` | Pack + LOD + UX SLOs |
| `docs/tz_terrain_relief.md` | Outdoor grade generate SoT (R41); product scores in this brief §8.1 |
| `docs/tz_terrain_relief_consume.md` | How dump/LLM are supposed to read Grade |
| `docs/tz_settlement_outdoor.md` | Outdoor city etalon (C1–C22); scores §8.2 |
| `docs/tz_world_generation_dag.md` | Library vs callers, DAG gate |
| `docs/tz_ideas.md` | Idea registry + analog list |
| `docs/tz_project_snapshot.md` | Older living snapshot (v1.3, 2026-08-17) — numbers here win |
| `backend/app/application/engine/llmExecutionEngine.py` | Outer loop (unchanged this window) |
| `backend/app/application/engine/graphs/graphCompiler.py` | Compile |
| `backend/app/application/engine/repair/patchApplier.py` | Apply (state only) |
| `backend/app/api/routes/map.py` | Debug bake harness contract |
| `backend/app/api/routes/locations.py` | Debug outdoor materialize harness |
| `backend/app/application/worldData/pack/bake/packMaterializationOrchestrator.py` | L0 bake job |
| `backend/app/application/worldData/settlementOutdoor/settlementOutdoorOrchestrator.py` | City etalon job |
| `backend/app/application/worldData/generators/terrain/relief/discover/` | Live grade writer |
| `backend/app/dataModel/` | Contract SoT |

---

*End of brief. Compiled 2026-09-03 from repository state (HEAD `0342edb`, 2026-09-02) plus working-tree TZ on C22 packing (not yet code). Previous brief: 2026-08-15 / §8.1 2026-08-17, HEAD `450c0f5`.*
