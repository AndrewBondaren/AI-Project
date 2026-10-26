# План: техдолг ревью шагов 7+ — wilderness regions

## Контекст

Ревью реализации шагов 7–10c плана
[`wilderness-regions-mechanic.md`](wilderness-regions-mechanic.md)
(`/review-wilderness-7plus`, 2026-10-19). Архитектура в целом
соответствует плану: единая формула membership L0/L2, порядок
paint→hills→hydro, single-writer `StateChangeConsumer`, overlay только
`system_terrain` ниже `patch`, tombstone-подавление, typed `TerrainKey`,
bulkSql в repo — всё подтверждено кодом. Ниже — зафиксированные
дефекты, открытые контрактные вопросы и TODO-записи, решённые мастером
в ревью-чате 2026-10-19.

Связанный документ: [`wilderness-regions-review-debt.md`](wilderness-regions-review-debt.md)
(шаги 0–7). Статус его находок на 2026-10-19:

| Долг 0–7 | Статус |
|---|---|
| #1 кэш `claim_owners` | ✅ закрыт `ClaimOwnersIndex` (`masks/regionRasterizer.py:141`) |
| #2 finePaint restore при пустом collect | ✅ закрыт (`landcover/finePaint.py:131-134,169-173`) |
| #3 merge_rank vs declared | ✅ закрыт — вариант b: `declared` первый элемент `_precedence_key` (`masks/regionPrecedence.py:27,33`) |
| #4 zero-score argmax | ✅ закрыт в коде (`coverageResolver.py:70-76`); write-path охват кандидатов — находка №2 ниже |
| #5 `resolve_forest_plains._pick` | ✅ закрыт — модуль удалён шагом 10b |
| #6 `BboxShape.area()` vs инклюзивный `contains` | ✅ закрыт — вариант a: coverage-клетки (`tz_map_light_bake` + тесты) |
| #7 `declared_regions` без `DefaultWhenMissing` | ✅ закрыт (`worldTerrainMasks.py:116`) |

## Решения мастера (ревью-чат 2026-10-19)

- **child_uid = `parent_region_uid + seed_xy` — принято.** Причина:
  overlapping родители могут содержать один lowland-кластер → `seed_xy`
  без родителя дал бы коллизию двух разных ChildRegion. Формула —
  отдельный источник identity по DET-1. Остаток — TODO-записи T-1, T-2.
- **Проекция hills/eligibility — только при инициализации.** Повторная
  нормализация хранимого реестра не обязана пере-проецировать policy;
  отдельный статус/маркер записи реестра — T-3.
- **`cleanup_orphans` — пока рано** (T-4, debt-note без шага).
- **`seed_root` → `World.seed`** — мировая миграция, отдельный трек (T-5).
- **`REGION_DEGRADED_IDENTITY` — severity по режиму.** validate_only →
  ошибка в отчёте (issue в `ctx.errors`, preview `valid=false`);
  runtime/apply → WarningError в логе, degraded uid принимается без
  reject. Ветка по `ctx.validate_only` в producer'е; severity-флаг и
  отдельный канал warnings не нужны.
- **Состав кандидатов state-change = autoresolve-фильтр.** Consumer
  получает `coverage_registry(..., autoresolve=True)` — тот же фильтр,
  что L0 autoresolve (enabled + autoresolve + alias-dedup +
  `e.eligibility`). Morph-таргеты проходят тот же eligibility-scoring:
  ключ без `eligibility` не выбирается автоматикой ни при генерации,
  ни при state-change.
- **Hydro identity = `water_body_uid` на клетке, не индекс.** Потребность
  в идентичности водоёмов — текущая (consumer: morph→lake materialize,
  см. T-1), включая autoresolve-воду. **Иерархия identity (declared
  имеет наивысшую цену):** declared → `location_uid` (durable);
  event/morph → `region_uid` (durable); procedural autoresolve →
  `auto-{role}-{anchor}` (позиционная, НЕ durable — re-bake
  перевыпускает; persist/`region_states` на неё не опираются, как и
  autoresolve region uid в T-5). `auto-*` стампуется только внутри
  явно включённого мастером autoresolve (`default_*.autoresolve` флаги
  — гейты уже authored); ничего не ставится «просто так». Будущие
  источники воды — разные треки: события (morph→lake через
  `MaterializeSignal`/region state → `region_uid`, T-1) и климат
  (отдельный механик; его identity-контракт определяется при
  появлении трека); ни один не минтует `auto-*`. `index_hydrology`
  удаляется:
  DECLARED-половина — re-derive из POJO, OBSERVED — группировка без
  uid, superseded пер-клеточным uid.

