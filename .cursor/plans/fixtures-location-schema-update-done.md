# Fixtures под схему локаций (location_payload / LOC-T-1 / LOC-T-2) — выполнен

Привести `fixtures/*.json` к новой схеме локаций после `4e88935` (settlement-поля →
`location_payload` по `payload_kind`) и `c01e9d0` (`is_inhabited` на type/subtype),
плюс фикс дефекта overlay рецептных полей subtype.

## Договорённости

| Решение | Итог |
|---|---|
| square / gate | `square` → тип `district`; `gate` → `building` + `system_location_subtype: "military"` |
| `system_city_size` городов | `medium` |
| `city_size_registry` | канон `small`/`medium`/`large` без `radius`; wire-ключ остаётся `city_size_registry` |
| N+1-ранг | `huge` в `world_test_all.json` и `world_test_gen.json`; только в реестре, не на строках |
| Legacy-типы | удалить неиспользуемые (`city`,`town`,`village`,`square`,`street`,`gate`,`dungeon`,`cave`,`camp`,`kingdom`,`empire`,`duchy`); `continent` оставить |
| Overlay subtype | отсутствует → engine; явный `[]` → очистка; непустой список → замена; omission сохраняется при normalize/JSON/read |
| Footprint overlay | merge по рангу; отсутствие / `{}` не меняет engine-таблицу |
| `l0_map_symbol` | отсутствие / `null` → engine; строка из одного символа → переопределение |
| Родитель settlement | канон `[null, "territory", "region"]`; поселение может оставаться корнем |
| Готовность fixture | весь bundle проходит реальный импорт; одной проверки POJO локаций недостаточно |

Контракты согласованы после разбора плана. Родительская связь не создаётся
автоматически и не меняет linked list каскада. Расширение допустимых родителей
не включает внедрение обязательной проверки `parent_types` в production CRUD/import:
это отдельное изменение контракта. Для fixtures соответствие дерева реестру
проверяется явно.

## ТЗ

- `docs/tz_locations.md` §565 (`location_type_registry`), §642 (LOC-T-1 import wire),
  §458–536 (LOC-T-2 ранг/footprint), §196 (payload per type — NL-P1), §563 (площадь —
  NL под районом → district).

## Шаги

### Шаг 1 — фикс `_overlay_subtype` (код) — выполнен

- **Цель:** omission рецептных полей на world-subtype → наследование engine-значения,
  как у `is_inhabited`/`payload_kind`; явный `[]` по-прежнему очищает рецепт.
- **Файлы:** `backend/app/dataModel/locations/locationType/worldLocationTypeRegistry.py`,
  `backend/app/dataModel/locations/locationType/locationTypeSubtypeEntry.py`,
  `backend/tests/test_location_payload.py` (+кейс: overlay `{system_subtype, footprint_by_size}`
  без рецептных полей сохраняет `typical_district_types`/`required_structure_types` engine).
- **Контракт:** `typical_district_types`/`required_structure_types` берутся из world-строки
  только при `"<field>" in world.model_fields_set`; `footprint_by_size` — merge (уже).
  Отсутствие рецептных полей сохраняется при сериализации source-POJO, как отсутствие,
  а не превращается в явный `[]`. Явные списки сохраняются; `null` не является
  командой очистки. Общую сериализацию остальных defaults не менять.
- **Проверка:** `python -m unittest tests.test_location_payload tests.test_city_three_axes
  tests.test_loc_t2_settlement_size` — зелёные.
  Регрессии: omission / явный `[]` / непустой список через normalize → JSON →
  runtime read → engine-merge. Для изоляции этого шага символ указан явно.
  Из корня проекта — `npm run typecheck:cascade`.
- **Done:** footprint-only overlay не обнуляет рецепт после сохранения и чтения;
  явный список заменяет engine-значение только соответствующего поля.
- **Результат:** отсутствующие рецептные поля не сериализуются, overlay наследует
  их из engine по model_fields_set. Регрессия проверяет девять сочетаний двух
  полей (omission / пустой / непустой список) через normalize → JSON → runtime read.
  До исправления — пять падающих сочетаний; после — все проходят.
  Три тестовых модуля: 82 теста OK. `npm run typecheck:cascade`:
  0 ошибок, четыре ожидаемые negative-contract ошибки подтверждены.

### Шаг 1b — nullable `l0_map_symbol` — выполнен

- **Цель:** footprint-only subtype без символа переживает сохранение и чтение.
- **ТЗ:** `docs/tz_locations.md`, раздел `location_type_registry`; перед кодом
  уточнить там согласованный контракт nullable-символа.
