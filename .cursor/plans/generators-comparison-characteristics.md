# Generators — characteristics for cross-project comparison

**Role:** agent memory / comparison rubric (not product TZ, not impl checklist).  
**Created:** 2026-08-09 · deep passes ✅ · peer matrix §7 ✅.  
**Use:** when comparing AI Project world/settlement generation to other games/engines.

How to use: §0–§5 = AP baseline axes; §7 = tech reference (not competitors); **§7A = AI-native competitors**; §10 = done/planned maturity. Prefer capabilities and contracts, not folder names.

**Pass status**

| Domain | Pass depth | Last updated |
|---|---|---|
| Terrain skeleton + pack L0/L2 | **deep** | 2026-08-09 |
| Hydrology | **deep** | 2026-08-09 |
| Climate | **deep** | 2026-08-09 |
| Mountains + Relief grade | **deep** | 2026-08-09 |
| Settlement | **deep** | 2026-08-09 |
| Road / Barrier | **deep** | 2026-08-09 |
| Structure | **deep** | 2026-08-09 |

---

## 0. Meta posture (platform, not “a game”)

| # | Characteristic | AI Project (baseline) |
|---|---|---|
| M1 | Dual audience: world master vs player | Yes — master owns registries/N+1; player sees materialised world only |
| M2 | Master declares rules/data; engine materialises | Yes — JSON/registries + generators; not player tile-designation |
| M3 | LLM / AI-GM consumes only known facts | Yes — skeleton-first; no inventing missing geometry for narration |
| M4 | Generators are a pure library (multi-caller) | Yes — same API for debug HTTP, future DAG, in-process; no SQL in generators |
| M5 | Persist / “when to run” separated from generate | Yes — orchestrators + MapCell*/Persist services; DAG gated |
| M6 | Semantic-first knobs (intent → registries) | Yes — e.g. `economic_tier` expands to materials/roads/templates |
| M7 | N+1 / system_* extensibility for masters | Yes — dataModel POJO + world registries |
| M8 | Not full physics sim as generation SoT | Yes — carve/mask/layout; flow/season/weather runtime mostly separate |

---

## 1. World surface / wilderness

| # | Characteristic | AI Project |
|---|---|---|
| W1 | Explicit world bounds / anchor-driven extent | Yes — AABB / anchors±padding; rectangular world contract |
| W2 | Multi-pass height / column skeleton | Yes — coarse surface → gap (`N_eff`) → solid columns |
| W3 | Declared relief objects before water | Yes — Pass 1.4 mountain/ravine z before hydrology |
| W4 | Hydrology carves real lows (not only paint water) | Yes — Pass 1.5 lowers `surface_z` + roles (pack planning path) |
| W5 | Sea / ocean / lake / river as metadata on one liquid type | Yes — `liquid_body` + hydrology roles |
| W6 | Declare + autoresolve water features | Yes — empty declare ≠ off if enabled |
| W7 | Climate independent of terrain shape ownership | Yes — climate writes temp/rain/(liquid phase); terrain owns solid shape |
| W8 | Climate poles / anchors (not elevation→biome alone) | Yes — poles set zones; z = lapse only |
| W9 | Layered climate: eager map vs runtime weather | Partial — eager+pack ✅; runtime weather pick stub; SurfaceClimateField/LOD open |
| W10 | Coarse→fine / LOD materialisation (pack light → refine) | Yes — L0 parent light + L2 fine; **product SoT = pack**, not map_cells bake |
| W11 | Mask / contributor compose order (ranked paint) | Yes — relief→climate→landcover→mountain→ravine→hydro→open_land→shore→settlement→road→road_shoulder |
| W12 | Mountain topology (ranges, saddles, MST-like) | Yes core — PassBuilder+U6 shipped; U4–U5/U7–U10 polish open |
| W13 | Slope/sheer grade as first-class (not fake terrain key) | Yes Waves A–D; Wave E (8-way, junction, gameplay) open |
| W19 | `ReliefContributor` = grade | **No** — it stamps base `surface_z` only; grade = open_land/shore/road_shoulder (+ mountain sides) |
| W14 | Ores / caves as full domains | Stub — markers only |
| W15 | Magma / deep geology gameplay | Partial — band on skeleton; movement resolver M-3 open |
| W16 | Deterministic seed contract | Yes — world_seed + pass identity family |
| W17 | Parallel chunk generate, serial persist | Yes on L2 refine pool; DAG `free_cores` wiring open |
| W18 | Legacy `generate_surface` ≡ product bake | **No** — facade skips 1.4/hydro; product = pack bake + refine |

---

## 2. Settlement / city

| # | Characteristic | AI Project |
|---|---|---|
| C1 | Skeleton-first settlements | Yes |
| C2 | Lazy outdoor materialisation on entry | Partial — debug persist full; `lazy_settlement` = map cells only |
| C3 | Hierarchical assemblers (city → district → lot → building) | Yes |
| C4 | District templates + placement conditions | Yes (core) |
| C5 | Generate-first building cache then place | Yes |
| C6 | City-level street graph + district roads | Partial — city + district **grid** |
| C7 | Multiple street morphology (organic, radial, …) | No — NotImplemented |
| C8 | Settlement walls / gates | Yes — optional heuristic walls |
| C9 | Parcel fences / yard model | Partial — fence yes; yard/small buildings thin; NC-2 parcel≠cells |
| C10 | Dominant material derived post-layout | Yes |
| C11 | Architectural style drives geometry | No — LLM metadata only |
| C12 | Organic / non-square city footprint | No — Phase G open |
| C13 | Multi-z settlement topology | Spec’d; Phase H open |
| C14 | Idempotent outdoor persist scopes | Yes in **service** + debug HTTP; prod lazy uneven |
| C15 | Settlement growth / regen over time | Open — no growth services |
| C16 | Location type vocabulary (`settlement` vs `city`/`town`) | Mismatch — debug route requires `"settlement"`; fixtures use city/town |

---

## 3. Buildings / interiors

