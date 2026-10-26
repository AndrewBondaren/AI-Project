# План: техдолг ревью шага B3 (5b) — world snapshot и packing identity — ✅ выполнен

> Все шаги 1–6 закрыты (2026-10-14). Итоги по шагам — в конце файла.

## Контекст

Ревью коммитов `a7d01a7f` (snapshot loader + packing identity по member
`template_uid`) и `9522f962` (сплит `tokens.py` → `tokens`/`subjects`/
`layoutPicks`) — шаг **B3** плана
[`domain-template-libraries-5b-implementation-done.md`](domain-template-libraries-5b-implementation-done.md).

Оси ревью: хардкоды · неявные контракты · один класс = одна
ответственность · класс ≤ 250 строк (запрошенный порог; repo-лимит
`class-size-limit` — 300). Архитектура в целом соответствует плану:
identity = member UID, pins ≠ фильтр, FS stdlib и world registry сняты,
одна библиотечная диагностика на границе. Ниже — дефекты чистоты.

Проверки каждого шага: `python -m unittest` из `backend/`.

## Карта находок → шаги

| Находка | Файлы | Шаг |
|---|---|---|
| `Facing.SOUTH` литерал ×~7 без константы «packing envelope facing» | `planner/tokens.py:119`, `planner/areaSlots.py:106,113`, `buildingCache.py:75,89,106,109,169`, `districtAssembler.py` | 1 |
| Магические district-метки `"snapshot"` / `"cache"` / `district or "cache"` в `packing_warning` | `templateSnapshotLoader.py:146`, `buildingCache.py:163,187` | 1 |
| Stringly-typed каталоги `"resource"`/`"crop"`/`"livestock"` — диспетчеризация по трём функциям | `planner/subjects.py` (`_subject_catalog`, `_fallback_pool`, `_token_in_catalog`) | 1 |
| `AreaPlacement.template_uid = ""` — пустая строка как sentinel «не member» + `or None` coercion ниже | `planner/types.py:135`, `districtAssembler.py:270` | 1 |
| `catalog=None` → `ValueError`: сигнатура обещает optional, контракт требует обязательный | `settlementAssembler.py:75`, `districtAssembler.py:120`, `settlementGeneratorService.generate_layout:88`, `buildingCache.build_layout_cache:144,150` | 2 |
| Мёртвые параметры `_ = world` / `_ = (world, skeleton)` / `_ = terrain_cells` | `buildingCache.py:124`, `buildingCache.py:149`, `areaSlots.py:96` | 2 |
| `StructureCatalog` ключуется по `body.system_name`, `BuildingCatalog` — по `entry.template_uid`: асимметрия; корректность зависит от model-A перезаписи `system_name = template_uid` в `bodyPreparation.py:46-56` | `structureCatalog.py:22-33`, `buildingDefaults.py:18-20` | 3 |
| `adapters.get(kind)` → `None` → `AttributeError` вместо доменной диагностики; требование «adapters ⊇ `_SNAPSHOT_KINDS`» не задекларировано | `templateSnapshotLoader.py:106` | 3 |
| Двойной `prepare_body`: `template_graph_issues` (`_PREPARATIONS`) + повторный `adapter.prepare_body` в loader — два pipeline обязаны совпадать, результат первого не переиспользуется | `templateGraphValidation.py:23,46-50`, `templateSnapshotLoader.py:95-115` | 3 |
| Single-pass исключение ref'ов опирается на незащищённый инвариант «refs только plot/building → structure» | `templateSnapshotLoader.py:118-129`, `refFields.template_body_refs` | 3 |
| Private-имена (`_pick_layout_picks`, `_buildings_rng`, `_resolve_subjects`, `_*_kinds_for`) — фактический межмодульный API после сплита | `planner/tokens.py:11-14`, `planner/layoutPicks.py:11-16` | 4 |
| `candidate_template_uids` — чистый алиас `pick_layout_uids`, живёт только ради тестов | `planner/tokens.py:60-71`, `tests/test_city_three_axes.py` | 4 |
| `_resolve_subjects` мутирует `slot.subject_tags` — скрытый write-back внутри «resolve» (переехал as-is) | `planner/subjects.py:135` | 5 |
| Тихий `continue` — размещённый токен без template/envelope исчезает без диагностики | `planner/areaSlots.py:102` | 5 |
| `StructureAreaAssembler` class body ~281 строка — выше порога 250 (pre-existing; B3 +~9 строк; repo-лимит 300 не перейден) | `structureAreaAssembler.py:202-482` | 6 |

## Вне scope (не долг этих коммитов)

