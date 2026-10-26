# AI RPG Platform — global characterization

> **Superseded for current numbers:** [`.cursor/plans/project-characterization-2026-09-03.md`](./project-characterization-2026-09-03.md) (2026-09-03). Keep this file as the August snapshot.

**Date:** 2026-08-15  
**Purpose:** Self-contained brief for an external reviewer / other LLM.  
**Not a product pitch.** Evaluate architecture, thesis consistency, and engineering density — not “can a player finish a session.”

**How this document was compiled:** code + domain TZ (`docs/tz_*.md`) + git history + author-stated time split. Official living snapshot `docs/tz_project_snapshot.md` was last a full write-up on 2026-07-20; numbers below supersede it where they conflict.

**Author time split (stated by the project owner, matches git mass):** ~1 month closing the DAG runtime, ~2 months generators + world pack bake. Calendar age of the git repo: **2026-05-09 → 2026-08-14** (~3.2 months, 282 commits, essentially one author).

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

**Do not treat as failure:** missing player narration, missing world editor UI, DAG nodes not yet wired to bake (explicit gate), multiplayer spec-only.

**Do treat as framework issues:** Apply does not commit world state; EventBus is SSE-only; many `TaskType` values have no graph; `shared_context` is still an untyped dict.

---

## 1. One-paragraph thesis

This is an **AI RPG simulation platform**, not a chat frontend with a lorebook. Two audiences: a **world master** authors rules and registries (JSON import now, editor later); a **player** picks a world and a character and talks to an AI GM. The GM is not allowed to invent geometry or engine keys. Canonical truth is SQLite + an immutable **World Pack** (LOD bake). The LLM proposes structured JSON; the engine validates and (in target design) commits. Procedural terrain/settlement/structure is a **pure generator library**. The chat DAG is the intended production caller; today the bake/refine path is invoked through a **permanent debug HTTP harness**.

Product analogy used in-repo: Foundry VTT + AI GM + procedural world. Closest 2026 AI-RPG family: validation-first engines (Orchestrated Reality PDVA, MnesOS Director/Narrator, LlamaBrain, Project Lunar) **plus** a DF/Civ-class world compiler that those peers do not have.

---

## 2. Calendar and intensity

| Fact | Value |
|---|---|
| Git root | `2026-05-09T13:59:28+03:00` — `Init project` (already a dump, not empty hello-world) |
| Last commit at snapshot | `2026-08-14T20:03:15+03:00` — `refactor: add world seam to pack bake` |
| Commits | 282 |
| Authors | AndrewBondaren 272, Andrew 10 (same person in practice) |
| Monthly | 2026-05: 74 · 06: 90 · 07: 91 · 08 (to the 14th): 27 |
| Owner split | ~1 month DAG runtime, ~2 months generators / pack bake |

Apparent architectural density is much higher than three calendar months of a typical LLM-chat hobby repo. That is explained by: (a) a pre-existing thesis (system/display, N+1, skeleton-first, validation-first), (b) heavy agent-assisted implementation, (c) almost all mass going into world-gen after the DAG machine was closed.

---

## 3. Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.14, FastAPI, aiosqlite, SSE |
| Frontend | React 19, Vite, Electron, CSS Modules, feature-slices |
| LLM | `LLMRouter`: local Qwen, OpenAI, Anthropic |
| DB | SQLite, **one** migration `0001_initial.sql` (recreate, no incremental ALTER) |
| Schema sync | `validate_schema` at lifespan vs dataclasses |

**Layer rules (enforced in Cursor rules, mostly held in code):**

- Generators: pure materialize. No LLM payload, no HTTP, no SQL.
- API: transport only. Debug map routes delegate to orchestrators; they are not a second engine.
- Persist: services / orchestrators / (future) DAG nodes — not inside generator functions.
- `dataModel/` Pydantic is the only contract for fields/defaults; no parallel `_DEFAULT_*` literals.
- Engine nodes (`application/engine/nodes/`): **gated**. Agent must not wire new DAG nodes until the owner closes generator smoke (G1–G5 in `tz_world_generation_dag.md`).

