# План: техдолг ревью шагов 0–7 — wilderness regions — done

## Контекст

Ревью реализации шагов 0–7 плана
[`wilderness-regions-mechanic.md`](wilderness-regions-mechanic.md)
(коммиты `38e1be37..470300d8` + рабочее дерево; ~92 файла backend,
145 unittest проходят). Архитектура в целом соответствует плану
(typed Spec/Shape, precedence 2b единый для L0/L2, DET-1 каналы, thin
contributor); ниже — зафиксированные дефекты и открытые вопросы контракта.

Проверки каждого шага: `python -m unittest tests.<…>` из `backend/` +
`compileall app`; smoke — где указано.

## Карта находок → шаги

| # | Находка | Файлы | Шаг |
|---|---|---|---|
| 1 | `claim_owners` — полный BFS по всем сидам мира — пересчитывается на каждый регион (L0 `materialize`) и на каждый refine-тайл (L2): O(regions × seeds × max_radius²) | `masks/regionRasterizer.py:103`, `landcover/materializer.py`, `landcover/finePaint.py` | 1 |
| 2 | `paint_regions_fine`: `if not regions: return {}` до restore-ветки — stale `region_uid` на parent при пустом collect не восстанавливается в fallback | `landcover/finePaint.py:100-102` vs `:132-135` | 2 |
| 3 | `merge_rank` доминирует `placement_specificity`: declared farmland (`merge_rank=0`) проигрывает все конкурентные клетки autoresolve-региону (plains=1, forest=2); проигрыш молчаливый — «declared wins» на пересечениях не выполняется | `masks/regionPrecedence.py:27-35`, `dm/terrain/worldTerrainRegistry.py` (`_FARMLAND_ENTRY`) | 3 (контракт) |
| 4 | `resolve()` zero-score argmax → лексикографический min: при `facts=None` все кандидаты с 0.0 → побеждает `farmland`, а не `plains` | `regions/coverageResolver.py:62-69` | 4 |
| 5 | `resolve_forest_plains._pick` → `next(iter(terrain_set))` — недетерминированный fallback-ключ; функция теперь в пути L2 restore (`background_key_for_zone`) — ломает детерминизм bake, когда plains/forests отсутствуют в `terrain_set` | `masks/resolveForestPlains.py:24`, `contributors/landcoverBackground.py` | 5 |
| 6 | `BboxShape.area()` = `dx·dy`, но `contains` инклюзивен → реальное покрытие `(dx+1)(dy+1)`; bbox 1×1 имеет area=0 и всегда проигрывает tie-break | `dm/spatial/regionShape.py:64` | 6 |
| 7 | `declared_regions` без `DefaultWhenMissing` — на wire всегда сериализуется `[]`, в отличие от `declared_mountains` и соседних полей | `dm/terrainMasks/worldTerrainMasks.py:138` | 7 |

## Вне scope (зафиксировано, не долг этого ревью)

- `hillPlacement`/`openLandTerrains` — шаг 7b ещё не реализован (в работе);
  ревью там не применимо.
- `hydrologyIndex`/`sublocations`/`claim_area` — staging для шага 8;
  `self.hydrology_entries` гоняется каждый `collect` впустую — уйдёт при
  подключении manifest-адаптера.
- `resolve_forest_plains`/`profile_for_zone_key`/`*_from_zone` целиком —
  удаляются шагом 10b; фиксится только детерминизм `_pick` (шаг 5), не
  переписывание legacy-модуля.
- `merge_hydro_hard_corridor` повторно вызывает `hydro_mask_from_parent`,
  хотя orchestrator уже построил `l0_hydro` — дублирующий проход; мелкий
  perf, отдельного шага не стоит.
- `equal_rank_resolved` WarningError внутри `cmp_to_key` — до O(n log n)
  дублей лога на один sort; терпимо.
- Дубль формулы macro→fine bounds: `RegionRasterContext.fine_topology` vs
  `autoresolve/claim.fine_topology` — вынести в общий helper при первом
  же касании (тривиально).
