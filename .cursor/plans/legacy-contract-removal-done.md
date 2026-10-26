# DONE — Legacy contract removal — срезка старого формата после конвертации фикстур

**Решение (мастер):** legacy-контракты нужны только для старых фикстур; фикстуры
переводятся на новый формат; legacy-механизм удаляется. Transitional read
flat-JSON bundle (`tz_template_library_packs.md` §4.2) отменяется: плоские
секции и старые wire-ключи становятся ошибкой импорта, а не входом миграции.

## Граница трека

**Входит:** формат данных на входе (flat body-секции, registry pointer-колонки
в bundle `world`, wire-алиасы чтения, old→new UID-карта, world-owned `legacy`
pack как конструкция миграции).

**Не входит** (отдельные долги, не про формат): debug read-path `map_cells`
(`LegacyMapGridRender`, `MapCellService.save_generated`, `bootstrapMapCellWriter`
DeprecationWarning), deprecated имена кода (`footprint_*` aliases,
`RecalcTrigger`, `WorldPerk` class name), алгоритмические legacy (`seed_int`
md5, `make_grade_uid`, v1 Voronoi CL-8, `terrain_shore` lore-запись,
`is_macro_grid_coord`), RELIEF-TD-4 leftover-стек для locked-тестов.

**Не legacy вообще** (не трогать): `packs/write/writeFacade.py` и
`write/domainWriteEntry.py` — живой API-фасад поверх L-4, слово «legacy» в
docstring означает pre-L-4 сигнатуры; `fixtures/templates/*.json` — canonical
source plot-пака в **новом** формате; `structures_templates/base`,
`relief_templates/smoke_003` — уже UID-layout; `fixtures/packs/*.wpack` —
новый формат архива.

## Верифицированный инвентарь legacy-входа в fixtures

| Фикстур | Legacy-вход |
|---|---|
| `world_test_gen_003.json` | flat `relief_templates` (4 body); pins уже на `legacy_member_uid(world-test-003)`; dict-map `location_type_registry` + `display_name` |
| `world_template.json` | `default_plains`/`default_forests`; dict-map `location_type_registry` + `display_name`; dict-map `climate_zone_registry` |
| `world_terrain_test.json` | `default_plains`/`default_forests`; dict-map `location_type_registry` + `display_name`; dict-map `climate_zone_registry` |
| `world_test_all.json` | dict-map `location_type_registry` + `display_name`; dict-map `climate_zone_registry` |
| `world_test.json`, `world_test_002.json`, `world_test_gen_noloc.json` | dict-map `location_type_registry` + `display_name` |
| `_smoke_races.json` | `race_uid` → `template_uid` |
| Остальные (`world_test_gen_003` pins, `world_landcover_*`, `world_defaults_test`, `character_test`, `seed*`, `_smoke_*`) | уже новый формат / вне scope |

Sweep-ключи для повторной проверки: `system_template_uid`,
`*_template_registry` в `world`, flat `plot/building/structure/relief_templates`,
`default_forests|default_plains`, `climate_tier|"tier"`, `perk_uid|race_uid|
display_race` (только race/perk template bodies — `character_test.display_race`
это поле персонажа, не алиас), `trapdoor`, `terrain_resample`,
`shoulder_width_cells`, UID-литералы из `uidMap` (STRUCTURE_MEMBER_RENAMES,
RELIEF_SMOKE_003_FORMER_UIDS), dict-map форма реестров.

## Решения (приняты мастером 2026-10-18)

- **D1 — `POST /worlds/{uid}/relief-templates/import` (body variant):**
  **reject loose bodies.** Оставить только `template_uid` instantiate;
  `ReliefWorldImportService` и loose-path удалить. Адресный импорт
  одиночного шаблона в пак — отдельные engine-входы `write_authored_bodies`
  с обязательным `pack_uid` (`POST /relief-templates[/import]`).
- **D2 — reject-валидаторы удалённых ключей** (`_reject_legacy_body_wire`,
  `reject_removed_shoulder_width`, `InteriorTransitionsRebuildRequired` и пр.):
  **оставить как strictness-guard** — старый ключ даёт явную ошибку, а не
  молчаливый игнор при `extra="ignore"`.