---

## 4. Code mass (2026-08-15, physical lines, no `__pycache__`)

| Area | Files | Lines | Role |
|---|---|---|---|
| `worldData/generators/` | 290 | 21 290 | Pure world-gen library |
| `docs/tz_*.md` + related docs | 41 | 20 833 | Domain TZ (product spec, not agent TODOs) |
| `worldData/pack/` | 101 | 9 406 | Immutable pack bake / refine / read |
| `backend/tests/` | 78 | 9 032 | Almost all pack/relief/hydrology/JV — almost no engine DAG tests |
| `dataModel/` | 212 | 7 370 | Pydantic SoT |
| `application/engine/` | 74 | 2 920 | DAG runtime |
| `db/` | 70 | 2 240 | Repos + models |
| `jsonValidation/` | 15 | 1 944 | Import/runtime resolve |
| `api/` | 19 | 1 650 | HTTP |
| `frontend/src` | 24 | 879 | Player shell |
| `application/chat/` | 4 | 96 | Turn wrapper |

**Read the imbalance as a design fact, not a bug:** the world compiler is the bulk of the three months; the GM loop is a closed machine with almost no content nodes; the player UI is a thin Electron/chat shell.

Backend routes (`backend/app/api/routes/`): `chat`, `sessions`, `settings`, `worlds`, `locations`, `characters`, `races`, `perks`, `map`, `connections`, `seed`, `debug`, `reliefTemplates`.

DB dataclasses include: `world`, `namedLocation`, `mapCell`, `gameSession`, `sessionScene`, `sessionPending`, `player`, `npc`, `message`, `state`, `faction`, `race`, `world_perk`, `connectionNode/Edge/EdgeCell`, `locationLevel`, `locationPassage`, `buildingTemplate`, `reliefTemplate`, `reliefGradeInstance/System`, `chunkRefineJob`, `sessionSummary`.

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

---

## 6. Engine — framework as coded

Spec: `docs/tz_engine_flow.md`. Runtime: `application/engine/`.

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

**DSL files on disk (6):** `llm_group.txt`, `intent_detection/intent_detection.txt`, `intent_detection/repair_confidence.txt`, `context_snap_gatherer/context_snap_gatherer.txt`, `character_generation/character_generation.txt`, `analysis_reasoning/analysis_reasoning.txt`.

Intent node **declares** patches `repair_tone`, `repair_missing_intent`, `repair_confidence`; only `repair_confidence.txt` exists. Context-snap `dsl_patches` keys also lack files. The **mechanism** is real; the **patch library** is thin.

### 6.5 TaskType (28 values)

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

`terrain_context` still writes `shared_context["terrain"]` (typed `TerrainContext` on `ExecutionState` is TZ-only: `tz_engine_node_context.md`).

**Python climate:** `generate_climate`, `recalculate_climate` — **registered with empty `supported_tasks`**, so `RuleEngine` never selects them on a chat turn. `resolve_weather` is live on scene tasks.

**Stub:** `prepare_context` (`PrepareAnalysisContextNode`) — empty tasks, not `@register_python` in the same style as others.

### 6.7 PatchApplier — honest PDVA

`tz_ideas.md` ID-12 **accepted:** the pass loop is named Plan–Diff–Validate–Apply (Orchestrated Reality, arXiv:2606.16014).

As coded:

| PDVA | Code | Caveat |
|---|---|---|
| Plan | Compiled node set + DSL payload | Not an LLM-written plan object |
| Diff | Full JSON section per node id | Not JSON Patch against world entities |
| Validate | Pydantic contract + node validator + repair | No “ID exists in DB” domain validator wired yet |
| Apply | `pending_patches` → merge into `ExecutionState.node_results` | **Does not write SQLite / pack.** World writes happen inside Python `execute()` via repos (e.g. lazy settlement `insert_bulk_ignore`) |