| # | Characteristic | AI Project |
|---|---|---|
| B1 | Template-driven multi-level interiors | Yes — happy path tavern-like |
| B2 | Deterministic per-building seed | Yes |
| B3 | Shared walls / adjacency layout | Yes — mode A+B |
| B4 | Door / arch / entry passage rules | Yes |
| B5 | Corridor trim + connect post-pass | Yes — order ≠ TZ (connect after passages) |
| B6 | Staircase variety | Partial — u_shape + ladders; straight/spiral/embedded NotImplemented |
| B7 | Foundation + roof shell | Partial — slab/perimeter/full/hull + flat/gable/hull; stilts/auto/hip open |
| B8 | Multiple structure assemblers | Only `building` live; ruins/hull/extraction stubs |
| B9 | Furniture / interior props | No |
| B10 | Building↔building bridges / balconies | Out of v1 |
| B11 | Player construction / repair | Placeholder TZ |
| B12 | Mobile structures via same assembler | Contract only |
| B13 | Master `validate_template` quality gate | Stub returns `[]` |
| B14 | Porch / entrance_steps / access_type | Context fields only — not generated |

---

## 4. Graphs / movement / barriers

| # | Characteristic | AI Project |
|---|---|---|
| G1 | Typed connection graph (city / district / world) | Partial — city+district generate; world routes draft; area graph missing |
| G2 | Road width / sidewalk / travel from tier | Partial — resolvers ✅; sidewalk **edges** ❌ (flag only) |
| G3 | World trade / long-haul routes | No — deferred |
| G4 | Shared barrier primitive | Yes — `generators/barrier/` + settlement/area planners |
| G5 | Relief-linked fences (ribbon grade) | Yes — BAR-1 after light compose |
| G6 | Hydrology→navigation | Partial — hydro emit stub |
| G7 | District street morphologies beyond grid | No |
| G8 | Pack road paint separate from urban graph gen | Yes — `RoadContributor` does not import `generators/road` |

---

## 5. Data / authority / tooling

| # | Characteristic | AI Project |
|---|---|---|
| D1 | Single POJO / dataModel as field SoT | Yes — anti-hardcode rule across layers |
| D2 | JSON import validator = future editor rules | Target — JV + world row; master UI later |
| D3 | Template packs on disk → SQL library | Yes (relief SoT; buildings same convention to scale) |
| D4 | World pack storage vs millions of map_cells | Yes — **product wilderness = pack** bake path |
| D5 | Debug HTTP / scripts as first-class harness | Yes — `pack/bake`, `refine-from-entry`; legacy `generate-surface` **removed** |
| D6 | Production engine DAG as only runtime caller | Target — blocked by explicit gate |
| D7 | Domain tech-debt registry separate from TZ | Yes — `tz_generator_technical_debt.md` |

---

## 6. Explicit non-goals / anti-characteristics

| # | Anti-characteristic (peer may have) | AI Project stance |
|---|---|---|
| X1 | Player digs/designates every tile as generation UX | No — actions → node → generator slice (planned) |
| X2 | Earth-like elevation automatically picks climate zone | No — poles/anchors own zone |
| X3 | Water = `z ≤ 0` only | Rejected — carve + `liquid_candidate` |
| X4 | Generators call LLM or build chat payload | Forbidden layer boundary |
| X5 | One god-orchestrator mixing terrain+city+LLM | Split domains + thin callers |
| X6 | Full erosion / fluid sim as bootstrap SoT | Out of scope for Pass 1.5 |
| X7 | Style string directly paints meshes | Style ≠ geometry yet (and may stay semantic) |

---

## 7. Peer comparison

**Legend:** Y = has · P = partial / different shape · N = absent or opposite · — = N/A  

**Two audiences in this section:**
- **§7.1–7.9** — *tech / genre reference* (DF, Minecraft, RimWorld, …). **Not market competitors** for AP; used to score generator/capability axes against known systems.
- **§7A** — *AI-native competitors* (AI Dungeon, RoleForge, Hidden Door, …). Product/market comparison for AI RPG / AI-GM platforms.

### 7.0 Tech reference peers (not competitors)

**Peers:** **AP** = AI Project · **DF** = Dwarf Fortress · **MC** = Minecraft · **RW** = RimWorld · **NMS** = No Man’s Sky · **VH** = Valheim · **FV** = Foundry VTT · **PCG** = Unreal PCG / Houdini-class · **WT** = Watabou / city-layout tools  

Closest-domain hint under each table. Scores are capability/contract comparison, not “who is better”.

### 7.1 Meta posture (M)

| # | Characteristic | AP | DF | MC | RW | NMS | VH | FV | PCG | WT |
|---|---|---|---|---|---|---|---|---|---|---|
| M1 | Dual audience: world master vs player | Y | P | P | P | N | N | Y | Y | Y |
| M2 | Master declares rules; engine materialises | Y | Y | P | P | P | N | P | Y | Y |
| M3 | AI/LLM consumes only known facts | Y | — | — | — | — | — | — | — | — |
| M4 | Generators as pure multi-caller library | Y | N | N | N | N | N | — | Y | P |
| M5 | Persist / when-to-run ≠ generate | Y | Y | Y | Y | Y | Y | — | Y | P |
| M6 | Semantic-first knobs → registries | Y | P | N | P | N | N | P | P | N |
| M7 | N+1 / data-driven extensibility | Y | Y | P | Y | P | N | Y | Y | P |
| M8 | Gen SoT ≠ full fluid/erosion sim | Y | N | Y | Y | Y | Y | — | P | Y |

**Closest match:** DF/RW on M2+M7 (raws/defs); FV on M1 (GM vs players); PCG on M4 library posture. **AP unique:** M3 AI-GM fact discipline.

### 7.2 World surface / wilderness (W)