- **Файлы:** `docs/tz_locations.md`,
  `backend/app/dataModel/locations/locationType/locationTypeSubtypeEntry.py`,
  `backend/tests/test_location_payload.py`.
- **Контракт:** отсутствие / `null` наследуют engine; строка содержит ровно один
  символ. `null` не отключает отображение. Ограничение длины не применяется к `None`.
- **Проверка:** `python -m unittest tests.test_location_payload`;
  normalize → JSON → read для `{system_subtype, footprint_by_size}` без символа;
  явный `null` и корректный символ; недопустимая длина отклоняется моделью.
  Из корня — `npm run typecheck:cascade`.
- **Done:** повторное чтение не вызывает TypeError и сохраняет engine-символ.
- **Результат:** контракт добавлен в ТЗ; ограничение длины перенесено на строковую
  ветку nullable-типа. Регрессии подтверждают наследование при omission / null,
  переопределение одним Unicode-символом после normalize → JSON → read,
  сохранение рецепта/footprint и отклонение строк длины 0 / 2 моделью.
  До исправления — три ошибки TypeError; после — 84 теста трёх модулей OK.
  `npm run typecheck:cascade`: 0 ошибок, четыре ожидаемые negative-contract
  ошибки подтверждены.

### Шаг 1c — допустимые родители settlement — выполнен

- **Цель:** явно разрешить самостоятельное поселение и размещение под регионом.
- **ТЗ:** `docs/tz_locations.md`, раздел `location_type_registry`, инварианты родителей;
  сначала обновить канон в ТЗ.
- **Файлы:** `docs/tz_locations.md`,
  `backend/app/dataModel/locations/locationType/worldLocationTypeRegistry.py`,
  `backend/tests/test_location_payload.py`.
- **Контракт:** engine settlement `parent_types = [null, "territory", "region"]`.
  Непустой world-список заменяет engine-список согласно существующему overlay.
  Изменение не создаёт родителей и не добавляет регион в каскад или расчёт footprint.
- **Проверка:** `python -m unittest tests.test_location_payload` — канонический
  реестр разрешает все три варианта; world-override сохраняет существующую семантику.
  Из корня — `npm run typecheck:cascade`.
- **Done:** существующие поселения под region соответствуют канону;
  production-валидация родительских связей не расширяется этим шагом.
- **Результат:** канон и ТЗ разрешают `[null, "territory", "region"]`.
  Регрессии проверяют engine/minimal merged registry и normalize → JSON → read:
  omission / [] наследуют канон, непустой world-список заменяет его целиком,
  включая вариант только корневого поселения `[null]`.
  Три тестовых модуля: 86 тестов OK; `npm run typecheck:cascade`:
  0 ошибок, четыре ожидаемые negative-contract ошибки подтверждены.

### Шаг 2 — канон в простых файлах — выполнен

- **Файлы:** `fixtures/world_template.json`, `fixtures/world_terrain_test.json`,
  `fixtures/world_test_gen_003.json`, `fixtures/world_test_gen_noloc.json`.
- **Что:** `city_size_registry` → три канон-ранга без `radius`; в `location_type_registry`
  удалить legacy-типы (ген-файлы: `city`/`town`/`village`/`square`/`street`/`gate`/`dungeon`/
  `cave`/`camp`/`kingdom`/`empire`/`duchy`); `continent` оставить + `parent_types: [null]`,
  у `region` в мирах с `continent` — `parent_types: [null, "continent"]`.
- **Проверка:** JSON parse; `python -m unittest tests.test_declared_river_topology
  tests.test_terrain_masks tests.test_plot_layout` (грузят `world_template.json`).
  Baseline разбора: во всех шести модулях шагов 1–2 — 111 тестов, две ошибки
  `test_plot_layout` (`test_catalog_of_structure_type_via_structure_ref`,
  `test_leaves_of_plaza_rule_and_resolve`): старый LevelDef без display_name и с rooms=[]
  в helper `_plot`. Это отдельный тестовый техдолг; новых ошибок быть не должно.
- **Done:** нет морфологических ключей в size-реестре; нет `radius`.
- **Результат:** обновлены четыре оговорённые fixture. В каждой три канонических
  ранга без radius; в двух gen-файлах удалены 12 неиспользуемых legacy-типов;
  в трёх мирах с continent явно заданы родители continent/region.
  JSON, merged registry, footprint issues=[] и родители проверены; сравнением
  с HEAD подтверждено, что остальные секции файлов не менялись.
  Три тестовых модуля: 30 тестов, 28 прошли, две прежние ошибки test_plot_layout
  совпадают с baseline (старый LevelDef в `_plot`); новых ошибок нет.
  Полный импорт bundles остаётся проверкой шага 5.

