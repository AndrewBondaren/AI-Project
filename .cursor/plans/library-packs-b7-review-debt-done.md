# План: техдолг ревью шага B7 (5b) — schema/legacy cleanup — ✅ DONE 2026-10-15

## Контекст

Ревью коммита `56b0164` — шаг **B7** плана
[`domain-template-libraries-5b-implementation-done.md`](domain-template-libraries-5b-implementation-done.md):
колонки `building_template_registry` / `relief_template_registry` сняты
(SQL `0001_initial.sql` + `World` dataclass + `WORLD_SLICES` + accessors
`worldRow` + POJO-реестры); flat-секции bundle обслуживает
`import_libraries`; `removed_uids` снят из контракта адаптеров;
`remap_pins` → return-new; `_write_provider` / `._fs_writes` больше не
читаются снаружи (инъекция provider + публичный `import_path`).

Оси ревью: хардкоды · класс = одна ответственность · метод = одна зона ·
неявные зависимости. Контракт шага соблюдён; блокеров нет. Ниже —
дефекты чистоты и один структурный вопрос (шаг 1).

Проверки каждого шага: `python -m unittest` из `backend/`.

## Карта находок → шаги

| Находка | Файлы | Шаг |
|---|---|---|
| `ReliefBodyPreparation` — два construction site: модульные `_PREPARATIONS` всегда строят `world_import=None` → при `world is not None` каждый member на каждый `load_relief` шлёт `WORLD_IMPORT_UNWIRED`; barrier/canal-проверки на read-path структурно недостижимы; поведение класса зависит от того, кто его сконструировал | `templateGraphValidation.py:27`, `legacyDomainSplit.py:23`, `domainAdapters/relief.py:54-85,99`, `templateSnapshotLoader.py:93` | **1** |
| `report_issues(ResolveContext(), …)` — throwaway ctx ради log side-effect; issue пишется в отчёт, который тут же выбрасывается | `domainAdapters/relief.py:77`, `templateSnapshotLoader.py:97` | **2** |
| `_SYSTEM_NAME_FIELD` — private-имя как межмодульная константа (импортируют 4 модуля) | `domainAdapters/contract.py`, `bodyPreparation.py`, `relief.py`, `templateBodyAdapter.py`, `structure.py` | **3** |
| `consumed = {PLOT_TEMPLATES, BUILDING_TEMPLATES}` — дубль литерала в двух `except`; неявное знание «relief/structure handlers больше нет» | `worldBundleService.py:185,188` | **4** |
| `preparation` — instance-attr у relief vs class-attr у plot/building; следствие construction-split | `relief.py:99` vs `plot.py:34`, `building.py:16` | **1** |
| Doc drift: `WorldBuildingTemplateRegistry` ещё в тексте ТЗ | `docs/tz_building_generator.md:1385`; `tz_generator_technical_debt.md` (строка CITY-T-2b) | **5** |

## Закрыто B7-свипом (verified, из `library-packs-b6-review-debt-done.md`)

- **Шаг 0** `removed_uids` — снят из `PackDomainAdapter.prepare_world_refs`,
  всех реализаций и `WriteRetentionPlanner._world`.
- **Шаг 2** — `ReliefWorldImportService` получил собственный
  `write_provider` (не `self._library._write_provider`); `LibraryPackService.import_path`
  стал публичным, `._fs_writes` снаружи не читается.
- **Шаг 3** — литералы `'system_name'` в domainAdapters заменены на
  `_SYSTEM_NAME_FIELD`; остаток — rename приватного имени → шаг 3 здесь.
- **Шаг 4** — `_LOCATION_REF_KINDS` слит в `refFields.LOCATION_TEMPLATE_REF_KINDS`,
  `LOCATION_TEMPLATE_REF_FIELDS` derive из неё.
- **Шаг 6** — `ReliefBodyPreparation.validate_world` делегирует
  `world_import` по паттерну `PlotBodyPreparation`; адаптер тонкий.
  Породило находку шага 1 (unwired `_PREPARATIONS`).
- **Шаг 8** — `remap_pins` return-new, все call-site присваивают
  (`relief.py`, `structure.py`, `templateBodyAdapter.py`).