| # | Characteristic | AP | DF | MC | RW | NMS | VH | FV | PCG | WT |
|---|---|---|---|---|---|---|---|---|---|---|
| W1 | Explicit bounds / anchor-driven extent | Y | Y | P | Y | P | P | — | Y | Y |
| W2 | Multi-pass height / column skeleton | Y | Y | P | P | P | P | — | Y | N |
| W3 | Relief objects before water pass | Y | Y | N | N | N | N | — | P | — |
| W4 | Hydrology carves real lows | Y | Y | P | P | P | P | — | P | N |
| W5 | One liquid type + role metadata | Y | P | N | N | N | N | — | P | — |
| W6 | Declare + autoresolve water | Y | P | N | N | N | N | — | P | N |
| W7 | Climate ownership ≠ terrain shape | Y | P | N | P | P | N | — | P | — |
| W8 | Poles/anchors (not elev→biome alone) | Y | P | N | N | N | N | — | P | — |
| W9 | Eager climate map vs runtime weather | P | Y | P | Y | Y | P | — | P | — |
| W10 | Coarse→fine / LOD materialise | Y | P | Y | N | Y | P | — | Y | N |
| W11 | Ranked mask/contributor compose | Y | N | N | N | N | N | — | Y | N |
| W12 | Mountain topology (ranges/MST-like) | Y | P | N | N | P | N | — | Y | N |
| W13 | First-class slope/sheer grade | Y | P | N | N | N | N | — | Y | N |
| W14 | Full ores / caves domains | N | Y | Y | P | P | P | — | P | N |
| W15 | Magma / deep geology gameplay | P | Y | P | N | N | N | — | P | N |
| W16 | Deterministic seed contract | Y | Y | Y | Y | P | Y | — | Y | Y |
| W17 | Parallel chunk gen, serial persist | Y | P | Y | N | Y | P | — | Y | — |
| W18 | Legacy facade ≠ product bake path | Y* | — | — | — | — | — | — | P | — |

\*AP: characteristic = *aware split* (pack SoT vs old facade) — peers usually one pipeline.

**Closest match:** DF on geological depth (W2–W4, W14–W15); MC/NMS on LOD/chunk (W10, W17); PCG on compose/masks (W11–W13). **AP gap vs DF/MC:** ores/caves. **AP strength:** poles≠biome, grade, declare water, ranked compose.

### 7.3 Settlement / city (C)

| # | Characteristic | AP | DF | MC | RW | NMS | VH | FV | PCG | WT |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Skeleton-first settlements | Y | Y | N | P | N | N | — | P | P |
| C2 | Lazy outdoor on entry | P | Y | Y | Y | Y | Y | — | P | N |
| C3 | City→district→lot→building hierarchy | Y | P | N | N | N | N | — | Y | P |
| C4 | District templates + placement rules | Y | P | N | P | N | N | — | Y | P |
| C5 | Generate-first building then place | Y | P | N | N | N | N | — | Y | N |
| C6 | City + district street graphs | P | P | N | N | N | N | — | Y | Y |
| C7 | Multiple street morphologies | N | P | N | N | N | N | — | Y | Y |
| C8 | Settlement walls / gates | Y | Y | N | P | N | N | — | Y | Y |
| C9 | Parcel fences / yard model | P | P | N | P | N | N | — | Y | P |
| C10 | Dominant material post-layout | Y | N | N | N | N | N | — | P | N |
| C11 | Architectural style → geometry | N | P | N | N | N | N | — | Y | P |
| C12 | Organic / non-square footprint | N | Y | N | P | N | N | — | Y | Y |
| C13 | Multi-z settlement topology | N | Y | P | N | N | N | — | Y | N |
| C14 | Idempotent outdoor persist scopes | Y | P | Y | Y | Y | Y | — | P | N |
| C15 | Settlement growth over time | N | Y | N | Y | N | N | — | P | N |

**Closest match:** WT/PCG on street morphology (C6–C7, C12); DF on sites + growth (C1, C12–C13, C15); RW on colony growth not city templates. **AP strength:** explicit assembler hierarchy + generate-first cache. **AP gap:** organic streets/footprint, growth.

### 7.4 Buildings / interiors (B)

| # | Characteristic | AP | DF | MC | RW | NMS | VH | FV | PCG | WT |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | Template multi-level interiors | Y | P | P | P | N | N | — | Y | N |
| B2 | Deterministic per-building seed | Y | Y | Y | Y | — | — | — | Y | Y |
| B3 | Shared-wall adjacency layout | Y | P | N | N | N | N | — | Y | N |
| B4 | Door / arch / entry rules | Y | Y | P | P | N | N | — | Y | N |
| B5 | Corridor trim + connect | Y | P | N | N | N | N | — | P | N |
| B6 | Staircase variety | P | Y | P | N | N | N | — | Y | N |
| B7 | Foundation + roof shell | P | P | P | N | N | N | — | Y | N |
| B8 | Multiple structure assemblers | N | Y | P | P | N | N | — | Y | N |
| B9 | Furniture / interior props | N | Y | P | Y | N | N | — | P | N |
| B10 | Building↔building bridges | N | Y | P | N | N | N | — | P | N |
| B11 | Player construction / repair | N | Y | Y | Y | N | Y | — | — | N |
| B12 | Mobile structures same pipeline | N | P | N | N | N | N | — | P | N |
| B13 | Master template validation gate | N | P | N | P | N | N | — | Y | N |
| B14 | Porch / entrance access types | N | P | N | N | N | N | — | P | N |

**Closest match:** DF on fort interiors + stairs + furniture (B6, B9–B11); PCG on authored multi-level templates (B1, B3). **AP strength:** template room graph + corridor post-pass. **AP gap:** furniture, player build, stair variety, validate_template.

### 7.5 Graphs / barriers (G)

| # | Characteristic | AP | DF | MC | RW | NMS | VH | FV | PCG | WT |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | Typed connection graph levels | P | P | N | P | N | N | — | Y | Y |
| G2 | Width / sidewalk / travel policy | P | N | N | N | N | N | — | Y | P |
| G3 | World trade / long-haul routes | N | Y | N | Y | N | N | — | P | N |
| G4 | Shared barrier primitive | Y | Y | P | P | N | P | — | Y | P |
| G5 | Relief-linked fences | Y | N | N | N | N | N | — | P | N |
| G6 | Hydro → navigation | P | Y | P | N | P | P | — | P | N |
| G7 | Non-grid street morphologies | N | P | N | N | N | N | — | Y | Y |
| G8 | Pack/road paint ≠ urban graph gen | Y | — | Y* | — | Y* | — | — | Y | N |

\*MC/NMS: world roads/paths often separate from “city street gen” (weak cities).

