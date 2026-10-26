# Plan: deterministic-ids — единый helper `worldData/ids` — DONE

**SoT:** `docs/project_data_storage_tz.md` § «Детерминированные uid и rng (DET-1)»; правило `.cursor/rules/deterministic-ids.mdc`.
**Связанные ТЗ:** `tz_location_transitions.md` инв. 10; `tz_terrain_relief.md` R15 / R36w (§321, §334, §367); `tz_world_pack_storage.md` job uid; `tz_cascade_context.md` §4.

## Решения (зафиксированы с мастером)

| # | Решение |
|---|---|
| D1 | Connection nodes (`gridLayout`, `areaPaths`, сейчас `uuid4().hex`) → **отдельный типизированный метод** `connection_node_uid(...)`, не голый `entity_uid` на месте |
| D2 | `districtAssembler` rng без `world_uid` в seed (`Random(f"{origin_x}_{origin_y}")`) — **баг**, чинится в шаге planner-rng |
| D3 | Level uid — **одна формула**, ключ `z_offset`. Минтится один раз при генерации; extract не перемонтирует (убрать `level_z|{z}` по абсолютному z) |
| D4 | Building uid — **единая точка минтинга** в `_place_building` через `building_location_uid` (district_uid уже параметр `assemble`); extract не перемонтирует, passage/room uid идут от финального parent |
| D5 | Grade instance/system uid → корень **`world_uid`** (`entity_uid`), не `world_seed` — поправить строку таблицы в SoT |
| D6 | Миграция **атомарно по домену**: шаг = домен (wrappers + все его consumers), не один глобальный проход и не «формула есть, consumers потом» |
| D7 | `world_seed` как значение: колонки `World.seed` нет. Helper принимает `world_seed: str`; провайдер `seed_root(world)` в `ids/` — сегодня `str(world_uid)` (точка для будущей колонки), числовой `seed_int(world)` заменяет `climate/math.py world_seed` |
| D8 | Глобальные библиотеки → **`library_uid` третьим root** в том же helper'е (`uuid5(NAMESPACE_URL)` из building/relief template services переезжает). `uuid4` в chat/player/session/`logMiddleware` — вне скоупа (не generated-сущности мира) |

## Целевой контракт

```text
backend/app/application/worldData/ids/
  uidKind.py            # UidKind StrEnum — закрытый набор тегов
  deterministicIds.py   # entity_uid/entity_rng/seed_uid/seed_rng/library_uid/runtime_uid,
                        # seed_root(world), seed_int(world)
```

- `entity_uid(world_uid, kind, **keys)` / `entity_rng(...)` — идентичность сущностей и rng каскада/генерации.
- `seed_uid(world_seed, kind, **keys)` / `seed_rng(...)` — pack job uid, grade catalog uid, relief pick streams.
- `library_uid(library: LibraryKind, system_name)` — третий root (D8): глобальные template-библиотеки, не world-scoped. `LibraryKind` StrEnum (`BUILDING_TEMPLATES`, `RELIEF_TEMPLATES`, …); canonical `"{library}|{system_name}"` под той же формулой.
- `runtime_uid()` — `uuid4`, только `origin='runtime'` сущности.
- Каноническая строка `"{root}|{kind}|{k}={v}"`, `k` отсортированы; `StrEnum→.value`, `int→str`, tuple→`,`, `None→ValueError`. Хэш `uuid5(NAMESPACE_DNS, canonical)`.
- `UidKind` инвентарь (полный список — приложение А): entity — `DISTRICT, AREA, BUILDING, LEVEL, ENTRY, PASSAGE, ROOM, CITY_NODE, CONN_NODE, TRANSITION, GRADE, GRADE_SYSTEM`; seed — `JOB_TILE, JOB_CHUNK, JOB_TILE_EDGE, GRADE_FACE, GRADE_INTERIOR, RELIEF_PICK, KIND_ROLL, TERRAIN`; rng-параметры — `CASCADE, CELL, TOPOLOGY, BARRIER, FRONTAGE, STRUCTURE, STAIR`.
- Доменные обёртки (`settlementOutdoorUids.*`, `connection_node_uid`, grade-фабрики) остаются — фиксируют обязательные ключи, строку не собирают.

## Шаги

### Шаг 1 — `ids/` helper + `UidKind` + grep-гейт

