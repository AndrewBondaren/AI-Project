# AI RPG Platform — unified brief for ChatGPT

**Date:** 2026-09-22 · HEAD `6539b42` · ~340 commits · ~4.4 months · one author  
**Repo role for you:** external reviewer / co-thinker. Prefer product thesis over “ship a playable vertical slice.”

Longer artifacts in-repo (if you later open the codebase):  
`.cursor/plans/project-characterization-2026-09-22.md` (scorecard) ·  
`.cursor/plans/llm-project-description-2026-09-22.md` (full handoff).

---

## 1. Product vision (what it is meant to be)

**One sentence.** A platform where the **world master encodes rules and a geometric world**, the **engine simulates and validates**, and an **LLM runs the player as GM strictly from world facts** — Foundry VTT + AI-GM + DF/Civ-class procedural substrate — **not** a lorebook chat.

### Two audiences

| Role | Target experience |
|---|---|
| **World master** | Authors/imports a preset: stats, formulas, registries, terrain/climate, building templates, purpose packs, races, states/factions. Offline **bakes** an immutable World Pack. Later: same validator in a **world editor UI**. Ships a cartridge the player just loads. |
| **Player** | Pick world → character → chat. Never sees N+1, DAG, `system_*`, bake. Sees prose, turn telemetry, start-location pick — a session with a GM, not a sim IDE. |

N+1 / `system_*` / `display_*` are **master tools**. Do not simplify the engine for player UX.

### Truth model (target)

```
Master rules + geometry (engine SoT)
        ↓
simulation / validation / commit
        ↓
information layers (who knows what)
        ↓
perception filter (senses / channel)
        ↓
LLM: propose structured events + prose (observation) — never invent cells/uids
```

Target turn pipeline name: **Plan → Diff → Validate → Apply** with Apply **committing** to canonical world state (SQLite patches / pack deltas), not only merging into turn memory.

**Living world** = simulation + validation first; LLM is creative **presentation**, not the world database.

### Target player feel

1. Preset loads fast (pack attach — not millions of OLTP INSERTs).
2. First AI-GM reply from spawn **≤ ~30 s p95**; no blocking “world gen 45%” on the gameplay path.
3. While fine chunks are missing: narration/mechanics use **L0 + L1 + patches**, not wait for full L2.
4. Entering city/building **materializes** geometry from library + pack city layer; LLM describes only what exists.
5. Long campaign: world continues (lazy sim, witness, plot-lock, beliefs) — not a fresh hallucination each chat.

### Target master feel

1. Custom rule systems (not one hard-coded TTRPG).
2. World as registries + templates + bake jobs (light/full/detailed, outdoor city layer, discrete relief **Grade**).
3. Authored city etalon lives in pack; player changes go to **Patch Store**.
4. One validator for JSON import and future editor UI.
5. Publish preset with smoke gate (cartridge idea).

### Conscious product “nos”

- No LLM-generated geometry.
- No RAG as primary world memory.
- No LLM on every ambient NPC / AgentCity.
- No interim player narration slice until scene reads the pack contract.
- Player never gets registry editor “for convenience.”
- Debug HTTP bake is a **harness**; production callers are engine/DAG after gate lift.

### Niche (what we are not)

| Class | Why not us |
|---|---|
| SillyTavern / AI Dungeon | Model *is* the world |
| Inworld / NPC overlay | LLM = character inside someone else’s game |
| Pure LangGraph Director/Narrator | No DF/Civ world compiler |
| Gaea / Cities: Skylines | We bake substrate for an AI GM, not landscape art or a city-builder UI |

**Uniqueness:** geometric procedural substrate + validation-first LLM GM + world presets in one platform.

---

## 2. Product layers beyond “chat + map” (vision)

These belong to the product even when still mostly TZ / draft. Do not treat them as afterthoughts to geometry.

### 2.1 Information as its own engine layer

Canonical geometry/state is **not** the same as “what an agent knows.”