### Шаг 3 — `world_test.json` + `world_test_all.json` (строки локаций) — выполнен

- **Что:**
  - `system_location_type: "city"` → `"settlement"` + `system_location_subtype: "city"`,
    `system_city_size: "city"` → `"medium"` (Айронхолд, Амберпорт в обоих файлах);
  - `square` (Рыночная площадь, Торговая набережная) → `"district"`;
  - `gate` (Северные ворота) → `"building"` + `system_location_subtype: "military"`;
  - `location_type_registry`: удалить неиспользуемые legacy-типы (см. таблицу);
    `continent` → `parent_types: [null]`; `region` → `parent_types: [null, "continent"]`;
  - `city_size_registry` → канон; в `world_test_all.json` + `huge` и overlay
    `settlement.subtypes[].footprint_by_size.huge` (`city` 8.0, `underground_city` 8.0,
    `village` 0.9 — сохраняет полосу village < city).
  - Уточнение по проверке существующего дерева: в world_test_all четыре river-NL
    уже вложены в geographic-NL. World geographic.parent_types явно разрешает
    `[null, "region", "territory", "geographic"]`; engine и ссылки дерева не менять.
- **Проверка:** `BundleNamedLocation.model_validate` каждой строки `locations[]` с
  `location_type_registry` файла (engine-merge) — без ошибок; payload городов содержит
  `system_city_size == "medium"`, `is_inhabited is True`.
  Отдельно проверить наличие родителя и допустимость его типа по merged-реестру:
  сама модель BundleNamedLocation эти связи не проверяет.
- **Done:** ни одной строки с типом вне merged-реестра; settlement-поля не теряются
  (тип имеет `payload_kind`).
- **Результат:** в каждом файле мигрированы два города, две площади и ворота;
  обновлены size/type-реестры. В world_test_all добавлен huge с тремя footprint
  overlays и world-разрешение geographic-родителя существующих рек.
  Проверены 15 + 33 строки, их родители, payload после to_db_fields/read,
  is_inhabited=true и medium у четырёх городов. Реестры проверены через
  partial normalize → JSON → runtime read; engine-рецепты и символы сохранены,
  footprint issues=[]; huge даёт 8.0 / 8.0 / 0.9. Остальные секции не менялись.
  Полная normalize_world проходит для world_test_all; world_test имеет отдельный
  блокер REF-W гидрологии, записанный в шаге 5. Импорт bundle этим шагом не закрыт.

### Шаг 4 — `world_test_gen.json` (N+1 huge) — выполнен

- **Что:** `city_size_registry` + `huge`; в `location_type_registry.settlement` —
  `subtypes` overlay с `footprint_by_size.huge` (как в шаге 3).
  Типы и ранги локаций уже обновлены; отдельно проверить родителей по контракту шага 1c.
  Применить общие договорённости по реестру: удалить неиспользуемые legacy-типы,
  continent → parent_types [null], region → [null, "continent"].
- **Проверка:** `resolve_settlement_footprint_multiplier("city","huge", ...)` по
  merged-реестру файла → 8.0; `settlement_size_registry_issues` → пусто.
- **Done:** N+1-ранг резолвится; нормализация мира без issues.
  Полный импорт в БД проверяется вместе с остальными bundles в шаге 5c.
- **Результат:** добавлены huge и три footprint-only overlays; очищен реестр
  legacy-типов, заданы родители continent/region. Пять строк locations и остальные
  секции не изменялись. После partial normalize → JSON → runtime read проверены
  родители и payload всех строк, medium/is_inhabited=true у обоих городов,
  huge=8.0/8.0/0.9; исходные ранги, engine-рецепты и символы сохранены,
  settlement_size_registry_issues=[]. Полная normalize_world также проходит.

### Шаг 5 — полный импорт bundles — выполнен

Выявленный блокер: normalize_world(world_test.world) выдаёт семь REF-W ошибок:
defaults гидрологии требуют terrain shore_river / shore_mountain_river /
shore_lake / shore_sea и material sand. Согласованный контракт: недостающие
канонические записи автоматически подключаются из библиотеки defaults к миру.
Не дописывать эти зависимости вручную в world_test и не менять defaults гидрологии.

Шаг выполнять атомарными подшагами:

