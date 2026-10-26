# Plan: BUNDLE-2 — section handlers (architecture layers) ✅ DONE

**SoT:** [`docs/tz_world_bundle.md`](../../docs/tz_world_bundle.md) (WB-1…WB-15)  
**Status:** Impl landed 2026-07-30 (Q1–Q3 locked: breaking rename, `*_template_registry`, perk FK → library). Follow-up: fixture/script wire rename.  
**Gate:** schema via `0001_initial.sql` + models only (recreate DB); DAG nodes не трогать; backend не стартовать агенту  
**Out of scope this plan:** Location subgraph transfer API (documented in TZ § Location transfer — later); RELIEF-BAR-1; Pack bake

---

## Целевое состояние

```text
WorldBundleService → ORDERED handlers
  EntitySectionHandler×5   (world, states, locations, connection_nodes, connection_edges)
  LibraryTemplateSectionHandler×4  (relief_templates, building_templates, race_templates, perk_templates)
```

- Library: global SQL + `*_template_registry` on world + top-level body sections  
- Races/perks: migrate off world-scoped full rows  
- Locations: entity; cross-world copy = subgraph import later (not this plan)

---

## Порядок имплементации = слои

| Step | Слой | Deliverable |
|---|---|---|
| 0 | Domain errors | `BundleValidationError`; facade без FastAPI; route map |
| 1 | Protocol + order | `bundle/handler.py`, `order.py`, `registry.py` — см. TZ § Размещение классов |
| 2 | Library kind | `bundle/library/libraryTemplateSection.py` + `adapters.py` |
| 3 | Wire + schema | `BundleSection` keys; global race/perk libraries; world registries; building section; character_perk FK per Q3 |
| 4 | Library instances | Relief + Building + Race + Perk wired to kind |
| 5 | Entity handlers | world, states, locations (+ topo_sort), nodes, edges |
| 6 | Thin facade | loop only; Container builds ordered handlers |
| 7 | Polish | ImportResult sweep (`application.importResult`); BUNDLE-2 / HY-S-2 → resolved in debt TZ |

**Не done:** entity-only facade без library domains.

**Блокер старта кода:** закрыть Q1–Q3 в TZ (или явное «breaking rename + library uid FK» от мастера).

---

## Тесты / smoke (после impl; backend поднимает мастер)

- Unit: handler order; library miss → WARNING; locations topo_sort  
- Round-trip skeleton with all four `*_templates`  
- Duplicate world_uid remap (BUNDLE-1) still works  
- `map_cells` → 422  

---

## Антипаттерны

- Slice «handlers without race/perk/building templates»  
- Locations → library ради cross-world copy  
- Copy-paste per library domain without shared kind  
- FastAPI / HTTPException в `WorldBundleService`  
- DAG / BAR-1 / subgraph-transfer API в этом PR