- **Цель:** существует единственная точка формулы; старый `utils/deterministicIds.py` пока живёт параллельно.
- **ТЗ:** `project_data_storage_tz.md` § DET-1 (контракт функций, нормализация, `runtime_uid`).
- **Файлы:** новый `backend/app/application/worldData/ids/{__init__.py, uidKind.py, deterministicIds.py}`; `backend/tests/test_deterministic_ids.py` — переписан под новый контракт.
- **Контракт:** сигнатуры выше; `UidKind` полный по приложению А.
- **Проверка:** `python -m unittest tests.test_deterministic_ids`; gate-тест сканирует `app/**` на `uuid5(`, `uuid4(`, `Random(f`, `random.seed(`, `hashlib.md5/sha256`-seed паттерны вне `ids/` и whitelist (текущие нарушители заносятся в whitelist с TODO к шагу).
- **Done:** тесты зелёные; gate падает на новом нарушении.

### Шаг 2 — settlement identity domain

- **Цель:** NL-uid (district/area/building/entry/city_node) через `entity_uid`; building uid минтится один раз (D4).
- **ТЗ:** § DET-1; `tz_settlement_outdoor` extract uids.
- **Файлы:** `settlementOutdoor/settlementOutdoorUids.py`, `settlementOutdoorExtract.py`, `assemblers/settlementAssembler/planner/districts.py`, `planner/streets.py`, `areaAssembler/structureAreaAssembler.py` (`_place_building`: `a_uid = area_uid(district_uid, …)` → `location_uid = building_location_uid(a_uid, …)`).
- **Контракт:** `district_location_uid/area_uid/building_location_uid/city_connection_node_uid/entry_uid` → `entity_uid(world_uid, kind, parent=…, …)`; extract берёт `location_uid` из layout, не перемонтирует.
- **Проверка:** unittest по extract (существующие `test_settlement_topology` и пр.); ручной smoke — uid стабилен между generate и extract.
- **Done:** ни одного `_uuid5(`/`det_uuid` в settlement-домене; building uid одинаков до и после extract.

### Шаг 3 — structure generator domain

- **Цель:** level (z_offset), passage, room uid и structure rng через helper (D3).
- **ТЗ:** § DET-1; `tz_location_transitions.md` инв. 10.
- **Файлы:** `generators/structure/structureGeneratorService.py` (`_build_levels` → `level_uid(building_uid, z_offset)`; `_make_seed` → `entity_rng`), `passages/{entry,doorway,archway,staircaseTunnelOrchestrator,shared}.py`, `staircase/{builder,surfaceCorridor,shaftPlacer,uShape/uShape}.py`, `layoutEngine.py`.
- **Контракт:** `level_uid` ключ `z_offset`; passage kinds → `UidKind.PASSAGE` + ключи; `scoped_rng(...)` → `entity_rng(world_uid, …)`.
- **Проверка:** `python -m unittest tests.test_deterministic_ids tests.test_embedded_shaft tests.test_u_shape_facing tests.test_wall_opening_spec` — replay-тесты зелёные (формула новая, значения изменятся — это ожидаемо, фиксируется в шаге 9).
- **Done:** в `generators/structure/` нет `det_uuid`/`scoped_rng`/`md5`-seed.

### Шаг 4 — cascade context rng

- **Цель:** scope/materialize rng каскада через `entity_rng(world_uid, UidKind.CASCADE, scope=…, param=…)`.
- **ТЗ:** § DET-1; `tz_cascade_context.md` §4.
- **Файлы:** `context/locationScope.py` (`make_scope_seed` → helper), `generators/utils/materialResolver.py` (`fold_dominant_material` rng), docstring `context/contextResolver.py`.
- **Контракт:** один rng на scope+param, как сейчас; `make_scope_seed` удалён.
- **Проверка:** `python -m unittest tests.test_context_extend tests.test_cascade_context_baseline` — материализации детерминированы (значения сменятся с новой формулой).
- **Done:** `hashlib`/f-string seed в `context/` и `materialResolver` устранены.

### Шаг 5 — planner / topology rng (включая баг D2)