**Closest match:** WT/PCG streets; DF/RW caravans (G3); DF hydro travel. **AP unique-ish:** G5 ribbon grade fences + G8 pack paint split.

### 7.6 Data / tooling (D)

| # | Characteristic | AP | DF | MC | RW | NMS | VH | FV | PCG | WT |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | Single typed data model SoT | Y | P | N | P | N | N | P | P | N |
| D2 | Import validator = future editor rules | P | N | N | N | N | N | Y | P | N |
| D3 | Template packs → library | Y | P | P | Y | N | N | Y | Y | P |
| D4 | Coarse pack / streaming vs all cells | Y | P | Y | N | Y | P | — | Y | N |
| D5 | Debug harness first-class | Y | P | P | P | N | N | Y | Y | Y |
| D6 | One production runtime caller (DAG) | P | Y* | Y* | Y* | Y* | Y* | Y | P | N |
| D7 | Separate generator tech-debt registry | Y | N | N | N | N | N | N | N | N |

\*Integrated game loop is “the” caller — not a separate DAG library, but single runtime.

**Closest match:** FV modules/packs (D3, D5); MC/NMS streaming (D4); DF raws (D1 partial). **AP unique:** D7 debt registry + explicit DAG gate.

### 7.7 Anti-characteristics (X) — who *does* the thing AP rejects

| # | Anti (peer may do this) | AP | DF | MC | RW | NMS | VH | Notes |
|---|---|---|---|---|---|---|---|---|
| X1 | Player digs/designates as gen UX | N | Y | Y | Y | N | P | DF/MC/RW core fantasy |
| X2 | Elevation alone picks climate zone | N | P | Y | P | P | P | MC biomes classic |
| X3 | Water ≈ z≤0 / sea level paint | N | N | P | P | P | P | AP/DF carve-aware |
| X4 | Gen builds LLM/chat payload | N | — | — | — | — | — | AP-specific forbid |
| X5 | One god-object gen+LLM+UI | N | P | P | P | P | P | Monoliths common |
| X6 | Erosion/fluid sim as bootstrap SoT | N | Y | N | N | N | N | DF identity |
| X7 | Style string paints meshes directly | N | N | N | N | P | N | Often art-pipeline |

### 7.8 One-line peer summaries

| Peer | Closest to AP | Farthest / contrast |
|---|---|---|
| **DF** | Geological passes, sites, raws extensibility, deep interiors | Dig UX, erosion/fluid identity, no AI-GM layer |
| **MC** | Chunk/LOD, caves/ores, streaming | Elev→biome, weak cities, no master semantic registries |
| **RW** | Defs/modding, colony growth, weather | Map = local parcel not world hierarchy; no city assembler stack |
| **NMS** | Planet LOD / streaming | Thin settlement/interior gen; little master declare |
| **VH** | Hand+proc hybrid, player build | Almost no city/template stack |
| **FV** | Master vs player, modules | **No** world gen — tooling contrast only |
| **PCG/Houdini** | Library generators, masks, city graphs | No RPG/AI-GM runtime; DCC not product |
| **Watabou** | Street morphology, organic cities | No 3D columns, climate, persist, interiors |

### 7.9 Where AP stands vs tech reference (not market pitch)

1. **Platform posture** (M1–M3, M6–M7) — closer to Foundry+moddable DF than to MC/NMS.  
2. **Wilderness tech** — between DF depth and MC/NMS LOD; unusual poles + grade + ranked compose.  
3. **Cities** — stronger *hierarchy/templates* than MC/RW/NMS; weaker *organic morphology/growth* than DF/Watabou.  
4. **Interiors** — stronger authored template graph than most open-world games; weaker than DF fort + furniture + player dig.  
5. Market pitch → **§7A** (AI peers), not this subsection.

---

## 7A. AI-native competitors (market)

**Scope:** products that sell AI GM / AI RPG / persistent AI world — *not* classic proc-gen games.  
Scores use the **same characteristic IDs** (M/W/C/B/G/D/X) so AP can be compared without mixing DF/MC into the competitor set.

**Peers:**  
**AP** = AI Project · **AID** = AI Dungeon · **HD** = Hidden Door · **RF** = RoleForge · **AE** = Aether Engine · **WA** = wilds.ai · **WL** = WorldLines · **AQ** = ArcQuill · **ST** = SillyTavern (+ lorebook/card stack) · **IW** = Inworld (NPC platform)

*Caveat:* public marketing ≠ audited code. Scores reflect claimed/typical product shape as of 2026-08. Re-score after hands-on.

### 7A.1 Meta posture (M) — where competition is real

| # | Characteristic | AP | AID | HD | RF | AE | WA | WL | AQ | ST | IW |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | Dual audience: world master vs player | Y | P | P | P | P | P | Y | P | Y | P |
| M2 | Master declares rules; engine materialises | Y | P | P | Y | P | P | Y | P | P | P |
| M3 | AI/LLM consumes only known facts | Y | N | P | Y | P | P | P | P | P | P |
| M4 | Generators as pure multi-caller library | Y | N | N | N | N | N | N | N | — | N |
| M5 | Persist / when-to-run ≠ generate | Y | P | Y | Y | Y | Y | Y | Y | P | Y |
| M6 | Semantic-first knobs → registries | Y | N | P | P | P | P | P | P | P | P |
| M7 | N+1 / data-driven extensibility | Y | P | P | P | P | P | Y | P | Y | Y |
| M8 | Gen SoT ≠ full fluid/erosion sim | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |

**Read:** Competitors fight on **M1–M3, M5, M7** (master tools, persistence, “AI doesn’t invent free”). Almost none claim **M4** generator library or **M6** semantic registries like AP. AID is weakest on **M3** (classic invent-anything). RF markets rules engine the AI can’t override → closest **M2/M3** narrative to AP.

### 7A.2 World surface / wilderness (W) — AP differentiator

