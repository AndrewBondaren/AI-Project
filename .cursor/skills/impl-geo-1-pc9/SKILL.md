---
name: impl-geo-1-pc9
description: "Имплементирует PC-9 плана geo-1-designed-water.md: surface caller cutover, compatibility shim, publication guard и cleanup PC-8C/PC-9A. Использовать по команде /impl-geo-1-pc9."
triggers: [user]
---

# Имплементация GEO-1 PC-9

Вызов `/impl-geo-1-pc9` — явная просьба реализовать **только PC-9** согласованного плана. Подготовка или редактирование этой команды сама по себе не разрешает реализацию.

Ты новый агент: не полагайся на память предыдущих сессий. Сначала прочитай SoT, сверь текущий код, затем выполняй шаг. Все пути ниже — от корня репозитория.

## Прочитать до первой правки

1. `.cursor/plans/geo-1-designed-water.md` — единственный SoT реализации: §5.4, §6.26–6.28 (особенно проверки §6.27), §6.31-E/F (bindings, activation/caller ledger), §6.33 (SurfacePlanSlot), §7 PC-9 целиком, evidence PC-8C и PC-9A **вместе с review correction**. Проверить приёмку входов: PC-9A помечен IMPLEMENTED / VERIFIED, но ожидает приёмки мастером; если она не подтверждена, сначала запросить подтверждение, не считать VERIFIED равным ACCEPTED.
2. `docs/tz_terrain_generation.md` — §Surface planning/cache и §PC-D1; `docs/tz_map_light_bake.md` — §compose. Уточнить нормативные ссылки PC-0 и требования публикации по ссылкам плана.
3. `.cursor/rules/code-gates.mdc`, `layer-boundaries.mdc`, `contract-creation.mdc`, `dataModel-no-hardcode.mdc`, `folder-composition.mdc`, `class-size-limit.mdc`, `project-context.mdc`, `runtime-world-edit-policy.mdc`.
4. Текущие composition, contracts, encoding и guards в `backend/app/application/worldData/planning/`; frozen declarations в `backend/app/dataModel/surfacePlanning/`; текущие caller/DI seams из ledger §6.31-F.

Противоречие план ↔ ТЗ ↔ код, отсутствие точного владельца/пути нового класса или несогласованная смена контракта — блокер. Не исправлять архитектуру молча: изложить расхождение и согласовать поправку к плану. До новых файлов посчитать непосредственные файлы в затрагиваемых папках, выдать WARN для >5, не расширять папки с >10 без согласованной композиции.

## Scope и готовые входы

Только **PC-9 — cutover surface caller, compatibility entry и publication guard**. PC-10 (L0 frozen consumer cutover), PC-11 (L2 consumer cutover), PC-12 и GEO-1 algorithms не выполнять.

PC-9A уже предоставляет assembler, capture, bundle, bindings, codec и source revision helper. Сверять актуальные пути после review correction: codec/manifest — `planning/encoding/`, revision guard — `planning/guards/sourceRevision.py`; не возвращать их в composition/capture и не создавать второй SoT bindings.

Generic `application/planning/` остаётся domain-neutral. Providers — тонкие boundary-адаптеры, domain kernels сохраняют владельцев. Layout/ref и materialization не смешивать; cutover не повод переносить placement/policy решения в shim или routes.

## Обязательный объём PC-9

### 1. Caller cutover и DI

- `generators/terrain/passes/surfaceTerrainContext.py` становится compatibility re-export/delegation к `SurfacePlanningAssembler.prepare`, не вторым coordinator.
- `prepare_surface_terrain_context`/`require` получают обязательные keyword-only `planning` и `capture` по §6.27/§6.31-F. `hydrology_generator` удаляется; `nodes`/`edges` — compatibility-only. Сохранить None extent и ValueError у require.
- Обновить все internal callers/test doubles атомарно по ledger: `materialize/terrainBatchOrchestrator.py::plan_bootstrap_tiles`; `materialize/worldSurfaceMaterializationOrchestrator.py::{plan_bootstrap_tiles,materialize_pack_detailed}`; `pack/bake/packMaterializationOrchestrator.py::_materialize_l0_pack`; `pack/bake/worldMapBakeOrchestrator.py::{bake_tiles,bake_tile}`; `pack/bake/packCompletenessClassifier.py::classify`; `pack/read/wildernessRegionReadService.py::outline`; три direct require calls в `backend/app/api/routes/map.py`.
- DI transit: `backend/app/core/container/{worldData,packs}.py`, `pack/read/packReadServices.py::build_pack_read_services`, `pack/read/packLoadingProgressFacade.py`. Использовать существующий Container lifetime: один CacheService/MemoryCache/PlanRegistry/PlanningService/assembler/capture на process; подключить shutdown build control к container lifecycle. Explicit cache policy values брать из согласованного контракта, не выдумывать defaults.
- Routes — только передача injected dependencies, без route-local build/cache. Один request ResolveContext/report boundary, одна captured source view. Совместимость artifact refs проверяется по A05: fingerprints разных доменов не обязаны совпадать с общей source revision.