1. **5a — подключение библиотек defaults — выполнен.** Сначала уточнить ТЗ
   `docs/tz_json_validation.md` и `docs/tz_locations.md` для material/terrain registries.
   При полном импорте отсутствие реестра → канонический реестр; непустой реестр →
   канонические записи + world-записи по ключу, с приоритетом указанных миром
   значений. Для совпавшего ключа явно указанные world-поля переопределяют
   каноническую запись; отсутствующие поля наследуют её значения. Явные false/0
   не считать отсутствием; nullable-поля обрабатывать по контракту конкретного POJO.
   Недостающие записи включаются в нормализованный мир до REF-W проверки,
   а в БД сохраняются обычным импортом после успешной проверки.
   **Единый import pipeline:** `WorldBundleService.import_bundle` →
   `normalize_world` → `merge_facade_slices` → `_merge_registry_list` →
   `validate_ref_w` → существующее сохранение секций bundle.
   **Точка подключения:** `_merge_registry_list` дополняет отсутствующий реестр
   при полном импорте и выполняет слияние по ключу/явным полям до валидации
   записей существующим policy resolver. Библиотека, ключ идентичности и режим
   дополнения задаются POJO/WorldSlice. Не создавать второй импортер defaults,
   обработчик специально для гидрологии или отдельный проход после сохранения.
   Runtime использует общий механизм с той же семантикой слияния, в том числе
   для ранее сохранённых частичных реестров. Неизвестные ссылки, отсутствующие и в мире, и в библиотеке,
   остаются ошибками. Для partial update отсутствие реестра не должно перезаписывать
   сохранённые world overrides. Общий механизм опирается на декларации POJO/WorldSlice;
   не заводить отдельный список shore/material-ключей в импортере.
   Контракты instance-каталогов resource/crops/livestock не менять автоматически:
   у них отдельно закреплена семантика полного списка мира.
   Файлы: соответствующие registry POJO, `worldSlices.py`, `worldSliceMerge.py`,
   REF-W index при необходимости, тесты defaults/overlay.
   Проверки: отсутствие / пустой / частичный реестр; world override канонического
   ключа; N+1 ключ; неизвестная ссылка; normalize/persist/read и partial update.
   `world_test` проходит normalize без ручного добавления shore_* / sand.
   **Результат:** material/terrain POJO объявляют CANONICAL_OVERLAY_ID_FIELD;
   WorldSlice передаёт декларацию единому canonical_registry_wire, вызываемому
   импортом и runtime перед policy-resolve. Полный импорт материализует реестры;
   partial update без ключа их не затрагивает. ТЗ обновлены.
   Добавлен `backend/tests/test_world_registry_defaults.py` (восемь регрессий),
   обновлён `test_repair_world_defaults.py`: частичный реестр читает каноническую
   воду; repair материализует библиотеку; явная смена категории water сохраняется.
   Целевые три модуля — 24 теста OK. Все восемь миров проходят normalize_world.
   Полный прогон: 1594 теста, 21 прежняя ошибка и один expected failure;
   сравнение с `.local/inhabited-defaults-tests.log` — новых падений нет.
   Лог: `.local/registry-defaults-tests.log`. `npm run typecheck:cascade`:
   0 ошибок, четыре ожидаемые negative-contract ошибки подтверждены.
   Сохранение/чтение через реальный bundle service в изолированной БД
   проверяется следующими подшагами 5b–5c; шаг 5 целиком ещё не закрыт.
2. **5b — fixture defaults — выполнен.** Добавить `fixtures/world_defaults_test.json`: минимальный
   world bundle без material_registry, terrain_registry и остальных собственных
   библиотек/настроек мира. Проверять все defaults, объявленные мировыми POJO/WorldSlice,
   и разрешимость ссылок между ними, а не только shore_* / sand. Это проверка
   defaults мира; выполнение всех генераторов не является критерием импорта.
   После реального импорта канонические material/terrain записи присутствуют
   в сохранённых реестрах; повторное чтение согласовано с нормализацией.
   Источник ожидаемых канонических данных — POJO, не второй снимок библиотек в fixture.
   Отдельный тест частичного world-реестра обязателен: fixture без реестров сама по
   себе не ловит исходный дефект непустого реестра world_test.
   **Результат:** fixture содержит только секцию world с uid/name/created_at;
   собственных библиотек/настроек нет. `_fixture_meta` удалён: реальный импорт
   отвергает его как неизвестную секцию. В `test_fixture_bundle_import.py`
   три интеграционных теста используют временную SQLite БД, apply_migrations,
   validate_schema и настоящий WorldBundleService/WorldSectionHandler/WorldService
   с SqliteWorldRepository. Проверены import/read defaults всех 32 facade WorldSlice
   по их POJO, сохранённые полные material/terrain библиотеки, persist явных
   overrides и их сохранность после update(name), отклонение неизвестной ссылки
   до записи мира. Четыре целевых модуля: 27 тестов OK. Остальные bundles пока
   не покрыты интеграционным импортом — это подшаг 5c.