| # | Characteristic | AP | AID | HD | RF | AE | WA | WL | AQ | ST | IW |
|---|---|---|---|---|---|---|---|---|---|---|---|
| W1 | Explicit bounds / anchor extent | Y | N | P | P | P | P | P | P | N | — |
| W2 | Multi-pass height / column skeleton | Y | N | N | N | N | N | N | N | N | — |
| W3 | Relief before water pass | Y | N | N | N | N | N | N | N | N | — |
| W4 | Hydrology carves real lows | Y | N | N | N | N | N | N | N | N | — |
| W5 | Liquid type + role metadata | Y | N | N | N | N | N | N | N | N | — |
| W6 | Declare + autoresolve water | Y | N | N | N | N | N | N | N | N | — |
| W7 | Climate ownership ≠ terrain shape | Y | N | N | N | N | N | N | N | N | — |
| W8 | Poles/anchors ≠ elev→biome | Y | N | N | N | N | N | N | N | N | — |
| W9 | Eager climate vs runtime weather | P | N | N | N | N | N | N | N | N | — |
| W10 | Coarse→fine / LOD materialise | Y | N | N | P | N | P | N | N | N | — |
| W11 | Ranked mask/contributor compose | Y | N | N | N | N | N | N | N | N | — |
| W12 | Mountain topology | Y | N | N | N | N | N | N | N | N | — |
| W13 | First-class slope/sheer grade | Y | N | N | N | N | N | N | N | N | — |
| W14 | Full ores / caves | N | N | N | N | N | N | N | N | N | — |
| W15 | Magma / deep geology | P | N | N | N | N | N | N | N | N | — |
| W16 | Deterministic seed | Y | N | P | P | P | P | P | P | N | — |
| W17 | Parallel chunk / serial persist | Y | — | — | — | — | — | — | — | — | — |
| W18 | Legacy facade ≠ product bake | Y | — | — | — | — | — | — | — | — | — |

**Read:** On **W2–W13** AP is essentially alone among AI RPG peers — they materialise *narrative/memory worlds*, not voxel/column wilderness pipelines. RF/WA may have *maps* (hand-drawn / soft proc) → **W10 P** at best, not skeleton generators.

### 7A.3 Settlement / city (C)

| # | Characteristic | AP | AID | HD | RF | AE | WA | WL | AQ | ST | IW |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Skeleton-first settlements | Y | N | P | P | P | P | P | P | N | — |
| C2 | Lazy outdoor on entry | P | — | — | P | — | P | — | — | — | — |
| C3 | City→district→lot→building hierarchy | Y | N | N | N | N | N | N | N | N | — |
| C4 | District templates + placement rules | Y | N | N | N | N | N | N | N | N | — |
| C5 | Generate-first building then place | Y | N | N | N | N | N | N | N | N | — |
| C6 | City + district street graphs | P | N | N | N | N | N | N | N | N | — |
| C7 | Multiple street morphologies | N | N | N | N | N | N | N | N | N | — |
| C8 | Settlement walls / gates | Y | N | N | N | N | N | N | N | N | — |
| C9 | Parcel fences / yard | P | N | N | N | N | N | N | N | N | — |
| C10 | Dominant material post-layout | Y | N | N | N | N | N | N | N | N | — |
| C11 | Architectural style → geometry | N | N | N | N | N | N | N | N | N | — |
| C12 | Organic / non-square footprint | N | N | N | N | N | N | N | N | N | — |
| C13 | Multi-z settlement topology | N | N | N | N | N | N | N | N | N | — |
| C14 | Idempotent outdoor persist scopes | Y | P | Y | Y | Y | Y | Y | Y | P | P |
| C15 | Settlement growth over time | N | N | P | P | P | P | Y | P | N | — |

**Read:** Competitors’ “settlement” ≈ **named places + memory/events** (C1/C14/C15 P), not assembler hierarchy. **C3–C10** is AP’s structural moat vs AI peers.

### 7A.4 Buildings / interiors (B)

| # | Characteristic | AP | AID | HD | RF | AE | WA | WL | AQ | ST | IW |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | Template multi-level interiors | Y | N | N | N | N | N | N | N | N | — |
| B2 | Deterministic per-building seed | Y | N | N | N | N | N | N | N | N | — |
| B3 | Shared-wall adjacency layout | Y | N | N | N | N | N | N | N | N | — |
| B4 | Door / arch / entry rules | Y | N | N | N | N | N | N | N | N | — |
| B5 | Corridor trim + connect | Y | N | N | N | N | N | N | N | N | — |
| B6 | Staircase variety | P | N | N | N | N | N | N | N | N | — |
| B7 | Foundation + roof shell | P | N | N | N | N | N | N | N | N | — |
| B8–B14 | Other assemblers / furniture / build / validate / porch | N/P | N | N | N | N | N | N | N | N | — |

**Read:** AI peers describe rooms in prose; AP **materialises cell geometry**. Furniture/player-build (B9/B11) — DF-class, not AI-peer fight (yet).

### 7A.5 Graphs / barriers (G)

| # | Characteristic | AP | AID | HD | RF | AE | WA | WL | AQ | ST | IW |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G1 | Typed connection graph levels | P | N | N | P | N | P | P | N | N | — |
| G2 | Width / sidewalk / travel policy | P | N | N | N | N | N | N | N | N | — |
| G3 | World trade / long-haul routes | N | N | N | N | N | N | P | N | N | — |
| G4 | Shared barrier primitive | Y | N | N | N | N | N | N | N | N | — |
| G5 | Relief-linked fences | Y | N | N | N | N | N | N | N | N | — |
| G6 | Hydro → navigation | P | N | N | N | N | N | N | N | N | — |
| G7 | Non-grid street morphologies | N | N | N | N | N | N | N | N | N | — |
| G8 | Pack road paint ≠ urban graph | Y | — | — | — | — | — | — | — | — | — |

**Read:** RF/WA may have tactical/grid maps → weak **G1 P**; not road/barrier generators.

### 7A.6 Data / tooling (D)

| # | Characteristic | AP | AID | HD | RF | AE | WA | WL | AQ | ST | IW |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | Single typed data model SoT | Y | N | P | P | P | P | P | P | N | P |
| D2 | Import validator = editor rules | P | N | P | P | N | N | P | P | N | P |
| D3 | Template packs → library | Y | P | Y | P | P | P | Y | Y | Y | Y |
| D4 | Coarse pack / streaming vs all cells | Y | N | N | N | N | P | N | N | N | — |
| D5 | Debug harness first-class | Y | N | N | N | N | N | N | N | Y | P |
| D6 | One production runtime caller | P | Y | Y | Y | Y | Y | Y | Y | N | Y |
| D7 | Separate generator tech-debt registry | Y | N | N | N | N | N | N | N | N | N |