- **Цель:** все planner-rng на `entity_rng`; `districtAssembler` получает world-root (bugfix).
- **ТЗ:** § DET-1.
- **Файлы:** `generators/coordinates/settlementCellRng.py`, `assemblers/settlementAssembler/planner/{topologyPlan,districts,streets}.py`, `settlementAssembler.py` (barriers), `districtAssembler.py` (`:129`, `:295`), `districtAssembler/planner/{tokens,frontage,buildingCache}` consumers.
- **Контракт:** `settlement_cell_rng` → обёртка над `entity_rng(world_uid, CELL, location=…, x=…, y=…, role=…)`; barrier/topology/frontage — свои `UidKind`.
- **Проверка:** unittest settlement/district тестов; `districtAssembler` seed содержит `world_uid`.
- **Done:** `Random(f` в `assemblers/` устранён.

### Шаг 6 — `connection_node_uid` (D1)

- **Цель:** детерминированные uid узлов графа связей — отдельный метод.
- **ТЗ:** § DET-1; `tz_location_transitions.md` инв. 10 (nodes).
- **Файлы:** новый метод (доменная обёртка, рядом с `settlementOutdoorUids` или свой модуль графа); consumers `road/layouts/gridLayout.py:82`, `areaAssembler/planner/areaPaths.py:50`.
- **Контракт:** `connection_node_uid(world_uid, level, tag, x, y, z) -> str` над `entity_uid(world_uid, CONN_NODE, …)`; убрать `uuid4().hex` и `n_/a_` префиксы.
- **Проверка:** regenerate → те же `node_uid`; unittest графов.
- **Done:** `uuid4` нет в production-коде генераторов.

### Шаг 7 — pack / grade / relief seed domain

- **Цель:** `seed_uid`/`seed_rng` для job uid, grade catalog и relief picks; единые провайдеры seed.
- **ТЗ:** § DET-1; `tz_terrain_relief.md` R15/R36w (§321–334, §367); `tz_world_pack_storage.md`.
- **Файлы:** `dataModel/worldPack/packJobUid.py` (wire-композитор остаётся, кормит `seed_uid`), `pack/bake/macroTileUid.py` (`pack_job_seed` → `ids.seed_root`), `pack/refine/{detailedJobUid,detailedGradeCatalog,detailedGradeFrontUid}.py`, `relief/volume/gradeInstanceFactory.py` (`_uid_digest`, `make_grade_uid`, `make_grade_system_uid`, `make_seeded_uid` → helper; grade uid → `entity_uid` корень `world_uid` — D5), `relief/geom/{bakeSeed,seededHash}.py` (→ `ids.seed_root` / `seed_rng`), `relief/pick/{kindRoll,templatePick,gradeConstrained,ribbonGrade,gradePass}.py`, `climate/math.py::world_seed` → `ids.seed_int`.
- **Контракт:** `site_id`/wire-формат `PackJobUid` не меняется — меняется только источник хэша (`sha256-digest` → `seed_uid` canonical); grade uid → `entity_uid(world_uid, GRADE, site=…, …)`.
- **Проверка:** unittest grade/pack; визуальный контроль, что `PackJobUid` строки в логах читаемы как раньше.
- **Done:** `hashlib` для uid/seed вне `ids/` нет (кроме content_hash integrity — не identity).

### Шаг 8 — `runtime_uid` + `library_uid`

- **Цель:** `origin='runtime'` сущности и глобальные библиотеки через helper (D8).
- **ТЗ:** § DET-1 (`runtime_uid`).
- **Файлы:** `db/repositories/sqlite/chunkRefineJobRepository.py` (job_uid передаёт caller — `runtime_uid()` в `chunkRefineWorker`; db не импортирует `ids/`), `application/worldData/bundleRemapService.py`; `buildingTemplateLibraryService.py`, `reliefTemplateLibraryService.py` (`uuid5(NAMESPACE_URL, …)` → `library_uid(...)`).
- **Решение в шаге (perk/race outlines):** `dataModel/perks|/races/*TemplateOutline.py` — **исключения** (`_EXEMPT`), не `library_uid`: dataModel не импортирует `application/`, а `library_uid` живёт там. Fallback-минт — authored content, не generated identity; `system_name UNIQUE` в `perk/race_templates` защищает от дублей. Риск: re-import uid-less JSON перемонтирует `template_uid` → dangling `world_perks.perk_uid` FK. Если станет критично — минтить `library_uid` в import-слое (application), не в POJO.
- **Контракт:** `library_uid(LibraryKind.BUILDING_TEMPLATES, system_name)`; enum value = `building_templates` → canonical совпадает со старой строкой, но namespace DNS ≠ URL → **uid сменятся** (принято: recreate/реимпорт библиотек в шаге 9).
- **Проверка:** unittest; grep-gate whitelist пуст или содержит только задокументированные исключения.
- **Done:** whitelist закрыт или явно зафиксирован.