- `isinstance(uid, str)` guard в `cells_to_fine_terrain_chunk` (uncommitted)
  — мёртвая защита, молча гасит невалидный uid; можно оставить, можно
  убрать — не блокирует.

## Шаги

### Шаг 1 — кэш `claim_owners` на один claim ✅

- **Статус:** done — явный `ClaimOwnersIndex` (предпочтительный вариант
  контракта): один BFS на claim за pass; `autoresolve_regions` →
  `(regions, index)`; materializer держит `self._claim_indexes`,
  `finePaint` берёт через `claim_index()`; бонус-фикс — дедуп в
  `wildernessRegionIndex` по `id(claim)` → по значению claim.
- **Цель:** карта «координата → победивший сид» считается один раз на
  `RegionClaim`, а не на каждый регион/тайл.
- **ТЗ:** `tz_map_light_bake.md` § Регионы покрытия › Autoresolve
  (детерминизм w не зависит от scope — сохранить); план §4 шаг 4/5b.
- **Файлы:** `backend/app/application/worldData/masks/regionRasterizer.py`,
  `backend/app/application/worldData/generators/terrain/landcover/materializer.py`,
  `backend/app/application/worldData/generators/terrain/landcover/finePaint.py`.
- **Контракт:** `claim_owners(claim, root, topology)` мемоизируется по
  identity claim (claim frozen → подходит ключом; либо явный
  `ClaimOwnersIndex`, создаваемый один раз в `collect`/pass и
  передаваемый в rasterize). Выбирает имплементатор: предпочтительно
  явный index-объект, а не скрытый `@cache` на публичной функции.
- **Проверка:** `tests.test_region_rasterizer` + `test_landcover_materializer`
  + `test_landcover_fine_paint` без изменений результата; benchmark-log
  или счётчик вызовов — один BFS на claim.
- **Done:** один `claim_owners` на claim за bake и за refine; тесты зелёные.

### Шаг 2 — restore fallback при пустом `regions` в `paint_regions_fine` ✅

- **Цель:** убрать early return, при котором `region_uid` на родительских
  light-клетках остаётся «замороженным» в upsampled terrain, когда
  collect() вернул пустой список. Код снят шагом 9b основного плана;
  здесь — регрессионный тест.
- **ТЗ:** `tz_map_light_bake.md` § Регионы покрытия › L0/L2 (фон вне
  точного контура = per-cell fallback); план §4 шаг 7.
- **Файлы:** `backend/app/application/worldData/generators/terrain/landcover/finePaint.py`,
  `backend/tests/test_landcover_fine_paint.py`.
- **Контракт:** при `regions == []` выполняется та же ветка
  `region_painted_parent → restore background`, что и при пустом
  `winners`; быстрый выход — только если нет ни winners, ни
  `region_uid` на parent.
- **Проверка:** новый кейс в `test_landcover_fine_paint` (parent с
  `region_uid`, collect → `[]` → terrain восстановлен в fallback);
  регрессия 145.
- **Done:** stale-region клеток нет; тест-кейс проходит.

### Шаг 3 — контракт: merge_rank vs declared на пересечениях (решение, не код) ✅ вариант b

- **Цель:** зафиксировать в ТЗ намеренное поведение: declared-регион с
  типом низкого merge_rank (farmland=0) проигрывает **все** конкурентные
  клетки autoresolve-покрытию с более высоким рангом — «declared wins»
  на пересечении не действует и не логируется.
- **ТЗ:** `tz_map_light_bake.md` § Регионы покрытия › Пересечения и
  приоритет, › Placement priority; план §4 шаг 2b.
- **Файлы:** `docs/tz_map_light_bake.md`; при изменении контракта —
  `backend/app/application/worldData/masks/regionPrecedence.py`.
- **Варианты:** (a) текущее поведение = контракт → зафиксировать в ТЗ +
  warning-лог проигранной declared-декларации; (b) declared-бонус к
  precedence перед merge_rank → правка `_precedence_key` + ТЗ.
- **Проверка:** ревью разработчика на правку ТЗ (или юнит на новый
  порядок при варианте b).
- **Done:** контракт в ТЗ однозначен; выбран вариант и доведён до кода/лога.