Closest analog Apply (OR paper) commits content-hashed JSON deltas to canonical world state. That is **not** what `PatchApplier` does today.

### 6.8 EventBus

`application/events/eventBus.py`: `ContextVar` + `asyncio.Queue` for **this HTTP request’s SSE**. Not a persistent world event bus. Lazy simulation, witness graph, essential-NPC background LLM all assume a world bus (`tz_lazy_simulation.md`, `tz_multiplayer.md`). Those are spec.

### 6.9 ChatService

96 lines. No scene logic. Engine owns control; chat owns turn persistence and pending crash recovery.

---

## 7. World pack bake — real job, debug caller

Spec: `docs/tz_world_pack_storage.md`, `docs/tz_map_light_bake.md`, `docs/tz_terrain_relief.md`.

**This is not “generators only exist as debug scripts.”** Bake is an orchestrated job. HTTP is explicitly a **debug harness**; production caller is supposed to be DAG nodes after gate G1–G5.

`map.py` module docstring (current):

- Production materialization → engine DAG (not these routes).
- `POST …/map/pack/bake?mode=light|full|detailed` — L0 / detailed L2.
- `POST …/map/refine-from-entry` / `schedule-chunk-refine` — gameplay-shaped L2 from an entry point (still invoked via debug HTTP today).
- Legacy `generate-surface` / `materialize-stack` write routes: **removed**.

### 7.1 Jobs

| Job | LOD | Scope | Role |
|---|---|---|---|
| `light_bake` | L0 world map + climate coarse + location skeletons | location ∪ declared hydro tiles | Minimum pack for map + player entry. SLO in TZ: bake light ≤ 2 min typical world |
| `full_bake` | Same L0 pipeline | entire `world_bounds` | Master / CI offline fill |
| `detailed_bake` | L2 | `scope=location\|wilderness` | Offline warm-start of fine terrain / grades |
| Entry refine (WP-13) | L2 from spawn outward | scene volume | Gameplay hot path **by design**; currently debug HTTP → `EntryRefineOrchestrator` |

Product UX (TZ, non-negotiable): first LLM reply ≤ 30 s p95 from spawn; must not block on full L2. While a fine chunk is missing, narration/mechanics should use **L0 + L1 + patches**.

Storage thesis: OLTP `map_cells` cannot hit cold-load ≤ 5 min (millions of INSERT). Target is **immutable World Pack** (mmap / zstd tiles) + **Patch Store** (SQLite deltas). Pack + LOD together; LOD without pack is rejected as insufficient.

### 7.2 Orchestrators (code)

- `PackMaterializationOrchestrator` — L0 light/full body; climate coarse; relief grade persist; tile planner; finalize pack on world row.
- `WorldMapBakeOrchestrator` — compose light grid → writer. Contributors: terrain paint, hydro, relief, mountain, ravine, road, settlement, climate, landcover. **World seam** copy across tile edges (commit 2026-08-14).
- `PackDetailedBakeOrchestrator` — L2 detailed.
- `FineTerrainRefineOrchestrator` / `FineChunkRunner` / persist — parallel chunk refine.
- `EntryRefineOrchestrator` — from entry anchor.
- `ClimatePackBakeOrchestrator` — coarse climate in pack.
- Read: `PackReadContext`, `PackDebugReadFacade`, `PackRenderReadFacade`, ASCII/grid renderers (`tz_pack_ascii_render.md`).

Light grid is a **binding L0 blueprint** (not a preview). Fine terrain / outdoor grades live at L2 (`surface_grade`, `grade_n`).

### 7.3 Caveats (bake exists, not finished)

