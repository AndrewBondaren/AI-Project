# CONN-1 — `node_type` → `connection_node_type`

**Status:** open · **P:** P2 · **Не блокирует HY-5**

## Зачем

- `node_type` на `connection_nodes` путают с engine DAG node.
- `connection_type` на edges занято (`road`, `lake_shoreline`, …).
- Целевой wire-ключ: **`connection_node_type`**; StrEnum **`ConnectionNodeType`** — без переименования.

## Checklist

- [ ] `backend/app/db/migrations/0001_initial.sql` — колонка `connection_node_type`
- [ ] `backend/app/db/models/connectionNode.py` — поле + комментарий portal-only полей
- [ ] `fixtures/world_template.json` — `connection_nodes[].connection_node_type`
- [ ] Generators: `streets.py`, `road/layouts/gridLayout.py`, hydrology graph loaders
- [ ] Import/persist: `ConnectionGraphService`, `bundleRemapService`, `WorldBundleService`
- [ ] `docs/tz_structure_connections.md` — §3.1, SQL draft, §3.5 примеры
- [ ] `docs/tz_terrain_hydrology.md` — draft bundle примеры
- [ ] `application/jsonValidation/` — DTO bundle row (когда connections slice в JV)
- [ ] Grep: `node_type` на connection_nodes → 0 (кроме engine DAG / unrelated)

## Правила

- **Без** backward-compat alias `node_type` на import — recreate БД.
- **Не** переименовывать `ConnectionNodeType` enum class.
- **Не** трогать `engine/`.

## Refs

- [`docs/tz_generator_technical_debt.md`](../docs/tz_generator_technical_debt.md) § CONN-1
