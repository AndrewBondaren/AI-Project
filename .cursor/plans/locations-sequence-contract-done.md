# Read-only locations: Sequence contract — DONE

Статус: DONE. Пользователь попросил составить план и выполнить исправление.

Один атомарный шаг: согласовать входной контракт существующей цепочки чтения,
без новых классов, изменения алгоритмов и копирования входа в list.

- ТЗ: docs/tz_terrain_generation.md §Surface planning/cache (request input
  contracts, уточнение Sequence в этом же шаге).
- Файлы: planning/composition/surfacePlanningEntry.py (`surface_world_topology`),
  generators/terrain/passes/bbox.py (`world_bounds_from_world`,
  `grid_bbox_from_locations`), generators/climate/locations.py (`static_map_anchors`).
- Контракт: locations: Sequence[NamedLocation]; для world_bounds_from_world
  сохранить optional None/default. Возвращаемые типы и существующие callers
  со списками не меняются. static_climate_poles и прочие соседние API вне scope.
- Проверки: list/tuple/UserList с реальными NamedLocation, fallback bounds,
  пустой вход, приоритет declared bounds и сохранение входной коллекции;
  positive typing fixture с Sequence и tuple; unittest world_bounds и planning
  request boundary, pyright planning valid.
- Done: четыре входные аннотации согласованы, алгоритмы неизменны, проверки
  проходят. Отметить выполнение и переименовать план с суффиксом -done.
- Папки: climate 20→20 (существующее превышение, новых файлов туда нет;
  композиция требует отдельного плана), terrain/passes 9→9,
  planning/composition 5→5. WARN по существующим папкам выдан в чат.

Проверено: `python -m unittest tests.test_world_bounds
tests.planning.consumers.test_request_boundary tests.planning.consumers.test_wiring -q`
из backend с PYTHONPATH=tests — 37 OK. Pyright planning valid — 0 ошибок;
positive fixture включает Sequence и tuple. Инструмент по-прежнему сообщает
о шести устаревших include paths существующей typing-конфигурации.
Алгоритмы и возвращаемые типы не изменялись. Коммит не создавался.