- **D3 — имя пака в `world_test_gen_003`:** **чистое имя** — пересчёт
  member uid через `library_uid` + rewrite `library_pins`.

**Статус:** шаги 0–4 DONE (вкл. расширенную пачку алиасов: `building_template`,
`structure_counts|priority`, `width_m|depth_m` slot, `title|content` lore,
`description`→`system_description` NL, `map_cell_size_m|cell_size_m` manifest +
`normalize_world`, `state_fingerprint`); шаг 5 DONE; шаг 6 — финал.
- **D4 — `races`/`perks` transitional alias:** **срезать в этом треке**
  (шаг 4).

## Шаг 0 — ТЗ sync (только документы)

- **Цель:** зафиксировать отмену transitional read и `legacy` pack до кода.
- **ТЗ:** `docs/tz_template_library_packs.md` §1.1 (legacy pack = destination),
  §4 «Legacy fixtures/bundle» (~632), §4.2 (~820 transitional read);
  `docs/tz_world_bundle.md` — блок А0 (~20–33), уточнение B7 (~144–150),
  таблица секций (~158–180), roadmap (~412); `docs/tz_domain_template_libraries.md`
  §6 «Recipe refs, legacy и migration» (~150–185).
- **Файлы:** перечисленные `docs/tz_*.md`.
- **Контракт:** flat body-секции и registry pointer-колонки — ошибка импорта;
  доступность = membership в паке; тело без пака не принимается; решения
  D1–D4 вписаны в ТЗ.
- **Проверка:** ручное ревью диффа; ссылки из правил/планов не битые.
- **Done:** ТЗ больше не описывает legacy-вход как допустимый.

## Шаг 1 — конвертация fixtures

- **Цель:** ни один файл в `fixtures/` не требует legacy-чтения.
- **ТЗ:** `tz_world_bundle.md` (форма секций/registries), `tz_template_library_packs.md`
  §4.2 (library_packs layout), `tz_locations.md` (location_type_registry
  канон: list + `display_type`), `tz_terrain_generation`/`tz_map_light_bake`
  (`default_landcover`).
- **Файлы:** `fixtures/world_test_gen_003.json`, `world_template.json`,
  `world_terrain_test.json`, `world_test_all.json`, `world_test.json`,
  `world_test_002.json`, `world_test_gen_noloc.json`, `_smoke_races.json`.
- **Контракт:**
  - flat `relief_templates` в `world_test_gen_003` → `library_packs` запись
    (manifest + bodies; имя пака по D3; member uid пересчитать через
    `library_uid`, pins обновить соответственно);
  - `location_type_registry` dict-map → list, `display_name` → `display_type`
    (только location_type/subtype записи — `display_name` в материалах/lore
    остаётся каноническим полем);
  - `default_plains`/`default_forests` → `default_landcover`
    (`LandcoverRegionsCategoryPolicy` wire);
  - `climate_zone_registry` dict-map → list;
  - `race_uid` → `template_uid` в `_smoke_races.json`.
- **Проверка:** `.\.venv\Scripts\python.exe -m unittest tests.test_fixture_bundle_import
  tests.test_terrain_masks tests.test_landcover_cutover tests.test_import_validation_policy
  tests.test_declared_river_topology` — зелёный при **ещё живом** legacy-коде
  (конвертированные фикстуры должны проходить и по canonical, и по legacy-пути
  чтения, порядок шагов 1→2 безопасен).
- **Done:** sweep-греп по fixtures по ключам из инвентаря — 0 совпадений.

## Шаг 2 — срезка входа worldBundle

- **Цель:** импорт не читает flat-секции и pointer-колонки.
- **ТЗ:** `tz_world_bundle.md` §A0/§B7 после шага 0; `tz_template_library_packs.md` §4.
- **Файлы:** `application/worldBundle/legacyTemplateBodies.py` (delete),
  `worldBundle/worldLibraries.py` (flat-ветки `import_libraries`,
  `LIBRARY_CONSUMED_SECTIONS` → flat-ключи = ошибка, не consumed),
  `worldBundleService.py` (`_prepare_bundle`: без `extract_legacy_world_input`,
  `legacy=` threading, `_cleanse_consumed_rows`), `worldBundle/worldCopyImport.py`
  (param `legacy`), `core/container/worldBundle.py` + `templateLibrary.py`
  (`legacy_world_migration()` wiring).