**Read:** ST/WL/AQ win on **creator share / cards** (D3). AP wins on **typed world SoT + pack streaming + debt discipline**. Competitors are ahead on **shipped single player runtime** (D6 Y vs AP DAG gate).

### 7A.7 Anti-characteristics (X) among AI peers

| # | Anti (bad for AP posture) | AP | AID | HD | RF | AE | WA | WL | AQ | ST | IW |
|---|---|---|---|---|---|---|---|---|---|---|---|
| X1 | Player digs/designates as gen UX | N | N | N | N | N | N | N | N | N | N |
| X2 | Elevation alone picks climate | N | — | — | — | — | — | — | — | — | — |
| X3 | Water ≈ z≤0 paint | N | — | — | — | — | — | — | — | — | — |
| X4 | Gen builds LLM/chat payload | N | Y* | P | P | P | P | P | P | Y* | P |
| X5 | One god-object gen+LLM+UI | N | Y | Y | Y | Y | Y | P | Y | Y | P |
| X6 | Erosion/fluid as bootstrap SoT | N | N | N | N | N | N | N | N | N | N |
| X7 | Style string paints meshes | N | N | N | N | N | N | N | N | N | N |

\*AID/ST: world “generation” often *is* the LLM turn (or card prompt) — closest to **X4 Y**.

### 7A.8 One-line AI competitor summaries

| Peer | Competes with AP on | Does not compete (AP moat) |
|---|---|---|
| **AI Dungeon** | Solo AI adventure, low friction | Fact discipline, rules engine, any spatial gen |
| **Hidden Door** | Structured AI RPG / Atlas worlds | Column wilderness, city/building assemblers |
| **RoleForge** | AI GM + **rules engine** + maps + persist memory | Procedural terrain/hydro/city/interior pipelines |
| **Aether Engine** | Persistent living world marketing | Same — narrative state, not generators |
| **wilds.ai** | Multi-genre AI games + memory + multiplayer | Voxel/settlement materialize stack |
| **WorldLines** | Creator worlds, agent harness, hub share | Spatial generators; closer on master/fork (M1/M7) |
| **ArcQuill** | Permanent memory DM, world publish | Geometry materialization |
| **SillyTavern** | Local LLM RP, lorebooks, cards (tooling) | Not a world engine; no pack/assemblers |
| **Inworld** | NPC/character AI layer | Not full RPG world gen; integration target not clone |

### 7A.9 Competitive reading (for pitch)

1. **Market fight** = AI GM quality + persistent world state + master/creator tools (**M1–M3, M5, D3, D6**).  
2. **Generator stack (W/C/B/G)** is **not** what AID/HD/RF/AQ sell today → AP’s structural differentiator *if* exposed to master and enforced for LLM (**M3**).  
3. Closest narrative competitors on “rules + memory + maps”: **RoleForge**, then **Hidden Door / ArcQuill / WorldLines**.  
4. Closest on “local/creator extensibility”: **SillyTavern stack**, **WorldLines** hubs — weak on simulation.  
5. Risk: market may not *perceive* W/C/B value until player-visible maps + LLM never contradict cells.  
6. Do **not** put DF/MC/RW in competitor slides; keep them in §7 tech appendix only.

---

## 8. Domain maturity snapshot (updated as deep passes land)

| Domain | Maturity | Done (headline) | Still to do (headline) |
|---|---|---|---|
| Terrain skeleton + pack | **Strong** | L0 compose + L2 parent-light refine; TR-1/PAR/PERF core | DAG wiring; ores/caves; M-3; TR-PAR-4; doc hygiene |
| Hydrology | **Mid–strong** | Pass 1.5 + light Path A + overlay mask | Ocean/DepressionForm; emit; landforms; H-7a route; status sync |
| Climate | **Strong eager/pack · weak runtime** | Pole/tier/weather + pack coarse/fine | Recalc flags; weather pick; LOD field; batch orphaned vs DAG |
| Mountains | **Strong core** | PassBuilder→Specs→paint; U6 | U4–U5/U7–U10; R33 on coarse |
| Relief grade | **Strong A–D** | Templates, ribbons, canal, persist | Wave E; Q4 mountain≠R36 volume |
| Settlement outdoor gen | **Strong A–F** | Skeleton→districts→grid streets→barriers→occupancy | Organic G/H; style→geom; growth |
| Settlement persist/lazy | **Mid** | PersistService + debug full outdoor | Unify `lazy_settlement`; type gate; init_mode |
| Structure building | **Strong interior v1** | u_shape + trim/connect + openings + shell | validate_template; porch; stair variants; other assemblers |
| Road urban | **Mid (grid-only)** | City+district grid + policy helpers + pack paint | Non-grid layouts; sidewalk edges; world routes |
| Barrier | **Mid–strong** | Shared primitives + area/settlement + BAR-1 | NC-3 district walls; NC-4 uid contract; settlement literal emit |

---

## 9. Pointers

- Domain TZ: `docs/tz_*.md` (terrain, hydrology, climate, city, building, assembler_hierarchy, map_light_bake, world_pack_storage, world_generation_dag)
- Debt: `docs/tz_generator_technical_debt.md`
- Code: `backend/app/application/worldData/generators/` + `…/worldData/*Orchestrator*`
- This file is agent comparison SoT; canvas `generators-domain-spec.canvas.tsx` is optional UI (shallow)

---

## 10. Deep pass log — done vs planned

### 10.1 Terrain skeleton + pack L0/L2 *(deep 2026-08-09)*

**Owns:** coarse heightmap, gap/`N_eff`, column fill, pack L0 `ReliefContributor` base z, L2 parent-light upsample + chunk columns, ore/cave stubs, magma band voxels.  
**Does not own:** mountain topology details, relief Wave E semantics, hydro algorithms, climate fields, DAG nodes.