Остаются из B6: шаг 7 (`WriteRetentionPlanner.finish` зоны), шаг 9
(хардкоды — частично в работе), шаг 10 (валидаторы
`ReliefWorldImportService` — было отложено до завершения B7, теперь
разблокировано).

## Вне scope (не долг этого коммита)

- `.agents/skills/source-command-impl-5b-b7/SKILL.md` внутри
  code-коммита — процессная заметка, не код.
- `import_libraries` (`worldLibraries.py`) — многозонная функция,
  до-коммитная; отдельный должник при желании.
- `BuildingCatalog.prefer_subjects` читает `entry.body.subjects` — поля
  нет на `BuildingBodyTemplate` (`extra="ignore"`); до-коммитное,
  проверять при первом реальном обращении.

## Шаги

### Шаг 1 — world-checks только на write-path (вариант B) ✅ 2026-10-15

Выполнен: `ReliefBodyPreparation` stateless (`__init__`/`_world_import`/
override `validate_world` удалены; generic `validate_prepared_source`
из базы сохранён на обоих путях). `ReliefPackAdapter`: `preparation =
ReliefBodyPreparation()` — class-attr; `prepare_body` при
`world is not None` дёргает `self._world_import.validate_world_refs`
(`ReliefValidationError` → `RELIEF_WORLD_REFS` с member-path).
Unwired write-path — один `logger.warning("packs | …")` на adapter
instance (`_unwired_warned`): на seam нет `ResolveContext`, поэтому
доменный log-route вместо throwaway ctx (см. шаг 2). `WORLD_IMPORT_UNWIRED`
удалён целиком; `reliefWorldImportService.validate_world_refs` docstring
обновлён. Проверка: `test_template_domain_*` 100/100,
`test_library_packs_*` 221/221, в логе 0 `WORLD_IMPORT_UNWIRED`
(было ~10 per-member строк).

- **Цель:** `ReliefBodyPreparation` снова stateless — поведение не
  зависит от construction site; read-path пропускает world-checks
  явно, без `WORLD_IMPORT_UNWIRED`.
- **ТЗ:** [packs §5/§7](../../docs/tz_template_library_packs.md);
  `layer-boundaries`; `tz_logging` (маршрут, не `getLogger` напрямую).
- **Файлы:** `domainAdapters/relief.py`; `_PREPARATIONS`
  (`templateGraphValidation.py`, `legacyDomainSplit.py`) — только
  проверка, что форма не сломана.
- **Контракт (B):**
  - `ReliefBodyPreparation.__init__` без `world_import`; метод
    `validate_world` на relief-уровне удаляется — preparation делает
    только схему + каналы (`super` в базе) + `warn_template_invalid_geom`.
  - Barrier/canal world-refs — на `ReliefPackAdapter.prepare_body`
    (write seam): после `super().prepare_body(...)` при
    `world is not None` → `self._world_import.validate_world_refs(world,
    body)`; unwired на write-path — одна диагностика через
    `report_issues` с настоящим ctx (решение B6: warning, не silent skip).
  - `preparation` возвращается к class-attr (`= ReliefBodyPreparation()`)
    — единообразие с `PlotPackAdapter`/`BuildingPackAdapter`.
  - `templateGraphValidation` остаётся pure: read-path вообще не знает
    про `ReliefWorldImportService`.
- **Проверка:** `python -m unittest discover -s tests -p "test_library_packs_*.py"
  tests.test_template_domain_preparation tests.test_template_domain_canonical`;
  smoke `load_relief` — 0 `WORLD_IMPORT_UNWIRED` в логе.
- **Done:** `WORLD_IMPORT_UNWIRED` не существует; `ReliefBodyPreparation()`
  конструируется без аргументов на всех site'ах; world-checks reachable
  только через write-адаптер.

### Шаг 2 — `report_issues` без throwaway ctx ✅ 2026-10-15