- **Контракт:** `import_libraries(data)` без `legacy_migration` флага; плоские
  ключи доменов → `ImportValidationError` с path секции; `library_packs` остаётся
  единственным входом библиотек.
- **Проверка:** `python -m unittest tests.test_fixture_bundle_import
  tests.test_bundle_library_archive tests.test_template_domain_archive`;
  `python -m compileall app`.
- **Done:** grep `legacy` в `worldBundle/` — только удалённые; импорт
  конвертированного `world_test_gen_003` проходит без flat-входа.

## Шаг 3 — удаление `packs/legacy/` и `uidMap`

- **Цель:** исчезает весь migration-модуль и one-shot UID-карта.
- **ТЗ:** `tz_template_library_packs.md` §1.1/§4 после шага 0; D1 зафиксирован.
- **Файлы:** `application/templateLibrary/packs/legacy/*` (12 файлов, delete),
  `packs/uidMap.py` (delete), `packs/packService.py` (`import_legacy_bodies`),
  `reliefWorldImportService.py` (fate по D1; при reject — delete сервис и
  `relief_world_import` параметр адаптера `domainAdapters/relief.py`/`factory.py`),
  `api/routes/reliefTemplates.py` (body-variant по D1), `packs/errors.py`
  (LEGACY_* коды, если не переиспользуются), `imports/helpers.py`
  (коммент про legacy registry columns — проверить актуальность).
- **Контракт:** нет `legacy` pack; world-owned bodies только через явный
  manifest/`library_packs`; route-контракт relief import по D1.
- **Проверка:** `python -m compileall app`; unittest по затронутым файлам
  (`tests.test_relief_*`, `tests.test_library_packs_*` оставшиеся);
  grep `packs.legacy|uidMap|import_legacy_bodies` — 0.
- **Done:** каталог `packs/legacy/` отсутствует; импорт мира не знает про
  former-UID.

## Шаг 4 — wire-алиасы dataModel/jsonValidation

- **Цель:** старые ключи wire перестают читаться; canonical — единственный вход.
- **ТЗ:** `tz_json_validation.md` (wire-policy алиасы), `tz_locations.md`
  (`display_type`), `tz_template_library_packs.md` §4.2, `tz_building_generator.md`
  §3.9 (`staircase_type`), `tz_map_light_bake`/`wilderness` (landcover).
- **Файлы:**
  - `worldSlices.py`: `registry_map_to_list`, `location_type_wire_from_raw`,
    `climate_zone_wire_from_raw` (dict-map → ошибка/строго list);
  - `locationTypeEntry.py`: `AliasChoices("display_type","display_name")` →
    только `display_type`;
  - `climateFieldWire.py`: `_LEGACY_STATUS` `a`/`b`, promotion-ключи
    `climate_tier`/`tier`;
  - `worldTerrainMasks.read_legacy_landcover` + `terrainMasks/landcoverWire.py`
    — **взаимодействие с wilderness-10b:** алиасы `default_forests/plains`
    закреплены за планом 10b; если 10b ещё не сдан — здесь только убедиться,
    что фикстуры не дергают алиас, удаление остаётся за 10b;
  - `perkTemplateOutline`/`raceTemplateOutline` + `normalize*Wire`:
    `perk_uid`/`race_uid`/`display_race`;
  - `enums/staircaseType.py`: `trapdoor` alias, `_STAIRCASE_TYPE_SIZE_ALIASES`;
  - `parentLightRefinePolicy.py`: `terrain_resample` migrate + property (D2);
  - `fineTerrainChunkWire._migrate_legacy_wire`;
  - `annotationPolicy.py`: deprecated `DefaultOnWire`/`DefaultEnumOnWire`
    (callers → `DefaultWhenMissing`/`DefaultEnumWhenMissing`), член `DEFAULT`;
  - `packBlobWire.InteriorTransitionsRebuildRequired` (D2);
  - `races`/`perks` section aliases при наличии (D4).
- **Контракт:** по каждому ключу — один canonical вход; старый ключ → ошибка
  валидации либо strictness-guard по D2.