3. **5c — импорт всех bundles — выполнен.** Удалить map_cells из импортируемых fixtures,
   а также недопустимые metadata-секции `_fixture_meta` / `_template_meta`.
   Обнаружено при 5b: BundleSection уже не разрешает legacy `races` / `perks`;
   привести их к действующим race_templates / perk_templates с проверкой
   контрактов содержимого, не ограничиваться переименованием ключей.
   актуализировать `backend/scripts/build_world_test_all_fixture.py`: сборщик
   не возвращает map_cells и воспроизводит huge/footprint и geographic-parent
   overlays world_test_all. Проверить сохранение данных при повторной сборке.
   Интеграционные проверки всех восьми bundles, включая defaults fixture, —
   через реальный импорт и чтение в изолированной БД актуальной схемы.

- **Цель:** проверить готовность всего bundle, включая остальные секции и persist/read.
- **ТЗ:** `docs/tz_locations.md`, LOC-T-1 import wire;
  действующий контракт World Pack для секции map_cells.
- **Файлы:** семь `fixtures/world*.json` из шагов 2–4 и `fixtures/world_defaults_test.json`;
  `backend/scripts/build_world_test_all_fixture.py`;
  `backend/tests/test_fixture_bundle_import.py` (интеграционная проверка).
- **Контракт:** импортируемые bundles не содержат ключа `map_cells`, даже с `[]`;
  убрать его из world_test/world_test_all и проверить остальные файлы.
  Контракт импортера не ослаблять. Если клетки нужны другому тестовому потребителю,
  сохранить их в отдельной fixture World Pack и обновить ссылки потребителя.
- **Проверка:** `python -m unittest tests.test_fixture_bundle_import` в изолированной
  БД актуальной схемы через WorldBundleService.import_bundle, затем чтение результатов.
  Для каждого файла: нет ошибок секций и rollback; реестры и payload сохраняются,
  рецепты engine не очищаются; huge резолвится в двух оговорённых файлах;
  дерево локаций соответствует merged parent_types.
- **Done:** все восемь bundles импортируются целиком; defaults автоматически
  подключаются и сохраняются, явно указанные world overrides не теряются;
  препятствия в других секциях
  фиксируются как явные блокеры плана, без молчаливого сужения проверки до locations.

- **Результат 5c:** семь legacy bundles переведены на race_templates/perk_templates:
  идентификаторы сохранены в template_uid, display_race → display_name,
  world_uid удалён из глобальных библиотечных тел; system_name заполнен стабильно,
  created_at минимальных рас указан явно. Недопустимые metadata/map_cells удалены.
  В world_template/world_terrain_test явно разрешён geographic-родитель вложенных
  географических объектов; сборщик наследует это разрешение для world_test_all.
  Сборщик использует новые секции, не remap-ит глобальные шаблоны, сохраняет huge
  и три footprint overlays; повторная сборка структурно идентична fixture.
  Интеграционный тест импортирует каждый из восьми bundles в отдельную пустую
  SQLite БД после migrations/validate_schema через production Container и все
  штатные handlers. Экспорт читает сохранённые секции: проверены количества,
  содержимое библиотечных тел, явные material/terrain overrides, канонические
  записи, payload, родители, engine-рецепты и huge footprint.
  Дополнительно сравнены с HEAD все states/locations/relief_templates и поля
  рас/перков: данные сохранены, кроме предусмотренных изменений wire-формата.
  Четыре целевых модуля — 43 теста OK; лог .local/fixture-bundle-import.log.
  Полный прогон — 1599 тестов, 21 прежняя ошибка, один expected failure;
  сравнение имён ошибок с .local/registry-defaults-tests.log: новых нет.
  Лог: .local/fixtures-schema-tests.log. npm run typecheck:cascade:
  0 ошибок, четыре ожидаемые negative-contract ошибки подтверждены.
  git diff --check проходит. План завершён; генераторы/bake и отдельный техдолг
  устаревших тестовых схем этим планом не закрываются.

## Вне scope

- `fixtures/_smoke_locations.json` — намеренно невалидный (`not_a_type`), не трогать.
- `seed.json`, `character_test.json`, `_smoke_*`, `fixtures/templates/*.json` — не локации.
- Локальная БД (`missing columns ['location_payload']` при старте) — recreate по
  `schema-migrations-policy.md`, не часть этого плана.