## Карта находок → шаги

| # | Находка | Файлы | Шаг |
|---|---|---|---|
| 1 | `validate_declared_regions` роняет `REGION_DEGRADED_IDENTITY` в validate_only: локальный `ResolveContext` со свежим `report` отбрасывает issue; runtime логирует WarningError, preview возвращает пустой report — режимы расходятся **Верификация 2026-10-19 (impl):** частично снята — в validate_only отсутствие `name` уже отвергает field_validator `RegionSpecBase.name` (`value_error` в preview), ветка `REGION_DEGRADED_IDENTITY` не достигается; остаётся drift ctx (`mode`/`schema_id`/report) и неявный контракт severity. | `jsonValidation/declaredRegions.py:22-26`, `jsonValidation/resolve.py:103-108`, `masks/regionIdentity.py:41-46`, `registries/worldService.py:192-196` | 1 |
| 2 | Zero-score argmax на write-path + нефильтрованный реестр consumer'а: `resolve` по полному реестру мира → entry без `eligibility` всегда кандидаты со score 0 (WarningError «все отпали» недостижим); при пустых фактах в `region_states` пишется `pending_target="farmland"`; ключи с `enabled=false`/`autoresolve=false` и не-landcover ключи — дрейф-таргеты | `regions/coverageResolver.py:52-69`, `regions/stateChange/consumer.py:135-141`, `regions/coverageBackground.py:10-17` | 2 |
| 3 | `index_hydrology`/`hydrology_entries` — мёртвый прогон на каждый `collect` (включая per-tile `paint_regions_fine` и outline render); потребность в hydro-identity реальна (morph→lake), но покрывается `water_body_uid` на клетках (шаг 3), не re-derive индексом без uid — удаление (шаг 4) | `landcover/materializer.py:38,45,86`, `landcover/hydrologyIndex.py` | 3, 4 |
| 4 | `region_states.world_uid` FK без `ON DELETE CASCADE` → delete мира со state-строками = `IntegrityError`; присоединить к WP-DELETE-1 | `db/migrations/0001_initial.sql:815-817`, `registries/worldService.py:153-155` | 5 |

## Шаги

### Шаг 1 — degraded identity: parity preview/runtime — ✅ выполнен (2026-10-19)

- **Цель (урезан после верификации):** явный контракт severity по режиму в producer'е и общий ctx родителя (чинит drift `mode=runtime`/`schema_id` в логе resolve при импорте); наблюдаемое поведение preview/runtime не меняется.
- **ТЗ:** план §5 #7 («draft = ошибка, runtime = fallback + warning»),
  приёмка 10c («`validate_only=true` без `name` → issue», «одинаковое
  решение в обоих режимах»); `docs/tz_json_validation.md` § ResolveContext.
- **Файлы:** `backend/app/application/jsonValidation/declaredRegions.py`,
  `backend/tests/test_declared_region_edit.py` (или JV-тесты регионов).
- **Контракт (решено):** `local` → `regions_ctx.child(index)` — шарит
  report/mode/schema_id родителя (заодно чинит drift `mode=runtime` в
  логе resolve при импорте). В `declared_region_identity` при
  `spec.name is None` — ветка по `ctx.validate_only`:
  `True` → `report_issues` → `ctx.errors` → `ImportValidationError` →
  preview видит ошибку; `False` → `log_issues` → WarningError,
  `ctx.errors` чистый → apply проходит. `prepare_import` и wire-форма
  `ImportValidationReport` не меняются. `REGION_UID_CONFLICT` —
  reject в обоих режимах, без изменений.
- **Проверка:** `POST /worlds/{uid}/regions?validate_only=true` с
  безымянным регионом → issue в `ImportValidationReport`; обычный
  импорт → WarningError + degraded uid, без reject; коллизия имён
  по-прежнему reject; регрессия declared-region тестов.
- **Done:** одинаковое решение в обоих режимах; issue виден в preview.

### Шаг 2 — drift-таргеты: фильтрация + zero-score unresolved — ✅ выполнен (2026-10-19; 2a был в коде, 2b добавлен)

- **Цель:** state-change не выбирает скрытый дефолт и не целится в
  ключи, закрытые policy.
- **ТЗ:** план 5a («все отпали → WarningError, тип не меняется»),
  10b («entry без eligibility не выбирается автоматическим покрытием
  с нулевым score»); `tz_map_light_bake` § Реестр и CoverageResolver.
