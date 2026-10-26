# Hydrology edge cases — declared / declared-autoresolve / autoresolve / consumers [DONE]

Источник: аудит покрытия (чат 2026-10-19). Три раздельные категории кейсов по
решению мастера: **declared** (явное объявление мастера — наивысший приоритет),
**declared-autoresolve** (мастер объявил интент endpoints/via_locations — движок
достраивает полилинию), **autoresolve** (процедурный, только policy-gated).

## Шаг 1 — `tests/test_hydrology_edge_cases.py`

Файлы: новый тест-файл + `named_location()` в `hydrology_fixtures.py`.

| Класс | Кейсы |
|---|---|
| `DeclaredEdge` | enabled=False → пустой результат и z не тронут; мастер без declared → noop; одноточечный coastline → без падения; declared-озеро в occupied → autoresolve море не перетирает uid |
| `DeclaredAutoresolveEdge` | via_locations → сегменты через NamedLocation anchors + uid; endpoints mouth → snap к ближайшей воде; missing location anchor → нет сегмента; steep z → mountain_river classify |
| `AutoresolveEdge` | river planner cap MAX_RIVERS_PER_BBOX; все autoresolve-флаги off → пусто |
| `ConsumerEdge` | LANDFORMS scope → `coastline_polylines`; scopes={LAKES} → COASTAL_SEA не запускается даже с declared coastline |

## Приёмка

- `python -m unittest tests.test_hydrology_edge_cases` зелёный.
- Полный hydrology-набор зелёный.
