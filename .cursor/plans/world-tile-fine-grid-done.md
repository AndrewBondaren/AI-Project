# World tile fine grid — impl plan ✅ DONE

## Контракт

- **Мировой тайл** `(Gx, Gy)` — индекс на глобальной карте.
- **`fine_cells_per_map_cell`** — сторона локальной карты тайла: `fine_cells_per_map_cell × fine_cells_per_map_cell` ячеек, шаг **1 м** (`FINE_CELL_SIZE`).
- **`map_cells.x/y`** для terrain skeleton — **world meters** (fine), не macro index.
- Macro tile: `Gx = x // fine_cells_per_map_cell`, `Gy = y // fine_cells_per_map_cell`.

## Генерация

1. Coarse heightmap (macro) — hydrology planning (ocean/lake flood на macro, expand на fine при materialize).
2. Hydrology `apply` на coarse heightmap.
3. **Bootstrap init** (default): full fine grid только для priority macro tiles (`bootstrap_macro_tiles`: anchors → declared hydro → meter rivers → coarse flood; cap `max_tiles`, default 16). API: `POST generate-surface?mode=bootstrap`.
4. **Full bbox** (опасно при `fine_cells_per_map_cell=3000`): `mode=full` — все macro tiles в bbox.
5. Доп. тайл: `POST materialize-tile?gx=&gy=`.

## Рендер

- `world-map.txt` — 1 символ / macro tile (aggregate top surface fine cells).
- `tiles/Gx{N}_Gy{M}/` — local top-down fine grid + z-column profile.

## Settlement occupancy

Footprint → все fine cells в macro tiles footprint (urban).