- **Файлы:** `backend/app/application/worldData/regions/coverageResolver.py`,
  `backend/app/application/worldData/regions/stateChange/consumer.py`,
  `backend/app/application/worldData/regions/coverageBackground.py`,
  тесты `test_coverage_resolver.py`, `test_state_change*.py`.
- **Контракт (две части, обе — после решения мастера):**
  - **2a zero-score:** кандидат с `score == 0` не побеждает → `resolve`
    возвращает `None` + WarningError (тот же путь, что «все отпали»).
    Закрывает долг #4 из `wilderness-regions-review-debt.md` — объединить
    реализацию, не делать два фикса.
  - **2b состав кандидатов (решено):** `_advance` передаёт в `resolve`
    `coverage_registry(self._registry, self._policy, autoresolve=True)`
    — тот же фильтр, что L0 autoresolve; сырой реестр сохраняется для
    `_require_key` и inertia lookups. В ТЗ: morph-таргеты проходят тот же
    eligibility-scoring — ключ без `eligibility` не выбирается
    автоматикой ни при генерации, ни при state-change (morph→`liquid_body`
    требует `eligibility` на целевом ключе либо отдельного контракта).
    Фикстуры morph-кейсов (`test_region_state_change.py` и др.)
    дополняются `eligibility` на целевых записях.
- **Проверка:** юнит — `facts=None` → `resolve=None` + warning;
  `evaluate` на пустых фактах не пишет `pending_target`; disabled-ключ
  не становится таргетом (по выбранному варианту 2b); существующие
  hysteresis/transition кейсы без изменений.
- **Done:** zero-score не пишется в store; состав таргетов зафиксирован
  в ТЗ и коде.

### Шаг 3 — `water_body_uid` на гидро-клетках (identity L0→L2) — ✅ выполнен (2026-10-19; coastline → per-spec carve, при >1 declared coastline геометрия может отличаться от flat-carve)

- **Цель:** каждая водная клетка знает свой водоём. Consumer —
  morph→lake materialize (T-1) и последующие hydro-факты; закрывает
  потребность, которую `index_hydrology` пытался покрыть re-derive'ом
  по ролям без uid.
- **ТЗ:** `docs/tz_terrain_hydrology.md` § C2 (wire-форма
  `map_cells.hydrology` — дописать поле); план §4 шаг 8 уточнение —
  hydro без достоверных UID не превращается в coverage entries;
  теперь UID достоверен (стамп при carve, не угадывание).
- **Файлы:** `backend/app/dataModel/hydrology/mapCellHydrology.py`
  (поле + `.shore()`), `hydrology/load/loadDeclaredHydrology.py`
  (coastline uid), `hydrology/basins/lakeBasinGenerator.py`,
  `hydrology/shore/deepeningBandCarver.py`,
  `hydrology/basins/seaBasinGenerator.py`,
  `hydrology/basins/oceanBasinGenerator.py`,
  `hydrology/autoresolve/proceduralLakeAutoresolve.py`,
  `hydrology/autoresolve/proceduralSeaAutoresolve.py`,
  `hydrology/rivers/riverBedCarver.py`,
  `hydrology/shore/fineHydrologyIndex.py`.
- **Контракт:** `MapCellHydrology.water_body_uid: str | None`
  (`DefaultWhenMissing`, `exclude_none` — миграция не нужна). Стамп при
  carve: declared → `location_uid` (`LakeSpec.location_uid`,
  `RiverSegment.location_uid`; coastline — `declared_coastline_segments`
  из flat `list[segments]` → per-coastline spec с uid, тот же
  паттерн, что `LakeSpec`); autoresolve → `auto-{role}-{anchor}` с
  детерминированным anchor (feature center для бассейнов, source для
  рек, min-cell для морей/океана), **только внутри policy-enabled
  autoresolve-веток**; morph→lake (будущий T-1) → `region_uid`.
  Declared-объект без `location_uid` → fallback `auto-{role}-{anchor}`
  — `water_body_uid` не-None на любой carve-клетке. Иерархия:
  `location_uid`/`region_uid` — durable; `auto-*` — позиционная,
  не durable-ссылка (детерминирована по входам, перевыпускается при
  re-bake). `connection_edge_uid` сохраняется (edge-уровень рек).
  Пропагация без доп. работы: `expand_coarse_hydro_to_tile` копирует
  entry целиком, `sparse_fine_hydro`/`merged_hydro` несут POJO,
  persist — `dump_cell_hydrology`. Light wire
  (`WorldMapCellWire.hydrology_role`/`width`) uid не получает: L2
  читает `surface_planning` (`coarse_hydro` + `sparse_fine_hydro`),
  где uid уже есть; если corridor-путь (`parentLightHydroCorridor`)
  потребует uid — отдельный шаг на wire.