### Шаг 4 — zero-score → unresolved в `resolve()` ✅

- **Цель:** argmax при score=0 у всех кандидатов не должен выбирать
  лексикографический минимум (`farmland`) как скрытый дефолт.
- **ТЗ:** `tz_map_light_bake.md` § Регионы покрытия › Реестр и
  CoverageResolver («все отпали → WarningError, тип не меняется»).
- **Файлы:** `backend/app/application/worldData/regions/coverageResolver.py`,
  `backend/tests/test_coverage_resolver.py`.
- **Контракт:** кандидат с `score == 0` не побеждает (или явный
  threshold); итог `None` → WarningError + сохранение типа — тот же
  путь, что и «все отпали». Точный порог — по решению в ТЗ; минимум —
  `score > 0`.
- **Проверка:** юнит — факты `None` → `resolve` = `None` + warning;
  существующие кейсы argmax/tie не меняются.
- **Done:** farmland не возникает из пустых фактов; тесты зелёные.

### Шаг 5 — детерминированный fallback `_pick` ✅ снято 10b

- **Цель:** убрать `next(iter(terrain_set))` — порядок set зависит от
  hash → ключ фона недетерминирован между запусками; теперь это вход
  в L2 restore-ветку.
- **Статус:** `resolveForestPlains.py` удалён шагом 10b основного плана;
  фон идёт через `surface_coverage` → `resolve` (детерминированный argmax).
- **ТЗ:** `tz_map_light_bake.md` § Hybrid C (детерминизм bake);
  `project_data_storage_tz.md` § DET-1 дух (воспроизводимость).
- **Контракт:** fallback — `min(terrain_set)` (канонический min, как в
  остальных tie-break); либо фиксированный ключ из реестра. Модуль
  умирает в шаге 10b — правка минимальная, без рефакторинга.
- **Проверка:** два прогона с разным `PYTHONHASHSEED` → один ключ;
  `test_terrain_masks` зелёный.
- **Done:** фон детерминирован.

### Шаг 6 — `BboxShape.area()` и инклюзивный `contains` ✅ вариант a

- **Цель:** устранить рассинхрон: `contains` включает границу
  (покрытие `(dx+1)(dy+1)` клеток), а `area()` возвращает `dx·dy` —
  bbox 1×1 имеет площадь 0 и проигрывает любой другой форме в tie-break.
- **ТЗ:** `tz_map_light_bake.md` § Регионы покрытия › Пересечения и
  приоритет (критерий `area()` — «площадь покрытия», а не геометрия).
- **Файлы:** `backend/app/dataModel/spatial/regionShape.py`,
  `backend/tests/test_region_precedence.py` (или models-тест).
- **Контракт:** `area()` → `(dx+1)(dy+1)` в клетках (или зафиксировать
  в ТЗ «площадь = геометрическая» и оставить; решение — с мастером).
- **Проверка:** юнит — bbox 1×1 не проигрывает по нулевой площади;
  остальные precedence-кейсы без изменений.
- **Done:** семантика area зафиксирована; тесты соответствуют.

### Шаг 7 — `DefaultWhenMissing` на `declared_regions` ✅

- **Цель:** согласовать wire-аннотацию с соседними полями —
  пустой `declared_regions` не должен сериализоваться на wire.
- **ТЗ:** конвенция `WorldTerrainMasks` (`declared_mountains` и др.
  используют `DefaultWhenMissing`).
- **Файлы:** `backend/app/dataModel/terrainMasks/worldTerrainMasks.py`.
- **Контракт:** `declared_regions: DefaultWhenMissing[list[LandcoverDeclareEntry]]`
  (подтвердить поведение дампа: пустой список пропускается).
- **Проверка:** `model_dump` канонического объекта не содержит ключ;
  parse пустого JSON → `[]`; `test_terrain_masks` зелёный.
- **Done:** wire идентичен соседним declared-полям.

## Порядок

1 → 2 → 4 → 5 (код, независимы); 3 — решение мастера по контракту,
может разблокировать/закрыть часть 1–2 дискуссии; 6–7 — однострочные,
в конец.
