# JSON Validation — roadmap (agent plan)

Ссылается на [`docs/tz_json_validation.md`](../../docs/tz_json_validation.md).

**Статус:** write-path triggers T1–T7 закрыты; row validators — perks ✅; map/state — pending.

**Тесты:** `93` — `python -m unittest discover -s tests -p "test_json_validation*.py" -q`

---

## Triggers (write path)

| ID | HTTP / код | Gate | Статус |
|---|---|---|---|
| **T1** | `POST /api/worlds/import` | `ValidationKind.BUNDLE` in `WorldBundleService` | ✅ |
| **T2** | `POST …/{locations,races,perks,map}/import` | `sectionImportGate` → synthetic bundle | ✅ |
| **T3** | `POST /api/worlds` | `crudPatchGate.gate_world_create` | ✅ |
| **T4** | `PUT /api/worlds/{uid}` | `crudPatchGate.gate_world_update` (+ `force` product rule in service) | ✅ |
| **T5** | `POST/PUT …/{locations,races,perks}` | `crudPatchGate` entity row | ✅ |
| **T6** | `POST /api/seed/import`, `POST /api/seed/{table}` | `seedImportGate` | ✅ |
| **T7** | `POST /api/characters/import` | facade → `character/jsonValidation` | ✅ |
| **T8** | editor dry-run (future) | `validate()` only | ⬜ |
| **T9** | generate / play | runtime read path, not facade | JV-7 warn-only ✅ |

---

## JV phases

| Phase | ID | Статус |
|---|---|---|
| 0 | каркас facade/orchestrator/registry | ✅ |
| 1 | JV-0, JV-1 — envelope, world row, N1-S normalize | ✅ |
| 2 | JV-2 — index, locations, connections, declare | ✅ |
| 3 | JV-3 — hydrology + climate policy | ✅ |
| 4 | JV-4, JV-5 — building/district/barrier templates | ✅ |
| 5 | JV-8 partial — race row + contract + seed index | ✅ |
| 6 | JV-6 — character package | ✅ |
| 7 | JV-7 — runtime legacy warn-only in generators | ✅ |

---

## Schema validators

| SCH-* | Validator | Sections | Статус |
|---|---|---|---|
| SCH-WORLD-BUNDLE-ENVELOPE | `EnvelopeValidator` | — | ✅ |
| SCH-WORLD-ROW | `WorldRowValidator` | WORLD | ✅ |
| SCH-WORLD-REGISTRY-REFS | `RegistryRefsValidator` | WORLD | ✅ |
| SCH-WORLD-HYDROLOGY | `HydrologyPolicyValidator` | WORLD | ✅ |
| SCH-WORLD-CLIMATE-POLICY | `ClimatePolicyValidator` | WORLD | ✅ |
| SCH-NAMED-LOCATION-ROW | `NamedLocationRowValidator` | LOCATIONS | ✅ |
| SCH-CONNECTION-* | node/edge + declare topology | CONNECTION_* | ✅ |
| SCH-RACE-ROW | `RaceRowValidator` | RACES | ✅ |
| SCH-RACE-CONTRACT | `RaceContractValidator` | RACES | ◐ Pass 1 (hair/skin/beard/brows/lifespan) |
| SCH-PERK-ROW | `PerkRowValidator` | PERKS | ✅ |
| SCH-SEED-BUNDLE | `SeedTableValidator` | SEED | ✅ |
| SCH-CHARACTER-* | character facade | CHARACTER | ◐ row/sheet/bind |
| SCH-MAP-CELL-ROW | `MapCellRowValidator` | MAP_CELLS | ⬜ low |
| SCH-STATE-ROW | `StateRowValidator` | STATES | ⬜ defer |
| SCH-ECONOMIC-TIER-REF | cross in location/template | — | ◐ partial |

---

## Ключевые файлы

```
backend/app/application/worldData/jsonValidation/
  facade.py, orchestrator.py, factory.py, registry.py
  crudPatch.py, sectionImport.py, seedImport.py, syntheticBundle.py
  validators/   — row + policy + templates + seedTable + perkRow
  normalize/    — n1s, worldRegistries, hydrology, climate
  index/        — worldRegistryIndex, seedRegistryIndex

backend/app/application/character/jsonValidation/

backend/app/api/utils/
  sectionImportGate.py, crudPatchGate.py, seedImportGate.py
  jsonResolver.py, responseHelpers.py
```

---

## In progress

| Phase | ID | Deliverable |
|---|---|---|
| **10** | SCH-MAP-CELL-ROW | `MapCellRowValidator` — terrain/hydrology refs (low) |

---

## Queue (priority)

| # | ID | Deliverable | Зачем |
|---|---|---|---|
| 11 | JV-8 Pass 2 | race contract: eye/mouth/voice, `applicable_fields` | полный SCH-RACE-CONTRACT |
| 12 | JV-6+ | character appearance vs race; mastery/perk refs | bind персонажа к миру |
| 13 | orchestrator | auto `seed_snapshot` on T1 bundle import | race contract без ручного seed |
| 14 | tech debt | убрать `WorldService._validate` на bundle path | один semantic gate |
| 15 | tech debt | fixture drift (`race_traits.adaptive`); legacy DB worlds | консистентность fixture/БД |
| 16 | JV-7 final | убрать generator `warn_once` paths | после normalize всех миров |
| 17 | v0.2 | Pydantic `jsonValidation/models/`; golden `world_template.json` | registry 0.2 |
| 18 | T8 | `POST …/validate` dry-run | редактор миров |

---

## Deferred

- **SCH-STATE-ROW** — нет states CRUD/import routes
- **SCH-WORLD-FORMULAS** — derived/action formulas, slots, combat, calendar
- **Connection T2** — нет import routes для nodes/edges
- **SCH-FACTION-BUNDLE** — контракт не готов
- **N1-W-37…39** — lighting/mat_tag/npc_llm_event ORM ⬜
- **Formula DSL** — `system_condition` / perk formulas struct-only v0.1

---

## Known issues

| Issue | Workaround |
|---|---|
| `world-template-001` в БД без `sand` в `material_registry` | re-import → v1 uid, или PUT registry |
| `world_test.json` world blob — неполные registries | row-only тесты OK; SECTION/CRUD нужен `world_template` world |
| T2 map/perks до PerkRow — world-level only | PerkRow ✅; MapCell still no-op on rows |
| `WorldService.import_from_json` — дубль `_validate` | tech debt #14 |

---

## Smoke (backend up)

```powershell
# T6 seed
curl.exe -X POST "http://127.0.0.1:8000/api/seed/import" -F "path=E:/AI Project/fixtures/seed.json"

# T5 perk CRUD (world с полным registry)
curl.exe -X POST "http://127.0.0.1:8000/api/worlds/{world_uid}/perks" -H "Content-Type: application/json" -d "{\"perk_uid\":\"p1\",\"system_name\":\"x\",\"display_name\":\"X\"}"
```