| Layer | Owner | Example |
|---|---|---|
| **Facts** | Engine (DB / pack / patches) | City is besieged; player is in the tavern |
| **Beliefs** | NPC / location aggregates | Innkeeper *thinks* the army is twice as large |
| **Witness / rumors** | Deterministic propagation | Who saw/heard what; distortion by distance, faction bias |
| **Perception** | Engine filter nodes | Sight / hearing / camera / magic — geometric slice for LLM |
| **Presentation** | LLM narrator | Prose from perception + beliefs of the speaker |
| **Event graph (lazy disclosure)** | Engine + LLM expand | Compact hashed plot nodes; expand on demand — not RAG |

Rules of thumb:

- Free LLM must **not** write Facts or invent wars into canon.
- Rumors write **beliefs**, not ground truth.
- Authority hierarchy (target): designer/preset > world_state > episodic > beliefs.
- Perception closes the gap “what exists” vs “what the GM claims exists.”

### 2.2 Economy (draft vision)

- Trade routes **sit on** the existing road/connection graph — they do not fork a second geography.
- Pathfinding weights: route length + danger.
- New trade need may **request** a new road edge via the same world-route generate path as city TZ.
- Full economy sim (markets, prices, production chains) is **product intent**, still a draft TZ (`tz_economy.md`) — not the current implementation center of gravity.

### 2.3 Politics / factions / states

- **States** = world **entities** (polity / territory) in the world bundle — politics of *this* world, not a library template.
- **Factions** influence location influence, essential-NPC triggers (`faction_influence_shift`), rumor bias, narrative loyalty fields (`faction_context`).
- Far LOD sim aggregates into settlement/faction/region indicators (war, treaty, economic crisis as location_states) — not per-peasant ticks.
- Not “Civilization as the core game loop” in v1; politics is a **sim + narrative substrate** the GM reads and patches.

### 2.4 Races

- **Race contract** is its own subsystem (table `races` / bundle section), **not** a casual N+1 vocabulary on `worlds`.
- Master authors races: appearance stack, gender blobs, simulation flags, refs.
- Characters bind `system_race` → race contract; display is denormalized UI.
- Product role: filters for appearance + sim + LLM context — authored master content, not procedural fluff.

### 2.5 City-building (what it means here)

**Not** a player city-builder genre product.

It **is**:

- Skeleton-first settlements → procedural/authored **outdoor city substrate** (districts, streets, plots, buildings) baked into pack city-structure.
- Rank (`small`/`medium`/`large`) ≠ morphology (`city`/`village`).
- Building **function** taxonomy: `BuildingPurpose` family→leaf; world enables leaves via `purpose_packs` (pack ≠ tree).
- Later player/master mutations via patches (build, destroy), not “paint zoning in a SimCity UI.”
- Interiors / furniture / NPC spawn in rooms are later layers on the same hierarchy.

### 2.6 Detailed NPCs (thoughts, needs, memory, goals)

Target model (data storage + lazy sim TZ):

| Concern | Product idea |
|---|---|
| **Needs** | `system_current_needs` + `npc_needs_registry.increment_per_tick`; modified by location_states; persist across scenes |
| **Goals** | `system_npc_goal` strategic; drives `system_current_target` with needs + traits |
| **Thoughts about entities** | `npc_thoughts_about` — persistent opinions of specific uids; updated after scenes with that target |
| **Traits / custom fields** | Engine columns + N+1 `npc_fields` categorized (e.g. `faction_context`) |
| **Memory of the world** | Not chat-log RAG: witness paths, beliefs, world_history events, event-graph nodes |
| **LLM use** | **Essential** NPCs only, **per configured event** (siege, linked death, faction shift, …) — background, non-blocking; ambient NPCs never get per-tick LLM |

**LOD sim:** near = full tick; medium = batch aggregate; far = system indicators. Essential NPCs always full tick regardless of distance. Ambient ≠ AgentCity.

---

## 3. Architecture sketch (how the vision is encoded)

**Stack:** Python 3.14, FastAPI, aiosqlite, SSE · React 19 / Vite / Electron · `LLMRouter` (Qwen / OpenAI / Anthropic) · SQLite one migration `0001_initial.sql` · Pydantic `dataModel/` = only field/default contract.

**Layers:**

- `api` — HTTP only  
- `chat` — turn / pending / crash recovery  
- `engine` — DAG compile / phases / repair / replan  
- `worldData` — pack bake, outdoor etalon, persist services  
- `generators/` — pure materialize (no SQL / HTTP / LLM payload)  
- Persist outside generators; bulk SQL via `bulkSql`