- DAG is **not** the bake caller yet (gate).
- Hydrology **is implemented as a generator** (coastal sea, open ocean, lakes, rivers, landforms, autoresolve seas) and is used from bake context — this **supersedes** the July snapshot “hydrology = stub”. Completeness vs TZ (bathymetry still has stub modules, declared vs procedural coverage) is still a domain caveat, not “empty function.”
- Some WP-13 helpers (`tile_cross` / `location_entry` kinds) still open; debug/light bake often uses `session_start`.
- Parallel workers: `free_cores` still a caller-boundary stub in places; determinism G4 is a gate item.
- Player chat does **not** yet consume pack L0 as scene facts for the LLM (terrain nodes still talk `map_cell_repo` / `shared_context`).

---

## 8. Generator library (the two-month mass)

Hierarchy (`tz_assembler_hierarchy.md`):

```
SettlementAssembler
  └── DistrictAssembler
        └── StructureAreaAssembler
              └── StructureAssembler (registry: building, ruins, resourceExtraction, vastHull)
                    └── StructureGeneratorService  # interior box
                          └── StructureInteriorAssembler  # no TZ; furniture/NPC later
```

**Semantic-first:** `economic_tier` is intent (“poor district”), not a pile of literals. Materials, lighting, roads, barriers, building templates resolve through registries (`TierResolver`).

| Domain | Entry | Status (honest) |
|---|---|---|
| Terrain surface | `TerrainGeneratorService`, passes: surface / gap / column fill | Live; pack L0 compose sits on this |
| Relief / grades | `generators/terrain/relief/discover/*` + L2 `GradeFormation`; templates in `relief_templates/` | **Live writer = v2 (R41).** Discover in chunk worker (rim → lockstep W×L → ray seam → paint → one fill). Open_land / road / thin ravine live; shore stub; thick ravine + System emit open; v1 sample/stitch still in tree (not on writer). Product scores: §8.1 |
| Mountains | peak/ridge/saddle/sideFill | Live enough to stamp L0 |
| Hydrology | `HydrologyGeneratorService.apply` | Live generator, used in bake; not “empty stub” |
| Climate | `ClimateOrchestratorService`, runtime assembler | Live math; pack coarse bake; engine `generate_climate` node dead (empty tasks) |
| Roads | `DistrictRoadGenerator` layouts (grid/organic/radial/cul-de-sac/courtyard) | Live inside settlement stack |
| Structure interiors | rooms, passages, staircases (straight/uShape/spiral/ladder) | Deterministic generator live |
| Settlement | `SettlementGeneratorService` → assembler phases A–F | Live layout; organic footprint / z-topology G–H incomplete; ruins/extraction/vastHull assemblers still `NotImplementedError` |
| Barriers | perimeter/cells | Partial |
| Flora / ores / caves | mostly stubs or thin | Not the two-month center of gravity |
| Construction (player build) | TZ | Not in DAG |

**Coordinates (NC-1):** `WORLD_SURFACE_GRID` vs `WORLD_FINE_GRID` vs `LOCATION_FINE_GRID`. Conversion only via `generators/coordinates/convert.py`.

**Skeleton-first:** world create/import writes `NamedLocation` skeleton + footprint occupancy; first entry materializes settlement geometry. Lazy settlement in the DAG still writes some cells via repo; connections + building locations persist through `SettlementPersistService` on master/debug path.

**Three allowed callers of the same library** (`tz_world_generation_dag.md`): (1) Engine DAG — not yet for bake, (2) Debug HTTP — **current**, (3) In-process unit tests — pure helpers, 78 test modules concentrated here.

Template packs: domain roots must not mix. Relief library: `relief_templates/` → SQL `relief_templates`. Buildings: `structures_templates/` (convention; scale when that TZ is touched).

### 8.1 Outdoor relief grade — product axis (2026-08-17)

This is part of **World substrate**, not a second product. Score it as a **discrete-grid grade entity** for an AI GM (one uid, one θ, occupancy). Do **not** score it as Gaea / Unity landscape / erosion art — wrong league.