### 2. Publication guard — строго согласованный контракт

Новый collaborator: `backend/app/application/worldData/planning/guards/sourcePublication.py` (guards 2→3 по плану; перепроверить фактическое число).

`require_fresh(captured: SurfacePlanningView, *, mode, mountain_templates, resolve_ctx) -> World` перечитывает world row + named_locations через repositories, выполняет re-capture и `require_current_source(captured, current)` из `guards/sourceRevision.py`. Сам не открывает transaction и не пишет SQL. Mountain templates — frozen caller input, template store не входит в re-read scope. Карту класса/зависимостей сверить с планом до реализации; недостающую карту сначала согласовать.

Порядок: **capture → bake без лока → caller transaction_if_needed {re-read → re-capture → check → publish}**. Нельзя держать BEGIN IMMEDIATE на весь bake; child tasks не наследуют txn-флаг GuardedConnection.

- L0: внутри существующей transaction_if_needed непосредственно перед `finalize_pack_on_world` выполнить `guard.require_fresh`, затем finalize.
- Detailed: вынести `recalc_manifest_counters`/`save_manifest` из `PackDetailedBakeOrchestrator.bake` в owner `WorldSurfaceMaterializationOrchestrator`. Bake пишет blobs и возвращает; owner делает `{require_fresh → recalc + save_manifest}` внутри своей transaction_if_needed.
- `PackMaterializationOrchestrator` получает INamedLocationRepository (+ guard); `WorldSurfaceMaterializationOrchestrator` — db + guard. Captured view передаётся от entry до публикации через injected capture, не через legacy ctx.
- Stale source: SurfacePlanningStale наружу, rollback без публикации и без auto-retry. Уже записанные pack files могут остаться до overwrite следующим bake; не добавлять удаление файлов или rollback filesystem без отдельного согласования.

### 3. Обязательные cleanup-долги этого шага

- PC-8C: убрать lazy import `build_local_plan_from_coarse` в `ClimateLocalPlanProvider.build`; вынести base pole helpers из provider module либо удалить legacy chain по карте плана. Итоговый импорт top-level, без обхода цикла через другой lazy import.
- PC-9A: отделить transitional `SurfaceTerrainContext` от frozen contracts; убрать generator imports ClimatePoleField/ClimateAnchorField/SurfaceHeightmap из `contracts/surfacePlanningView.py`. Сохранить **единственное определение**, old type import identity и восьмиполевой public API. `to_legacy_context` остаётся module-level adapter. Если точный путь вынесенного контракта/нового helper не задан — сначала согласовать карту, не выбирать её во время написания кода.

## Проверки и Done

Использовать реальные команды из §6.27 и существующих configs, не угадывать имена test modules. По возможности сначала добавить регрессионные тесты, демонстрирующие проблему, затем реализовать.

Проверить:

- old/new entry equivalence, old type import identity, None/require semantics и mutable working-view isolation;
- production callers проходят через одну boundary; legacy shim/guard не содержат direct climate/hydro/relief planning;
- edit → replan только affected closure; stale aggregate не выдаётся за current;
- stale source → SurfacePlanningStale → rollback **без publish** отдельно для L0 и detailed; fresh source → check и publish в одной UOW; no-writes validation;
- DI singleton lifetime, shutdown и обязательные cache policies; не создан второй активный orchestration path;
- suites consumers/contracts/providers/cache/encoding и затронутые regressions; pyright valid0, negative exact code+location по действующим configs;
- folder counts, тела классов ≤300 строк, отсутствие generator imports в frozen view и lazy import долга PC-8C.

Не стартовать backend, не менять DAG-ноды, не менять SQL-schema, не коммитить и не применять разрушительные операции. City/location caches не трогать. Не обходить permissions/configuration проблемы: сообщить мастеру и запросить помощь.

После успешных проверок обновить DONE/evidence **только PC-9** в существующем плане: файлы, ответственность/размеры классов, folder counts, команды и результаты. Не объявлять весь GEO-1 план завершённым и не переименовывать его в -done. Отчёт: сделано / файлы / проверки / оставшиеся блокеры, затем ждать «ок»; PC-10 автоматически не начинать.