- **Проверка:** юнит — declared lake → клетки несут `location_uid`;
  autoresolve lake → `auto-lake-*`; река → `location_uid` +
  `connection_edge_uid`; persist wire содержит поле; детерминизм
  (два прогона → те же uid); `compileall app`.
- **Done:** все carve-точки стампуют uid; wire-форма задокументирована.

### Шаг 4 — удалить `index_hydrology`/`hydrology_entries` — ✅ выполнен (2026-10-19)

- **Цель:** collect не гоняет мёртвый индекс на каждый
  bake/refine/outline вызов.
- **ТЗ:** план §4 шаг 8 уточнение — superseded шагом 3.
- **Файлы:** `landcover/materializer.py` (поле + reset + вызов),
  удалить `landcover/hydrologyIndex.py`, секция в
  `backend/tests/test_landcover_materializer.py` (прямой вызов).
- **Контракт:** удаление целиком (решение мастера).
- **Проверка:** collect/materialize/outline идентично; регрессия
  landcover тестов.
- **Done:** мёртвого прогона нет; тесты зелёные.

### Шаг 5 — `region_states` в WP-DELETE-1 — ✅ выполнен (2026-10-19, только ТЗ)

- **Цель:** delete мира со state-строками не падает с IntegrityError —
  присоединить таблицу к существующему долгу, не чинить здесь.
- **ТЗ:** `docs/tz_generator_technical_debt.md` § WP-DELETE-1,
  `tz_world_pack_storage` § WP-FIX-DEBT-10.
- **Файлы:** `docs/tz_generator_technical_debt.md` (дописать
  `region_states` в перечень FK-блокеров WP-DELETE-1).
- **Контракт:** только документ; код не меняется до общего фикса
  WP-DELETE-1.
- **Проверка:** ревью мастера на правку ТЗ.
- **Done:** `region_states` зафиксирована в WP-DELETE-1.

## TODO-записи (не шаги; зафиксированы решениями мастера)

- **T-1 Child-region baked reachability.** При подключении
  `MaterializeSignal` → refine morph-child footprint должен штамповать
  `state.region_uid` (= `parent+seed_xy`) в клетки/индекс, иначе его
  state-строка невидима для overlay. Текущие paint-пути выводят uid из
  spec-identity и эту формулу не воспроизводят. При morph→lake carved
  водные клетки дополнительно стампуются `water_body_uid=region_uid`
  (контракт шага 3). Контракт будущего шага morph-materialize — вне
  scope этого долга.
- **T-2 Синк плана по child uid.** Инвариант шага 8 («UID родителя не
  включается в UID саблокации») применим только к autoresolve-
  саблокациям; morph-child — отдельный источник `parent+seed_xy`.
  Уточнить формулировку в `wilderness-regions-mechanic.md` при
  ближайшей правке плана.
- **T-3 Статус/маркер идемпотентности записи реестра.** Мастер:
  проекция `hills`/`eligibility` из `default_landcover` — только при
  инициализации; чтобы re-normalize не принимал проекцию за authored,
  нужен отдельный статус записи реестра (todo мастера, не долг этого
  ревью).
- **T-4 `cleanup_orphans`/`mark_tombstones`.** API есть, потребителей
  нет; tombstone-строки копятся. Решение мастера: «пока рано» —
  подключить при появлении политики очистки (worldEdit/bake hook).
- **T-5 `World.seed`.** `seed_root(world)=str(world_uid)` — интерим
  (`deterministicIds.py:14,175`). Появление seed пересолит
  `seed_*`-потоки (seed/claim/edge/density) → новые seed_xy → новые
  uid autoresolve-регионов/саблокаций, сироты в `region_states`, stale
  membership в pack — мировая миграция уровня re-bake, отдельный трек.
- **T-6 Долг 0–7 закрыт.** Все находки `wilderness-regions-review-debt.md`
  (#1–#7) закрыты в коде — см. таблицу статусов в шапке. Запись
  оставлена как маркер; сам документ-долг можно архивировать при
  следующей правке планов.

## Порядок

1 → 2 (major, независимы) → 3 (hydro identity, medium) → 4 (minor,
независим от 3 — можно параллельно) → 5 (minor, в конец).