**Storage thesis:** immutable **World Pack** (L0/L2/grades/city-structure) + **Patch Store** + SQL for sessions/names/graph. `map_cells` OLTP is not the cold-load end state.

**Two products in one repo (intentional):** (1) world compiler, (2) validation-first GM. They meet when **session start consumes the pack** the bake already produces.

---

## 4. What exists today vs gated (honest status, 2026-09-22)

Score “thesis + engineering density,” **not** “can a player finish an adventure.”

### Live / strong

| Area | Status |
|---|---|
| Session CRUD, SSE chat, intent LLM + repair, scene gates | Yes |
| Compiled 3-phase DAG runtime (pre_llm / llm / post_llm), temp-batched LLM | Yes — **content graph thin** (intent path only) |
| Pack light/full/detailed bake + entry refine | Yes via **debug HTTP** |
| Relief Grade v2 writer (discrete entity, 8 pack slots) | **~8/10** generate; **R41-T-25** occupancy open |
| Outdoor city: C23 topology + C24 packing → pack + SQL tree | **~8/10** orchestrator |
| C22 district packing (lattice→pass1→grid frame→pass2→frontage) | **~7/10**; **grid streets only** |
| BuildingPurpose + `purpose_packs` | Closed |
| Race ORM / import struct | Partial (contract TZ ahead of full merge/runtime) |

### Explicitly not done / gated

| Area | Status |
|---|---|
| Player narration (`scene_narration` node) | **Conscious blocker** |
| LLM reads pack L0 / Grade / city-structure as scene facts | No (~2–3/10 consumption) |
| Bake/outdoor called from DAG / session start | No (DAG gate) |
| `PatchApplier` commits world | No — **state-merge only** |
| EventBus as persistent world bus | No — per-request SSE |
| Economy / politics sim / rumor / witness / beliefs runtime | Spec / draft |
| Lazy sim LOD + essential NPC background LLM | Spec |
| Perception filter nodes | Spec |
| World editor UI | Placeholder |
| Most `TaskType` values | Enum only |
| Engine/DAG automated tests | Almost none |

**Code mass (approx.):** generators 28k · docs 25k · tests 22k (compiler-heavy) · dataModel 12k · pack 11k · engine **2.9k frozen since 2026-08-14** · frontend 1.6k · chat 96.

**Framework holes to score harshly:** Apply ≠ commit; three writers for scene-shaped facts (`map_cells` DAG path vs pack vs city-structure) while player path still reads the first; untyped `shared_context`; inverted test pyramid vs GM thesis.

---

## 5. How to evaluate / help

**Do treat as success criteria:** thesis consistency; DAG as real dispatcher; pack bake as real job; generators as multi-caller library; `dataModel` as SoT; coherent split compiler vs GM.

**Do not treat as failure:** missing player narration; missing editor UI; DAG not wired to bake yet; multiplayer spec-only; non-grid streets (intentional v1 cut); economy/NPC info layers still conceptual.

**If editing the repo:** code only when owner says implement; never touch `engine/nodes/` until gate lift; don’t propose interim narration; don’t start the backend yourself.

**Fair verdict shape:** Rare 2026 thesis. Engine machine is real but almost empty of content. World compiler is dense and increasingly worth consuming (bake + grade + packed cities). Largest product risk: more months of compiler without (1) session start reading pack facts and (2) PDVA Apply owning world commits — plus the still-spec social/info/economy substrate that makes a “living” campaign, not just a baked map.

---

## 6. End-state picture (horizon)

Master ships a preset → player is in session in minutes → AI-GM runs a campaign on a **real** baked world (map, grades, cities, interiors as entered) → turn patches **commit** with authority → information layers (witness/beliefs/perception) sit on facts → economy/politics move the far LOD → essential NPCs think with needs/goals/memory without LLM-per-peasant → optional multiplayer on the same substrate.

Compiler and GM are **two halves of one product**. Geometry without consumption is a cook-job. GM without geometric + informational SoT collapses to chat-as-world.

---

*Unified brief compiled 2026-09-22 for paste into ChatGPT. Status numbers supersede older snapshots when they conflict.*