| Axis | Score | Note |
|---|---|---|
| Live v2 writer (R41 discover) | **7/10** | Architecture of one construction + C41 seam is the win. Completeness and dual-path hygiene hold it off 9. |
| v1 occupancy path (still in repo, not writer) | **4/10** | First-come / peak-seed / road as second ribbon. Dead for bake; delete is layer 7. |
| L2 volume apply (`GradeFormation`) | **~8/10** | Shared, closed; not a second ribbon planner. Do not fork. |
| Vs public discrete-grid grade models | **~8/10** | Distinctive: occupancy + ray seam + plugin body + face catalog vs discover. Weak: 1D extrusion across W, diag W=1. |
| Vs landscape / erosion tools | **N/A** | Wrong product class. |
| Grade facts on a player turn | **3/10** | Same hole as the rest of the generator: entity exists; `terrain_summary` still emits biome keys; `scene_narration` gated. |
| Master authoring of grade | **8/10** | Templates + pick + seeded bake. No editor UI. |

**World substrate overall stays 8/10.** Relief is why that 8 is not a 6; it is not a 9 until shore/System/v1 cut **and** the turn reads pack Grade.

Visual scorecard (same numbers): Cursor canvas `generator-ai-game-eval.canvas.tsx`. Impl vs v1 (engineering, not product): `relief-v1-vs-v2-impl.canvas.tsx`. Spec: `docs/tz_terrain_relief.md` R41.

---

## 9. JSON validation and authoring

`application/jsonValidation/` — POJO-first v1. `resolve` policy: import **strict → 422**, runtime **warn-only**.

`worldSlices.py` is the registry of `worlds` master-data slices (climate scalars, terrain scalars, hydrology blob, relief templates/policy/obstacles/canals, materials, tiers, climate zones, weather, location types, city sizes, moods, district templates, building/barrier/room templates, connection types, road settings, lore, terrain masks, terrain categories, …). Adding a world field = POJO + SQL column + slice row; not a new default table in a generator.

Gaps vs TZ: bundle races / perks / locations not fully in JV; world editor UI is a placeholder route.

---

## 10. Frontend (player shell)

Routes: `/` sessions → `/new` world → `/new/:worldId` character → `/chat/:sessionId` SSE chat. `/settings/backend` LLM. `/settings/world` **placeholder**.

~879 lines. Can: list sessions, pick world/character, stream node status / thinking / result, cancel. Cannot: world editor, map as a product UI, master registries.

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
| 3-phase compiled DAG + temp-batched LLM | **Runtime, distinctive** | Unusual vs 2-node LangGraph |
| Error-code repair DSL | Mechanism yes, files thin | Schema retry common; this patch map is not |
| SSE node telemetry + cancel/resume | Runtime | Lunar streams prose; job-like cancel is rarer |
| `dataModel` + N+1 + system/display | Runtime in data layer | MnesOS public_state vs system_notes |
| Generator library + pack bake | **Large runtime** | Almost no 2026 AI-RPG peer; closer to DF/Civ + cook jobs |
| Outdoor Grade as discrete entity (R41) | **Live writer** (7/10 impl; ~8 vs discrete-grid peers) | Almost no AI-RPG peer; **not** Gaea/landscape. Consumption on turn still 3/10 |
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

| Loop | Status 2026-08-15 |
|---|---|
| Dev stack, session CRUD, chat SSE, cancel/resume skeleton | Yes |
| World/character JSON import (partial JV) | Yes |
| Intent LLM + repair | Yes |
| Scene gate (init / pick start location) | Yes |
| Pack **light/full/detailed bake** via debug HTTP | Yes, with caveats in §7.3 |
| Entry/chunk refine via debug HTTP | Yes |
| ASCII/grid pack render (master/debug) | Yes |
| Hydrology as generator inside bake | Yes (not empty) |
| Relief grades / detailed grade path | **Live v2 writer** in `detailed_bake` / entry refine (discover in worker). Shore stub; System not emitted; v1 sample still in repo. Scores §8.1 |
| Terrain context into `shared_context` on scene tasks | Yes, if those tasks run |
| **Player narration turn** | **No** — no `scene_narration` node (conscious) |
| Bake called from DAG / session start | **No** — gate |
| LLM reads pack L0 as facts | **No** |
| World editor | Placeholder |
| Most TaskTypes | Enum only |
| Engine/DAG automated tests | Almost none |
| Interior furnishing | Not started |
| Multiplayer executor | Spec only |