**Product pipeline (actual):**  
`prepare_surface_terrain_context` (pole → coarse → 1.4 → 1.5 → meter rivers) → pack L0 `compose_light_grid` (contributor order) → L2 `build_tile_surface_state` → `generate_surface_chunk` / column fill → pack writer.

#### DONE
- TR-1 multi-pass skeleton; TR-1b pole isolation  
- Pack bake modes light / full / detailed + refine-from-entry HTTP  
- L0 contributor compose from `COMPOSE_CONTRIBUTOR_ORDER`  
- WP-PERF-22 parent-light L2 (z band + terrain mask carry + facing)  
- TR-PAR chunk pool on L2; TR-PERF-1…4 on residual map_cells paths  
- TR-LAZY-LOAD-1/2 service + debug HTTP (`has-column`, `scene-volume`)  
- Pass 1.4 before hydro in surface context; relief grade persist hook after L0  

#### PARTIAL
- Magma band yes / M-3 movement no  
- Ores/caves stubs only  
- Landcover / settlement L0 = interim pins/paint, not full Spec plugins  
- `generate_z_slice` / `save_z_slice` code without HTTP  
- `generate_minimal` still climate-mixed (TR-5)  
- WP-28 resume / completeness loops  

#### PLANNED — near-term
- TR-PAR-4 stress; WP-28 resume; TR-6/7 persist matrix hygiene  
- Close D HY acceptance on **pack** smoke (not map_cells)  
- Doc: remove stale `generate-surface` / sequential-v1 banners  
- MLB deferred: flora, farmland MaskDomain, ocean DepressionForm (hydro-owned)  

#### PLANNED — DAG / deferred
- TR-PAR-DAG-1, TR-LAZY-LOAD-DAG (`check_terrain` / `lazy_terrain` …)  
- Phase 9+ materialization nodes — **gate with master**  
- M-3 magma movement; lazy caves ~20r gameplay  

#### Stale TZ watch
- Docs still mention `POST generate-surface|ores|caves` — **removed**; SoT = `pack/bake`  
- Mid-doc “parallel v1 sequential / TR-PERF ⬜” contradicts later ✅  
- Facade `generate_surface` ≠ pack product path (no 1.4/hydro)

---

### 10.2 Hydrology *(deep 2026-08-09)*

**Owns:** Pass 1.5 carve + roles/`liquid_candidate`; light HydroContributor Path A + R5b stub bathymetry; river segments DTO.  
**Does not own:** ice/steam phase, season flow, LLM naming, cave hydro, connection persist.

#### DONE
- Full `generators/hydrology/` layout + `HydrologyGeneratorService.apply` scopes  
- Declare U23 from `world.hydrology.declared_*` (not connection graph)  
- Coastal sea bands, lakes declare+auto, rivers declare+procedural D8  
- Wired in `prepare_surface_terrain_context` after Pass 1.4  
- Light Path A declare rivers/basins + coarse open water; R5b stub z  
- L2 `merge_hydro_hard_corridor`; U19 hydrology JSON on column fill; U28 river_bed → `liquid_body`  
- Climate overlay gated on `liquid_candidate` (**not** z≤0)  
- Offline smoke script exists  

#### PARTIAL
- Open ocean ≈ relabel stub (no real open-mass expand)  
- Coastal landforms classifier = coastline echo  
- `riverConnectionEmit` returns empty  
- River U15 shore bands missing; U17 classify thin  
- SEA/LAKE `liquid_body` depends on climate overlay (not column fill)  
- `dirty_bbox` not wired into climate recalc (C14)  
- Legacy `TerrainGeneratorService.generate_surface` has **no** hydro  
- No `POST …/generate-hydrology` route  

#### PLANNED — near-term
- DepressionForm ocean floor; real OPEN_OCEAN / inland_sea  
- Landform topology; emit+persist rivers; HY-5/HY-5b smoke  
- Wire or formally retire legacy surface path; C14 dirty climate  
- Sync TZ header/checklist (still says Impl ⬜ H-0…H-7)  

#### PLANNED — DAG / deferred
- H-7b `apply_hydrology` node; U13 naming (HY-3); U12 cave hydro (HY-2)  
- Seasonal melt as runtime climate, not carve  

#### Stale TZ watch
- HY-1 still framed as “z≤0 liquid” — overlay fixed; remainder = carve/smoke completeness  
- Plan link `hydrology-pre-dag.md` missing  

---

### 10.3 Climate *(deep 2026-08-09)*

**Owns:** poles/anchors/tier, cell weather fields, liquid overlay (consumes hydro flag), pack climate blobs, season temp offsets.  
**Does not own:** terrain z, hydrology mask creation, volume climate, world snapshot.

**Product path today:** pack bake/read is primary. SQL `ClimateBatchOrchestrator` exists but **orphaned** after map `generate-climate` removal; DAG still calls serial `apply_climate_pass`.

#### DONE
- Pole + tier-2 resolve; admin merge only when pole empty; auto anchors zone-from-pole  
- Precipitation liquid + peak clamp; repair/normalize defaults  
- Eager cell weather; liquid overlay via `liquid_candidate` (not z≤0)  
- Pack coarse/fine bake + sample ladder + apply-to-view  
- `SurfaceTerrainContext` shares pole/local/z with pack  
- Season offsets at runtime; climate extracted from terrain facade  

#### PARTIAL
- `assemble_full` / `full_surface` = weather **without** liquid; liquid on `apply_climate_pass` / batch only  
- Recalc ignores most `ClimateRecalcRequest` flags; `run_cell_weather` wrongly gates liquid (CL-7)  
- Runtime `system_weather=None` — no registry pick / missing `weatherResolve.py`  
- Batch orchestrator unused by HTTP; DAG not on batch+ctx  
- Light `ClimateContributor` = pole-only tint (accepted), not climate field SoT  
- `ClimateFinePending.enqueue` dead — fine baked sync  

#### PLANNED — near-term
- Fix recalc types/flags; real weather pick; CL-3 sample unify; CL-5 import validator  
- Deprecate legacy Voronoi; align smoke; TR-5 `generate_minimal` decoupling  

#### PLANNED — DAG / deferred
- CL-PAR-DAG-1 batch wiring; event→recalc routing  
- C6–C13 / CL-17/18 `SurfaceClimateField` + LOD policy  
- Volume climate; snapshot field cache; neighbor blend  