- `system_template_uid = template_uid or template_name`
  (`structureAreaAssembler.py:468`) — имя в uid-поле для non-member
  placements; transitional fallback, persist-identity принадлежит B4.
- `CANONICAL_PLOT_NAMES` + `_FIXTURES_TEMPLATES` (`worldBuildingLayoutDefaults.py`)
  — объявленный trusted spec по решению TZ §6 (не wildcard scan);
  `parents[6]` — устоявшийся repo-style вычисления корня.
- `COUNT_WITHOUT_KEY` / `PRIORITY_WITHOUT_KEY` (`structurePlacement.py`)
  — задекларированные SoT fallback'и, не дубли POJO.
- `CatalogSnapshot(members, bodies, {})` — positional пустой
  `source_files`: `template_graph_issues` его не читает; косметика.
- `_resolve_subjects`/`placements_from_reservations` side effects —
  поведение до-B3, сплит перенёс as-is; фиксируются шагом 5, не
  регрессией B3.

## Шаги

### Шаг 1 — packing-литералы и sentinel-строки

- **Цель:** один источник констант packing-конвенций; нет магических
  строк в typed-полях лог-канала.
- **ТЗ:** `tz_structure_connections.md` §5.1.3 (envelope SOUTH —
  объявленный инвариант); `tz_template_library_packs.md` §7
  (диагностика границы).
- **Файлы:** `planner/types.py` (или новый `planner/packingFacing.py`),
  `planner/tokens.py`, `planner/areaSlots.py`, `buildingCache.py`,
  `districtAssembler.py`, `templateSnapshotLoader.py`,
  `planner/subjects.py`.
- **Контракт:** `PACKING_ENVELOPE_FACING = Facing.SOUTH` — единственная
  точка; pseudo-district контексты — typed значение (enum/None +
  явное поле в `packing_warning`), не литерал `"snapshot"`/`"cache"`;
  subject-каталоги — `StrEnum`/`SubjectCatalog` вместо `"resource"`…;
  `AreaPlacement.template_uid: str | None = None` вместо `""`.
- **Проверка:** `python -m unittest tests.test_city_three_axes
  tests.test_plot_layout tests.test_building_purpose` — зелёные;
  grep: `Facing.SOUTH` вне константы — только в non-packing контекстах.
- **Done:** литералы packing-конвенции — через константы/enum;
  sentinel `""` убран.

### Шаг 2 — честные сигнатуры: обязательный catalog, нет мёртвых параметров

- **Цель:** сигнатура = контракт: то, что обязательно, не
  `Optional`-default; игнорируемые входы удалены.
- **ТЗ:** `tz_template_library_packs.md` §5 (catalog — вход от caller,
  не self-load); правило `layer-boundaries.mdc`.
- **Файлы:** `settlementAssembler.py`, `districtAssembler.py`,
  `settlementGeneratorService.py`, `buildingCache.py`,
  `planner/areaSlots.py` + callers (packingJob, scripts, tests).
- **Контракт:** `catalog: BuildingCatalog` — позиционно обязателен
  (без `= None` + `raise`); `ensure()` без `world`;
  `build_layout_cache` без `terrain_cells`;
  `placements_from_reservations` без `world`/`skeleton`.
- **Проверка:** `python -m unittest tests.test_library_packs_5b_snapshot
  tests.test_settlement_topology tests.test_c24_district_packing` +
  `python -m compileall app` — зелёные; скрипты `debug_settlement*`
  обновлены.
- **Done:** ни один параметр не игнорируется; `None`-catalog невозможен
  типово.

### Шаг 3 — явная идентичность `StructureCatalog` + контракты loader'а

- **Цель:** оба каталога ключуются заявленным member `template_uid`;
  loader декларирует свои требования и не гоняет двойную подготовку.
- **ТЗ:** `tz_template_library_packs.md` §5 (resolve по member uid);
  `tz_domain_template_libraries.md` §5 (runtime refs).
- **Файлы:** `structureCatalog.py`, `buildingDefaults.py`,
  `templateSnapshotLoader.py`, `templateGraphValidation.py`,
  `refFields.py`.