---

## 13. Framework holes (for a harsh reviewer)

1. **Apply ≠ world commit.** The validation-first thesis is incomplete until one applier owns canonical mutation (pack patches / SQL), including authority (ID-8).
2. **`llm` phase has no Director/Narrator split.** Temperature groups exist; both live LLM nodes are the intent path.
3. **`shared_context: dict`.** Typed domain contexts are specified, not on `ExecutionState`.
4. **EventBus is SSE.** Cannot carry witness / essential NPC / lazy sim without a second bus.
5. **Registered ≠ live.** Empty `supported_tasks` on climate generate nodes; repair DSL map has missing files.
6. **Scene facts vs pack.** Terrain DAG nodes and pack bake can drift until the player path reads the same L0 the bake wrote.
7. **Test pyramid inverted relative to the GM thesis.** 9k lines of tests sit on generators/pack; the DAG/repair/replan machine is almost untested.

---

## 14. Suggested verdict shape (for the evaluating model)

A fair summary, not a scorecard you must copy:

- **Thesis quality:** rare in 2026 AI RPG (validation-first + geometric substrate). Internally consistent in docs and in layer rules.
- **Engine:** a real compiled runtime (ahead of typical LangGraph-RPG toys) with a thin **content** graph (only intent). Closing the DAG in ~1 month bought the machine, not the GM.
- **World:** two months bought an actual bake/refine/pack compiler, currently driven by debug HTTP. That is a world-compiler product, not a stub.
- **Outdoor grade:** live R41 writer is a real differentiator vs 2026 AI-RPG peers (~8 in the discrete-grid grade league, live implementation 7/10). Do not grade it as a landscape tool. It does not yet feed the GM turn (same 3/10 consumption hole).
- **Risk:** Foundry + AI-GM + procedural world is studio-sized. The bet pays only if session start consumes the pack the bake already produces, and if PDVA Apply eventually owns world commits. Further years of bake without those two closures yield a strong world compiler with an unused GM machine — or a GM schema the world never feeds.

**Conscious nos to respect:** no LLM geometry, no RAG-as-memory, no LLM-per-ambient-NPC, no interim `scene_narration` until the scene contract is stable, no agent-wired DAG nodes until owner lifts the gate.

---

## 15. Primary files for a reviewer who will open the repo

| Path | Why |
|---|---|
| `docs/tz_engine_flow.md` | Pass loop, repair, invariants |
| `docs/tz_world_pack_storage.md` | Pack + LOD + UX SLOs |
| `docs/tz_terrain_relief.md` | Outdoor grade SoT (R41 discover); product scores in this brief §8.1 |
| `docs/tz_world_generation_dag.md` | Library vs callers, DAG gate |
| `docs/tz_ideas.md` | Idea registry + analog list |
| `docs/tz_project_snapshot.md` | Older living snapshot (Jul 20) |
| `backend/app/application/engine/llmExecutionEngine.py` | Outer loop |
| `backend/app/application/engine/graphs/graphCompiler.py` | Compile |
| `backend/app/application/engine/repair/patchApplier.py` | Apply (state only) |
| `backend/app/api/routes/map.py` | Debug bake harness contract |
| `backend/app/application/worldData/pack/bake/packMaterializationOrchestrator.py` | L0 bake job |
| `backend/app/dataModel/` | Contract SoT |

---

*End of brief. Compiled 2026-08-15 from repository state (HEAD `450c0f5`). §8.1 relief scores added 2026-08-17 from live v2 writer (uncommitted discover path in the working tree).*