#### Stale TZ watch
- Docs still describe `POST generate-climate` / materialize-stack — removed  
- CL-R2 `_non_surface_anchor_cells` deleted but debt may still mention it  
- “DAG nodes ⬜” understates stub presence  

---

### 10.4 Mountains + Relief grade *(deep 2026-08-09)*

Keep as **two subdomains** sharing terrain package.

#### Mountains — DONE
- PassBuilder topology → Specs (MST/Delaunay, saddles, spine, range gap)  
- Paint FG→FR→SF + U6 range compose; MaskDomain plugin  
- Shared Spec SoT for Pass 1.4 z-rise and light paint  
- R33 side stamp on **light** collect  

#### Mountains — PARTIAL / PLANNED
- U4 secondary stub; U5 cap `t` partial; U7 inset defaults  
- R33 **not** on coarse 1.4 → all-SLOPE fallback warning  
- Open: U8 ridge noise, U9 ravine/cliff Spec, U10 summit overlays  

#### Relief grade — DONE
- Waves A–D: templates R33–R35, R36 core + canal, open_land/shore/road_shoulder ribbons  
- Grade instances/systems persist on pack bake; BAR-1 intents after compose  

#### Relief grade — PARTIAL / PLANNED (Wave E)
- Cardinal facing only → R36s 8-way → R36r diagonal  
- R36o junction smooth; Q4 mountain SideFill + R36 angle/Grade  
- R36f/k pathfinding gameplay; residual DRY smells T-33…40  

#### Stale TZ watch
- Mountain TZ / MLB tables still say “PassBuilder = target / 1:1 collect” — **code has PassBuilder**  
- `ReliefContributor` ≠ grade (base z only)  

---

### 10.5 Settlement *(deep 2026-08-09)*

**Owns:** outdoor city generate (skeleton→districts→streets→barriers→occupancy→dominant_material); persist scopes via `SettlementPersistService`.  
**Does not own:** interiors epic, architectural_style→geometry, growth/highways, LLM payload.

#### DONE
- Phases A–F outdoor generate; district conditions/specialisation/required_structures  
- Building cache generate-first; city+district **grid** graphs; walls + area fences  
- `dominant_material` post-assemble; economic tier filters  
- PersistService outdoor scopes + debug HTTP + persist smoke scripts  

#### PARTIAL
- `lazy_settlement` = cells only (≠ debug full persist)  
- Location type: route wants `"settlement"`, fixtures `city`/`town`  
- Street layouts besides grid raise; `init_mode` unimplemented  
- `derive_structure_context` thin; `collect_edge_cells` always `[]`  
- CitySkeleton missing state_uid / mood; density via getattr (NC-9)  

#### PLANNED — near-term
- Unify lazy → PersistService; fix type gate; DAG dominant_material wire  
- Explicit grid-only v1 or implement non-grid; NC-2/LC P1  

#### PLANNED — deferred
- Phase G organic footprint; Phase H z-topology; growth services; style→geometry; interiors in `full`  

#### Stale TZ watch
- Top city TZ status still “persist ⬜” — **false** vs §11.5 + code  
- Debt “out of scope: persist connections” — implemented at service layer  
- assembler-hierarchy rule still claims area NotImplemented — false  

---

### 10.6 Road + Barrier *(deep 2026-08-09)*

#### Road — DONE
- City `planner/streets` + district `DistrictRoadGenerator` **grid**  
- Width/lanes/sidewalk **policy** helpers + travel resolver  
- Pack `RoadContributor` paint + shoulder → ribbon intents  

#### Road — PARTIAL / PLANNED
- Sidewalk = flag/log only — **no sidewalk edges**  
- organic/radial/cul_de_sac/courtyard NotImplemented  
- World routes / RoadAssembler folder / area path graph — missing  
- District edges often unmaterialized; entry_point not snapped into district grid  

#### Barrier — DONE
- Shared `perimeter` / `material` / `cells` / `ribbonFence`  
- Settlement walls + area fences; BAR-1 once after light compose (RELIEF-BAR-1 resolved)  

#### Barrier — PARTIAL / PLANNED
- NC-3: no district barrier pipeline; template gates/towers unread  
- NC-4: settlement vs building `location_uid` undocumented  
- Settlement planner still string-literal wall/gate emit vs area `emit_barrier_cells`  

---

### 10.7 Structure *(deep 2026-08-09)*

**Owns:** interior box + BuildingAssembler shell; settlement cache/area path.  
**Does not own:** furniture, persist, LLM, yard/small buildings.

#### DONE
- Deterministic multi-level interior; shapes v1; layout A+B  
- u_shape + vertical/external ladders; corridor trim+connect; wall openings  
- Foundation slab/perimeter/full/hull; roof flat/gable/hull  
- Cache → translate → rebind → area barrier; debug generate; dataModel enums  

#### PARTIAL
- `validate_template` stub; outline ≠ full template schema  
- Context derive = defaults only; porch/access_type not built  
- Connect order ≠ TZ; railings commented out; `underground_fallback` unused  
- Taxonomy drift TZ §3.9 vs code `StaircaseType`  

#### PLANNED
- straight/spiral/embedded shaft; ruins/hull/extraction assemblers  
- stilts / roof auto / hip product types; furniture assembler  
- Full validate_template; OQ wall-opening rules; NC-1h / LC debt  

#### Stale TZ watch
- `BuildingGeneratorService` name; area NotImplemented claims; trapdoor package layout; connect-before-passages order  

---

## 11. Cross-cutting themes from deep passes

1. **Product path = pack bake** for wilderness; many TZ/HTTP references to `generate-surface` / `generate-climate` are stale.  
2. **Services ahead of production wiring** — climate batch, settlement persist exist; DAG/lazy/HTTP often still thin or cells-only.  
3. **Status tables lag code** — especially hydrology H-0…H-7, city persist ⬜, mountain “PassBuilder target”.  
4. **DAG remains gated** — do not treat missing nodes as generator immaturity.  
5. For peer comparison: score **capability axes** (§0–§5) using §10 done/partial, not optimistic TZ headers.