- **Проверка:** `python -m unittest` по затронутым доменам
  (`test_terrain_masks`, `test_landcover_*`, `test_structure_template`,
  `test_staircase_*`, `test_policy_*`, `test_import_validation_policy`);
  sweep-греп fixtures/tests — старые ключи только в reject-тестах.
- **Done:** grep алиасов в dataModel — 0 (кроме намеренных guard по D2).

## Шаг 5 — тесты — **DONE (2026-10-18)**

Удалены pure-legacy файлы: `test_library_packs_5b_migration.py`,
`test_template_domain_split.py`, `test_library_packs_5b_import.py`.
Переписано под новый контракт: `test_library_packs_b3.py` (UidMapTests и
Legacy* классы удалены, shipped-content тесты читают manifest, gen_003 —
новая pack identity `world.{uid}.smoke_003`), `test_template_domain_archive.py`
(4 legacy-теста → `test_flat_template_section_is_rejected_and_writes_nothing`),
`test_template_location_refs.py` (LegacyRefTests удалён), `test_world_scoped_writers.py`
(`missing_terrain_entries` вместо сервиса), `test_library_write_api.py`
(SeedLibraries → `write_authored_bodies`; loose-body endpoint → 422-тест),
`test_library_packs_4a/5a/5b_snapshot/5b_relief` (`pin_for_member` →
`LibraryPinEntry`, без `relief_world_import`), `test_location_context_contract`/
`test_registry_key` (`DefaultWhenMissing`), старые wire-ключи в
`test_location_payload{,_schema}`, `test_required_structure_position`,
`test_region_state_contract`, `test_pack_climate_apply`, `test_staircase_spec`,
`test_vertical_ladder_orientation_baseline`, `test_world_grid_settings`.
Дополнительно снят silent-alias `map_cell_size_m` в `jsonValidation/facade.py`
(`normalize_world` → `ImportValidationError` REMOVED_FROM_WIRE).

- **Проверка пройдена:** collection 0 failures; точечный батч 302 теста — зелёный;
  полный `unittest discover` — шаг 6.

## Шаг 5 — тесты (исходная формулировка)

- **Цель:** тестовый набор отражает только новый формат.
- **Файлы (кандидаты delete/rewrite, уточнить при имплементации):**
  `test_library_packs_5b_migration.py`, `test_template_domain_split.py`,
  `test_library_packs_5b_import.py`, `test_template_domain_archive.py`
  (legacy-части), `test_library_packs_b3.py` (legacy-части),
  `test_template_domain_api.py`, `test_policy_field_migration.py`,
  `test_world_scoped_writers.py` (legacy imports), `test_template_location_refs.py`.
- **Проверка:** полный `python -m unittest discover tests` зелёный.
- **Done:** тестов, кормящих старый формат, нет; reject-ветки покрыты
  позитивными/негативными тестами нового контракта.

## Шаг 6 — финал и документация

- **Цель:** ноль ссылок на снятый контракт.
- **Файлы:** `docs/*` sweep по `legacy`/`flat`/`transitional`; правила
  `.cursor/rules/*.mdc` (`template-pack-layout`, `bulk-sql` и пр. — упоминания
  legacy pack); `fixtures/packs/README.md` при необходимости; этот план →
  `-done.md` + пометка в H1.
- **Проверка:** grep `legacy` по `backend/app` остаётся только для
  осознанных остатков из «Границы трека» (debug map_cells, deprecated имена,
  TD-4) — зафиксировать список остатка в `docs/tz_generator_technical_debt.md`
  или отдельной строке ТЗ.
- **Done:** план переименован в `legacy-contract-removal-done.md`.

## Порядок и зависимости

0 (ТЗ) → 1 (фикстуры, безопасно при живом legacy) → 2 (вход) → 3 (модуль) →
4 (алиасы) → 5 (тесты) → 6 (финал). Шаги атомарны: один слой / одна группа
файлов за заход, короткий отчёт → «ок» → следующий.

Взаимодействие: landcover-алиасы (`default_forests`/`default_plains`) —
общий пункт с wilderness-10b; фикстурная конвертация независима и идёт здесь,
удаление алиаса — по тому треку, который ляжет последним (пометка в обоих
планах). `world_perk`, `seed_int` и прочий неформатный legacy — не блокеры.
