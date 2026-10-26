# JSON Validator — чеклист имплементации

**Статус:** Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ · Phase 3 ✅ · Phase 4 next  
**Канон:** [`docs/tz_json_validation.md`](../docs/tz_json_validation.md) — § Архитектура, § Runtime validation (read path)

---

## Phase 0 — каркас ✅

- [x] `worldData/jsonValidation/types.py`, `facade.py`, `orchestrator.py`, `registry.py`, `http.py`
- [x] Hook в `WorldBundleService` — validate-before-transaction (Phase 0 no-op pass)
- [x] `ValidationIssue` → HTTP 422 via `format_validation_issues`
- [x] `Container.json_validation_facade()`
- [x] Unit: `tests/test_json_validation_jv0.py`

**Код:** `backend/app/application/worldData/jsonValidation/`

---

## Phase 1 — JV-0 + JV-1 ✅

- [x] `shared/wire.py` (`parse_enum`, `WireEnumError`)
- [x] `EnvelopeValidator`, `WorldRowValidator`, `N1SNormalizeStage` + `normalize/n1sSchemas.py`
- [x] Envelope checks removed from `WorldBundleService` → `EnvelopeValidator`
- [x] `WorldService._validate` → `collect_world_row_issues_from_world`
- [x] `factory.py` — default registry + orchestrator
- [x] Unit: `tests/test_json_validation_jv1.py`
- [ ] `generators/registries/*` StrEnum (deferred — wire.py only for now)

## Phase 2 — JV-2 ✅

- [x] `WorldRegistryIndex` + `RegistryIndexBuilderStage` (Pass 1)
- [x] `RegistryRefsValidator` (Pass 2 inbound refs in world registries)
- [x] `NamedLocationRowValidator`, `ConnectionNodeRowValidator`, `ConnectionEdgeRowValidator`
- [x] `DeclareTopologyValidator` (geographic lake/coast declare)
- [x] `generators/registries/wireEnums.py` (E-08…E-13)
- [x] `syntheticBundle.py` + facade `SECTION` kind
- [x] climate_pole limit moved from `NamedLocationService` → validator
- [x] Unit: `tests/test_json_validation_jv2.py`
- [x] Fixture drift fix: `sand`, `terrain_open_space` in `world_template.json`

## Phase 3 — JV-3 ✅

- [x] `normalize/hydrologyDefaults.py` — explicit defaults, `type_classify` null→U22
- [x] `normalize/climateDefaults.py` — pole mode/preset, `precipitation_liquid`
- [x] `HydrologyClimateNormalizeStage` in orchestrator
- [x] `HydrologyPolicyValidator`, `ClimatePolicyValidator`
- [x] wire enums E-17…E-21 in `generators/registries/wireEnums.py`
- [x] Unit: `tests/test_json_validation_jv3.py`
- [ ] Unify `resolveRiverTypeClassify` to read explicit DB only (JV-7)

## Phase 4 — JV-4/5 (next)

- [ ] Building / district / barrier template validators

## Phase 5 — JV-8

- [ ] `RaceContractValidator` + seed index loader

## Phase 6 — JV-6

- [ ] `character/jsonValidation/`

## Phase 7 — JV-7

- [ ] Remove runtime hardcodes; generators warn_only