Выполнен шире заявленного: в `resolve.py` выделен `log_issues` —
log-половина `report_issues` (dedupe + `json_validation | WarningError`
route), `report_issues` делегирует ей. Все пять сайтов pure-log паттерна
переведены: `templateSnapshotLoader._prepare`,
`referenceResolver.member_usages`, `packScope.diagnose_missing`,
`writeService._prepare` ×2. На seam'ах ctx не существует — честный
log-route вместо фиктивного. Grep `report_issues(ResolveContext(` —
0 по всему backend (критерий был scoped на libraryPacks + loader).
Проверка: `test_library_packs_*` 221/221; `json_validation | WarningError`
строки видны в логе с прежним форматом.

- **Цель:** диагностика либо доходит до отчёта caller'а, либо явно
  логируется; `ResolveContext()` не создаётся ради side-effect.
- **Done:** issue не теряется молча и не живёт в выброшенном ctx.

### Шаг 3 — `_SYSTEM_NAME_FIELD` → публичное имя ✅ 2026-10-15

Выполнен (одна ветка, координация не нужна): `SYSTEM_NAME_FIELD` в
`contract.py` + 4 импортёра. По тому же критерию сняты ещё два
`_`-символа, пересекающих границу модуля: `_LibraryBodyMixin` →
`LibraryBodyMixin` (`mixins.py` → `structure.py`,
`templateBodyAdapter.py`), `_remap_relief_pick_policy` →
`remap_relief_pick_policy` (`remapRefs.py` → `relief.py`).
Проверка: compileall + import smoke OK; `test_library_packs_*` —
221/221 OK. Остаток `_MemberOps`/`_PackOps`/`_PackScope`/`_coerce_kind`
(packService ↔ ops-модули) — до-коммитный package-internal паттерн
вне domainAdapters, отдельный должник при желании.

- **Цель:** константа не объявляет ложный module-private scope.
- **Done:** ни один модуль domainAdapters не импортирует `_`-символ
  из соседнего модуля.

### Шаг 4 — consumed-fallback: одна декларация ✅ 2026-10-15

Выполнен: `LIBRARY_CONSUMED_SECTIONS = frozenset(kind.value for kind in
TEMPLATE_KINDS)` рядом с `FLAT_KINDS` в `worldLibraries.py` (derive из
единственной декларации claim'а `import_libraries`; покрывает оба пути —
migration и non-migration). Обе `except`-ветки `_prepare_bundle`
используют её. Побочный эффект: relief/structure теперь тоже помечаются
consumed на error-path — корректно, т.к. у pack-доменов handlers нет
(`bundle/order.py`), а если появятся — двойной валидации не будет.
Проверка: `test_bundle_archive_routes` + `test_import_validation_policy`
— 19/19 OK.

- **Цель:** множество flat-секций, съедаемых `import_libraries`, —
  одно имя; связь с handler-set видна из кода.
- **Done:** литерал один; читателю не нужно знать про отсутствие
  handlers из головы.

### Шаг 5 — doc sweep (текстовый) ✅ 2026-10-15

Выполнен: `tz_building_generator.md` (§5.2 union-POJO → история),
`tz_terrain_relief.md` (R11 таблица + колонки мира — cutover B7),
`tz_structure_connections.md` ×3, `tz_city_generation.md` ×2,
`tz_locations.md` ×3 (таблица + tier_range + секция → библиотека),
`tz_economic_tier.md`, `tz_lighting.md`, `tz_architectural_style.md`,
`tz_assembler_hierarchy.md`, `tz_pojo_city_typing.md`,
`tz_generator_technical_debt.md` (NC-8 сужен + CITY-T-2b аннотация),
`tz_city_generation_technical_debt.md` (аннотация). Остаток grep —
только strikethrough/done/`v1_superseded`/история.

- **Цель:** термины удалённых POJO в docs — только как история.
- **Done:** grep `building_template_registry`/`relief_template_registry`/
  `World*TemplateRegistry` по `docs/` — только пометки «удалён B7»,
  зачёркнутый текст и superseded-документы.

## Порядок и зависимости

Шаг 5 — текстовый, первым. Шаги 3, 4 независимы (3 — после/вместе с
текущим sweeep хардкодов B6-шаг-9). Шаг 1 → шаг 2 (общие файлы).
После шага 1 разблокирован B6-шаг 10 (вынос `_validate_structure_*` из
`ReliefWorldImportService` — валидатор переиспользуется preparation без
обхода ctor).
