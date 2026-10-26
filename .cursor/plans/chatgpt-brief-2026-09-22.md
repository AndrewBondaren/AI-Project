# AI RPG Platform — short brief for ChatGPT

**Date:** 2026-09-22 · HEAD `6539b42` · ~340 commits · ~4.4 months · one author  
**Full scorecard:** `.cursor/plans/project-characterization-2026-09-22.md`  
**Full handoff:** `.cursor/plans/llm-project-description-2026-09-22.md`

You are reviewing / helping with an **AI RPG simulation platform**, not a chat frontend with a lorebook.

---

## Product in one paragraph

Master authors world rules (JSON registries, terrain, buildings). Engine + geometry are **source of truth** (SQLite + immutable World Pack). LLM is an AI GM that **renders facts**, does not invent cells/uids/`system_*` keys. Analogy: Foundry VTT + AI-GM + DF/Civ-class procedural world. Niche 2026: validation-first GM peers (Orchestrated Reality PDVA, MnesOS, Lunar, LlamaBrain) **plus** a world compiler those peers lack.

| Role | Sees |
|---|---|
| World master | N+1 registries, `system_*`, bake/debug, pack |
| Player | World → character → SSE chat only |

---

## Stack

Python 3.14 / FastAPI / aiosqlite / SSE · React 19 / Vite / Electron · `LLMRouter` (Qwen/OpenAI/Anthropic) · SQLite **one** migration `0001_initial.sql` · Pydantic `dataModel/` = only field/default contract.

**Layers:** `api` = HTTP only · `chat` = turn/pending · `engine` = DAG compile/phase/repair · `worldData` = pack + outdoor orchestrators · `generators/` = pure materialize (no SQL/HTTP/LLM) · persist outside generators.

---

## Two products in one repo (intentional)

1. **World compiler** — pack bake (light/full/detailed), L2 refine, outdoor city on pack, relief grades. **Mass of the repo.** Callers today: debug HTTP (+ bake→topology). Production caller = DAG after gate.
2. **Validation-first GM** — compiled 3-phase DAG (pre_llm / llm / post_llm), temp-batched LLM, repair DSL, SSE cancel. **Machine closed; content graph thin** (intent only). Engine files **unchanged since 2026-08-14**.

Do **not** score “can a player finish a session.” `scene_narration` is a **conscious blocker**.

---

## What is live (honest)

| Area | Status |
|---|---|
| Session CRUD, SSE chat, intent LLM + repair, scene gates | Yes |
| Pack light/full/detailed bake, entry refine (debug HTTP) | Yes |
| Relief grade v2 writer (discrete Grade entity, 8 pack slots) | **8/10** generate; **R41-T-25** occupancy open; **3/10** on player turn |
| Outdoor city: C23 topology + C24 packing → pack `settlement.zst` + SQL tree | **8/10** orchestrator |
| C22 district packing (lattice→pass1→grid frame→pass2→frontage) | **7/10** live; **grid streets only** |
| BuildingPurpose family→leaf + `purpose_packs` | Closed |
| Player narration / LLM reads pack L0·Grade·city as facts | **No** |
| Bake/outdoor from DAG / session start | **No** (gate) |
| World editor UI | Placeholder |
| Most TaskTypes | Enum only |
| Engine/DAG tests | Almost none (~22k tests on generators/pack/city) |

**Code mass (approx.):** generators 28k · docs 25k · tests 22k · dataModel 12k · pack 11k · engine **2.9k frozen** · frontend 1.6k · chat 96.

---

## Framework holes (score these)

1. `PatchApplier` = state-merge only — **does not commit** SQLite/pack (PDVA Apply incomplete).
2. Three writers for scene-shaped facts: DAG `map_cells`, pack L0/L2/Grade, outdoor city-structure — player path still reads the first.
3. EventBus = per-request SSE, not a world bus.
4. `shared_context` still untyped `dict`.
5. Compiler grew; GM consumer did not — bet is lopsided on purpose (DAG gate).

---

## Agent / helper rules (if you edit this repo)

- Code only if owner explicitly says implement/fix.
- Do **not** touch `application/engine/nodes/` until owner lifts gate.
- Do **not** propose interim `scene_narration` / player vertical slice by default.
- No LLM geometry, no RAG-as-primary-memory, no LLM-per-ambient-NPC.
- Non-grid street layouts = intentional v1 cut.
- Purpose tree ≠ purpose pack (packs are world masks over known leaves).
- Do not start the backend yourself.

**City hole queue (not product SoT):** `.cursor/plans/city-generation-remaining-holes.md` — walls, footprint-by-subtype, dual persist; packing/purpose closed.

---

## Fair verdict shape

Rare 2026 thesis (validation-first + geometric substrate). Engine is a real compiled runtime with almost no content. World side is a real compiler (bake + grade + packed outdoor city), still debug-HTTP-driven. Strongest risk: more months of compiler without session start **consuming** the pack bake already produces.