- **Контракт:** `StructureCatalog.from_entries({template_uid: body})`
  (uid передаётся явно, не выводится из `body.system_name`); loader —
  `self._adapters[kind]` с доменной ошибкой на пробеле, не `.get()`;
  подготовленные тела из `template_graph_issues` возвращаются caller'у
  (или loader'у), второй `prepare_body` устранён либо задокументирован
  как единственный; инвариант «refs только → structure» — assertion в
  `template_body_refs` или comment-контракт на уровне полей.
- **Проверка:** `python -m unittest tests.test_library_packs_5b_snapshot`
  — зелёный; при подмене адаптера ошибка доменная.
- **Done:** идентичность структур не зависит от side-effect подготовки;
  пробел адаптеров диагностируется.

### Шаг 4 — межмодульный API без underscore + снятие алиаса

- **Цель:** имена функций отражают их реальный уровень доступности;
  нет двух имён одной операции.
- **ТЗ:** — (чистота пакета; правило `class-size-limit.mdc` о
  единственном публичном шве).
- **Файлы:** `planner/tokens.py`, `planner/layoutPicks.py`,
  `planner/subjects.py`, `tests/test_city_three_axes.py`.
- **Контракт:** `_pick_layout_picks`, `_buildings_rng`,
  `_resolve_subjects`, `_resource_kinds_for`, `_crop_kinds_for`,
  `_livestock_kinds_for` — без ведущего underscore (это межмодульный
  API пакета planner); `candidate_template_uids` удалён, тесты
  переходят на `pick_layout_uids`.
- **Проверка:** `python -m unittest tests.test_city_three_axes` —
  зелёный; grep: импорт `_`-имён между модулями planner отсутствует.
- **Done:** один публичный шов `pick_layout_uids`/`build_tokens`;
  алиас снят.

### Шаг 5 — зафиксировать до-B3 side effects (документация или fix)

- **Цель:** снять двусмысленность pre-existing поведения, перенесённого
  сплитом.
- **ТЗ:** `tz_structure_connections.md` §5.1.3 (subject tags —
  детерминизм выбора).
- **Файлы:** `planner/subjects.py`, `planner/areaSlots.py`,
  `districtSlot.py` (тип `subject_tags`).
- **Контракт:** либо `subject_tags` write-back — задокументированный
  контракт `_resolve_subjects` (docstring), либо возврат picked без
  мутации slot; тихий `continue` в `placements_from_reservations` —
  `packing_warning` с доменным reason (или явный задокументированный
  пропуск synthetic-плейсментов).
- **Проверка:** существующие packing-тесты зелёные; новый warning —
  доменный, один на событие.
- **Done:** side effects либо устранены, либо являются записанным
  контрактом.

### Шаг 6 — `StructureAreaAssembler` > 250 (pre-existing, вне B3)

- **Цель:** зафиксировать факт, не раздувать B3.
- **Файлы:** `structureAreaAssembler.py` (~281 строка тела класса).
- **Статус:** repo-лимит `class-size-limit` (300) не перейден;
  превышение запрошенных 250 зафиксировано. Вынос зоны — при следующей
  правке файла (assemble / `_place_building` / `_build_barrier` —
  смешение area-оркестрации и building placement).
- **Done:** не применимо к B3; кандидат в FM-таблицу при следующем
  аудите.

## Итоги выполнения (2026-10-14)

- **Шаг 1 ✅** — `PACKING_ENVELOPE_FACING` в `planner/types.py`;
  `PackingScope` {SNAPSHOT, CACHE} вместо меток; `SubjectCatalog`
  StrEnum; `AreaPlacement.template_uid: str | None`.
- **Шаг 2 ✅** — `catalog` обязателен во всех assemble/generate API;
  мёртвые `world`/`terrain_cells`/`skeleton` сняты; литералы
  step/reason → `PackingStep`/`PackingReason` (+ новый `AREA_SLOTS`).
- **Шаг 3 ✅** — `StructureCatalog.from_entries({uid: body})`;
  `prepare_template_graph()` один проход (loader без `adapters`);
  инвариант «refs → structure» — assertion в `template_body_refs`.
  Отступление: параметр `adapters` удалён вместо `.get`+raise — точка
  отказа устранена.
- **Шаг 4 ✅** — `_`-имена → публичные (`resolve_subjects`,
  `*_kinds_for`, `pick_layout_picks`, `buildings_rng`);
  `candidate_template_uids` удалён, тесты на `pick_layout_uids`.
- **Шаг 5 ✅** — `resolve_subjects` чистый; явный write-back
  `record_subjects()` в `pick_layout_picks`; `placements_from_reservations`
  — `district` параметр + `packing_warning` (MISSING_TEMPLATE /
  FOOTPRINT_MISS) вместо тихого `continue`.
- **Шаг 6 ✅** — зафиксирован: `StructureAreaAssembler` ~281 (≤300 repo,
  >250 review) — вынос при следующей правке файла; записан в
  `tz_generator_technical_debt.md`.