### Шаг 9 — cleanup + SoT sync

- **Цель:** старые формулы удалены; доки и recreate зафиксированы.
- **Файлы:** удалить `app/utils/deterministicIds.py`, `make_scope_seed`, `_make_seed`, `_uid_digest`/`make_grade_uid`/`make_seeded_uid`, `seededHash` (если поглощён), `bake_seed`/`pack_job_seed` (если переехали); `test_deterministic_ids.py` финальный; `project_data_storage_tz.md` § DET-1 — grade uid → `world_uid` (D5), статус «реализовано»; правило `deterministic-ids.mdc` без «→ переехать».
- **Проверка:** полный unittest прогон; grep-gate; инструкция мастеру: recreate SQL + пересборка pack (все uid сменились).
- **Done:** один модуль формулы; доки синхронны; план → `-done`.

## Приложение А — инвентарь текущих тегов (для `UidKind`)

| Текущий тег/строка | Файл | Новый kind + ключи |
|---|---|---|
| `district\|{name}\|{i}` | settlementOutdoorUids | `DISTRICT`, parent=settlement, name, index |
| `city_node\|{tag}\|{x}\|{y}\|{z}` | settlementOutdoorUids | `CITY_NODE`, parent=settlement, tag,x,y,z |
| `area\|{min_x}\|{min_y}\|{facing}` | settlementOutdoorUids | `AREA`, parent=district, min_x,min_y,facing |
| `building\|{tpl}\|{x}\|{y}` | settlementOutdoorUids | `BUILDING`, parent=area, template,map_x,map_y |
| `level_{z}` / `level_z\|{z}` | structureGeneratorService / extract | `LEVEL`, parent=building, z_offset (D3) |
| `entry{suffix}`, `entry\|{role}\|{passage}` | passages/entry, settlementOutdoorUids | `ENTRY`/`PASSAGE`, parent=building, role/passage |
| `door`, `arch`, `archway`, `surface_corridor`, `underground_tunnel`, `stair` | passages/*, staircase/* | `PASSAGE`, parent=building, kind, from,to |
| room `{uid_key}` | structureGeneratorService | `ROOM`, parent=building, key |
| `fr_anchor`, `embed_at`, `embed_entry`, `AttachWall` | uShape, shaftPlacer, layoutEngine | `STAIR`/`STRUCTURE` rng, parent=building, staircase/room, tag |
| `{world}_{loc}_{x}_{y}_{role}` | settlementCellRng | `CELL` rng, location, x, y, role |
| `{world}_{loc}` topology; `…_barriers`; frontage tie | topologyPlan, assemblers, frontage | `TOPOLOGY`/`BARRIER`/`FRONTAGE` rng |
| `{world}_{scope}_{param}` md5 | locationScope, materialResolver, structureGeneratorService | `CASCADE`/`STRUCTURE` rng, scope, param |
| `n_{x}_{y}_{z}_{uuid4}`, `a_{tag}_…_{uuid4}` | gridLayout, areaPaths | `CONN_NODE`, level, tag, x, y, z (D1) |
| `world_seed\|tile:{gx},{gy}\|…` | PackJobUid consumers | `JOB_TILE`/`JOB_CHUNK`/`JOB_TILE_EDGE` — wire SoT PackJobUid, хэш `seed_uid` |
| sha256 `world_seed\|site` face/interior | gradeInstanceFactory, catalog | `GRADE_FACE`/`GRADE_INTERIOR`, site |
| sha256 `world_uid\|site\|x,y` grade | gradeInstanceFactory | `GRADE`, site, seed_cell — корень `world_uid` (D5) |
| `world_uid\|grade_system\|site` | gradeInstanceFactory | `GRADE_SYSTEM`, site — корень `world_uid` (D5) |
| `{seed}\|relief_pick\|{ctx}\|{site}`, kindRoll key | templatePick, kindRoll | `RELIEF_PICK`/`KIND_ROLL` rng |
| md5 `world_uid` int | climate/math, noise | `seed_int(world)` — не uid, числовой seed |
| transition (будущий) | tz_location_transitions | `TRANSITION`, parent, a, b, type |
| `uuid5(NAMESPACE_URL, "{lib}\|{name}")` | building/reliefTemplateLibraryService | `library_uid` — не UidKind, отдельный `LibraryKind` (D8) |
