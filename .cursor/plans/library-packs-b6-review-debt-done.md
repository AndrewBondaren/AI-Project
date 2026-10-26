# План: техдолг ревью шага B6 (5b) — удалить pointer dual-write — done

## Контекст

Ревью коммита `bf814e39` — шаг **B6** плана
[`domain-template-libraries-5b-implementation-done.md`](domain-template-libraries-5b-implementation-done.md):
membership стал единственным availability source; `_RegistryPointerMixin`
и pointer-API удалены; flat export обеих секций читал
`members.list_for_world`; `layouts_for_world` удалён.

Оси ревью: неявные контракты · хардкоды · один класс = одна
ответственность · метод = одна ответственность · класс ≤ 250 строк
(запрошенный порог; repo-лимит `class-size-limit` — 300).

Контракт шага соблюдён; блокеров нет. Ниже — дефекты чистоты и неявные
контракты. **Правки B7 уже идут** (flat-секции и `export_bodies_for_world`
удалены, `_POINTER_UID_FIELD` снят, `building_template_registry` и его
scan удалены): часть находок закрыта обстоятельствами, один пункт
влит в B7-свип (решение мастера 2026-10-15).

Проверки каждого шага: `python -m unittest` из `backend/`.

## Решения мастера (2026-10-15)

- `removed_uids` — удалить **внутри B7-свипа** (те же файлы, не отдельный долг); уже снимается правками B7.
- Делегация relief prepare_body — **паттерн `PlotBodyPreparation`**:
  `ReliefBodyPreparation.validate_world` делегирует `world_import`,
  внедряемый в preparation; адаптер — тонкий.
- Конвенция remap-helpers — **return-new** для `remap_pins` (возвращает
  новое значение `library_pins`, caller присваивает).
- Шаг 10 (вынос `_validate_structure_*`) — **отложен до завершения B7**.
- `world_import=None` — **warning-лог** через существующий канал
  (`report_issues` / маршрут `jsonValidation/resolve`; новый consumer-файл
  и `logging.getLogger` мимо фасада запрещены — tz_logging L3, packs §7).
- Чужие приватные поля — **инъекция write provider напрямую** в
  import-сервис + расширение публичного `LibraryPackService.import_path`;
  `_write_provider`/`_fs_writes` снаружи не читаются.
- Missing-body — **зафиксировать политику**: boundary диагностирует один
  раз и исключает; runtime не подставляет (уже de facto в
  `TemplateSnapshotLoader._prepare` + `resolve_fallback`).

## Карта находок → шаги

| Находка | Файлы | Шаг |
|---|---|---|
| `removed_uids` — параметр контракта `prepare_world_refs`, который передаёт планнер, но не читает ни одна реализация | `contract.py:154`, `relief.py:127`, `structure.py:66`, `templateBodyAdapter.py:24`, `writeRetentionPlanner.py:106` | **B7-свип** |
| `resolve_picked_template` — falsy-guard `if uid` мёртв после `PickResult.template_uid: str` | `templatePick.py:51-52` | 1 |
| `reliefWorldImportService` лезет в приватное `self._library._write_provider` ×3; relief/structure services — в `._write_provider()._fs_writes` | `reliefWorldImportService.py:69,83,88`, `reliefTemplateLibraryService.py:161`, `structureTemplateLibraryService.py:180` | 2 |
| `_SYSTEM_NAME_FIELD` — константа есть, но `bodyPreparation.py`/`templateBodyAdapter.py` пишут `'system_name'` литералом, `relief.py:121` импортирует её локально внутри метода | `bodyPreparation.py:46-56`, `templateBodyAdapter.py:21`, `relief.py:121` | 3 |
| `LOCATION_TEMPLATE_REF_FIELDS` (refFields) и `_LOCATION_REF_KINDS` (remapRefs) — две параллельные декларации одного контракта | `refFields.py:138-141`, `remapRefs.py:92-95` | 4 |
| Missing-body политика: boundary диагностирует один раз и исключает, runtime не подставляет — зафиксировать явно (export-дивергенция умерла вместе с flat-секциями) | `templateSnapshotLoader.py` docstring, `domainAdapters/contract.py` (`resolve_fallback`), план/ТЗ | 5 |
| `ReliefPackAdapter.prepare_body` дублирует `ReliefBodyPreparation` (resolve + warn_geom + identity), теряя проверку каноничности `template_uid`; `world_import=None` → silent skip мировых проверок | `domainAdapters/relief.py:41-67` vs `:83-109`, `factory.py` | 6 |
| `library_pins` — единственная колонка вне `resolve_world_column`; инвариант «все прочие изменённые колонки известны resolver'у» не записан; порядок адаптеров `sorted(kind.value)` — произвольный | `writeRetentionPlanner.py:105-118` | 7 |
| `WriteRetentionPlanner.finish` ~57 строк: merge индексов + retention + deleted + rebuild deps + 2 проекции мира + ref-диагностика + dependency-issues | `writeRetentionPlanner.py:22-78` | 7 |
| `remap_pins` — mutating+bool; `remap_named_location_refs`/`_remap_relief_pick_policy` — return-new; caller'ы bool игнорируют | `remapRefs.py:31-42` vs `:75-163` | 8 |
| Хардкоды: `'|'` ×2; `version="1.0"` дублирует default `LibraryPackRow`; `rsplit(".",1)`; `source_file="bundle"`; consumer-префиксы `world:`/`named_location:`/`relief_pick_policy.` | `memberOps.py:29`, `packOps.py:32,56,72`, `refFields.py:130,157`, `structure.py` (consumer строка удалена B7), `buildingTemplateLibraryService.py`, `reliefWorldImportService.py` | 9 |
| `ReliefWorldImportService`: import + prepare + два structure-ref валидатора + terrain sync | `reliefWorldImportService.py:143-197` | 10 |

## Закрыто обстоятельствами B7 (verified)

- **Missing-body export-дивергенция** (relief skip+warn vs building
  `reject_unresolved`) — оба `export_bodies_for_world` и flat-секции
  удалены; каноничная политика живёт в snapshot-границе → шаг 5
  сведён к фиксации.
- **`_POINTER_UID_FIELD` + scan `building_template_registry`** —
  удалены с колонкой.
- **`BuildingTemplateLibraryService`** — сжат до thin CRUD; статик-блок
  валидации (`parse_body`/`subject_issues`/`prepare_body`) ушёл
  (ambiguous parse → `legacyTemplateBodies` converter).
- Тестовые хвосты `relief_template_registry`/`building_template_registry`
  в suites — вычищены правками B7.

## Вне scope (не долг этого коммита)

- `raceService`/`worldPerkService.export_bodies_for_world` — не
  pack-домены, свои секции; унификация с pack-границей не требуется.
- `_ensure_provider` в `buildingTemplateLibraryService` — lazy-seed
  глобальных defaults; отдельная зона.
- `memberOps.delete` читает `scope.world_for(pack)` — нужен для
  pin-usages; соответствует решению B6.
- `PackMaterializationOrchestrator` ~240 и `PackDetailedBakeOrchestrator`
  ~218 строк — под порогом; наблюдать при наполнении.

## Шаги

### Шаг 0 — влито в B7-свип ✅ закрыт B7-правками

- `removed_uids` снят из `PackDomainAdapter.prepare_world_refs`,
  всех реализаций и вызова `WriteRetentionPlanner._world` — вместе с
  остальным снятием legacy-контрактов B7 (отдельного долга нет).

### Шаг 1 — тип соответствует проверкам ✅ 2026-10-15

Выполнен: falsy-guard и `or "selected"` сняты в `resolve_picked_template`
(`templatePick.py`); 20 тестов (`test_library_packs_5b_relief` +
`test_relief_pure`) — OK.

- **Цель:** `resolve_picked_template` не защищается от состояния,
  исключённого типом.
- **ТЗ:** [relief R19/R21](../../docs/tz_terrain_relief.md).
- **Файлы:** `generators/terrain/relief/pick/templatePick.py`.
- **Контракт:** `pick.template_uid` обязателен (`str`); falsy-guard и
  `or "selected"` в path снимаются — missing body →
  `REF_W_UNAVAILABLE` по реальному uid.
- **Проверка:** `python -m unittest tests.test_library_packs_5b_relief
  tests.test_relief_pure`.
- **Done:** defensive-код не противоречит объявленному типу.

### Шаг 2 — seam write provider: инъекция + публичный `import_path` ✅ закрыт B7-правками

Реализовано мастером: `ReliefWorldImportService` получает
`write_provider` через собственный ctor (`reliefWorldImportService.py`),
`_library._write_provider` и `._fs_writes` снаружи не читаются;
`LibraryPackService.import_path` — публичный путь.

- **Цель:** приватные `_write_provider`/`_fs_writes` не читаются
  снаружи; форма — по ТЗ packs (граница = `LibraryPackService`).
- **ТЗ:** [packs §0.2/§1.2/§4](../../docs/tz_template_library_packs.md);
  правило `layer-boundaries`.
- **Файлы:** `reliefWorldImportService.py`, `reliefTemplateLibraryService.py`,
  `structureTemplateLibraryService.py`, `libraryPacks/packService.py`
  (публичный `import_path` получает `enforce_domain_root`),
  `core/container.py` (проводка provider в import-сервис).
- **Контракт:** `ReliefWorldImportService` получает `write_provider`
  через собственный ctor, не через `library._write_provider`;
  FS-import идёт по публичному `LibraryPackService.import_path` —
  `_fs_writes` остаётся внутренним job.
- **Проверка:** `python -m unittest discover -s tests -p "test_library_packs_5b*.py"`;
  `tests.test_bundle_archive`.
- **Done:** `_write_provider` и `_fs_writes` не упоминаются вне
  своих классов.

### Шаг 3 — единый `_SYSTEM_NAME_FIELD` и топ-импорты ✅ закрыт B7-правками

`_SYSTEM_NAME_FIELD` централизован в `domainAdapters/contract.py`,
читается во всех domainAdapters; локальный импорт в `relief.py` снят.

- **Цель:** wire-ключ `system_name` читается из одной константы.
- **ТЗ:** правило `dataModel-no-hardcode`; [packs §2](../../docs/tz_template_library_packs.md).
- **Файлы:** `domainAdapters/bodyPreparation.py`,
  `domainAdapters/templateBodyAdapter.py`, `domainAdapters/relief.py`.
- **Контракт:** все записи/чтения `system_name` в domainAdapters — через
  `_SYSTEM_NAME_FIELD`; локальный импорт в `relief.remap_body` → наверх.
- **Проверка:** `python -m unittest discover -s tests -p "test_library_packs_*.py"`;
  compileall.
- **Done:** литерал `'system_name'` в domainAdapters — только в
  объявлении константы.

### Шаг 4 — одна декларация location ref-полей ✅ закрыт B7-правками

`LOCATION_TEMPLATE_REF_KINDS` (field → kinds) — источник истины в
`refFields.py`; `LOCATION_TEMPLATE_REF_FIELDS` derive из ключей,
`remapRefs` читает ту же структуру.

- **Цель:** список persisted ref-полей и их допустимые kind'ы живут
  в одном месте.
- **ТЗ:** [packs §2](../../docs/tz_template_library_packs.md).
- **Файлы:** `domainAdapters/refFields.py`, `domainAdapters/remapRefs.py`.
- **Контракт:** одна структура (field → kinds), от неё derive:
  `LOCATION_TEMPLATE_REF_FIELDS`, `remap_named_location_refs`,
  `named_location_template_refs`, `_LOCATION_REF_KINDS`.
- **Проверка:** `python -m unittest tests.test_template_location_refs
  tests.test_bundle_remap tests.test_library_packs_b3`.
- **Done:** добавление ref-поля — одна правка; stale-комбинация
  невозможна конструкцией.

### Шаг 5 — зафиксировать политику missing-body (фиксация, не код) ✅ 2026-10-15

Выполнен: уточнение в [packs §5](../../docs/tz_template_library_packs.md)
(после списка состояний ref-поля), docstring `templateSnapshotLoader.py`,
docstring `resolve_fallback` в `domainAdapters/contract.py` — одна
формулировка.

- **Цель:** единая политика записана явно, не выводится из кода.
- **ТЗ:** [packs §5/§7](../../docs/tz_template_library_packs.md);
  правка ТЗ при отсутствии раздела.
- **Файлы:** docstring `templateSnapshotLoader.py`,
  `domainAdapters/contract.py` (`resolve_fallback`), при необходимости
  `docs/tz_template_library_packs.md` §5/§7.
- **Контракт:** «member без тела / битое тело / висячий ref → одна
  диагностика через `report_issues` + исключение из снапшота; runtime
  никогда не подставляет другой шаблон (relief `resolve_fallback`
  → `rejected`, R21)». race/perk — не pack-домены, политику не
  наследуют.
- **Проверка:** текстовая; ссылки из docstring сходятся.
- **Done:** формулировка одинакова в ТЗ и обоих docstring'ах.

### Шаг 6 — dedup relief prepare_body + warning для `world_import=None` ✅ закрыт B7-правками

`ReliefBodyPreparation` наследует `TemplateBodyPreparation` по паттерну
`PlotBodyPreparation` — `validate_world` делегирует `world_import`;
`world_import=None` → `WORLD_IMPORT_UNWIRED` через `report_issues`
(видно в тестовых WarningError). `ReliefPackAdapter` — тонкий.

- **Цель:** одна подготовка relief-тела на домен; отсутствие
  world-import сервиса — видимый warning, не silent skip.
- **ТЗ:** [relief — structure_refs/canal](../../docs/tz_terrain_relief.md);
  [packs §5](../../docs/tz_template_library_packs.md);
  [tz_logging](../../docs/tz_logging.md) (маршрут, L3).
- **Файлы:** `domainAdapters/relief.py`, `domainAdapters/factory.py`.
- **Контракт:** `ReliefBodyPreparation` наследует паттерн
  `PlotBodyPreparation` — `validate_world` делегирует `world_import`
  (внедряется в preparation, не в adapter); адаптер вызывает только
  preparation. `world is not None and world_import is None` → одна
  запись через `report_issues`/существующий маршрут (решение мастера:
  warning, не fail-fast, не `logging.getLogger`).
- **Проверка:** `python -m unittest discover -s tests -p "test_library_packs_*.py"`;
  `tests.test_library_write_service`.
- **Done:** identity/UUID-проверки не продублированы; unwired
  `world_import` оставляет диагностический след.

### Шаг 7 — `WriteRetentionPlanner.finish`: зоны + инварианты `_world` ✅ 2026-10-15

Выполнен: `finish` ~20 строк — композиция `_merged_catalog` →
`_retain_scope` → `_resolve_dependencies` → `_world`/`WorldWrite` →
`_diagnose_scope`; инварианты `_world` записаны в docstring
(независимость доменных проекций, `library_pins` — осознанный bypass
`resolve_world_column`). Проверка: `test_library_write_*` — 97 тестов OK.

- **Цель:** метод = одна ответственность; инварианты записаны.
- **ТЗ:** [packs §0.3/§1.2](../../docs/tz_template_library_packs.md);
  [scoped column write](../../docs/tz_json_validation.md).
- **Файлы:** `writeRetentionPlanner.py`.
- **Контракт:** `finish` — композиция `_retain_scope`,
  `_resolve_dependencies`, `_diagnose_scope` (или аналог); docstring
  `_world` фиксирует: проекции доменов независимы (`sorted(kind.value)` —
  детерминизм, не семантика); `library_pins` — осознанный bypass
  `resolve_world_column` с причиной; любая другая колонка обязана
  быть известна resolver'у.
- **Проверка:** `python -m unittest discover -s tests -p "test_library_write_*.py"`.
- **Done:** `finish` читается как список шагов; инварианты — в docstring.

### Шаг 8 — конвенция remap-helpers ✅ 2026-10-15

Выполнен: `remap_pins` → return-new projection (world-copy внутри,
caller присваивает); callers `relief.py` / `structure.py` /
`templateBodyAdapter.py` обновлены; конвенция записана в module
docstring `remapRefs.py`. Проверка: `test_library_write_*` 97 тестов +
`test_bundle_remap` — OK.

- **Цель:** одна конвенция в `remapRefs`.
- **ТЗ:** [packs §2](../../docs/tz_template_library_packs.md).
- **Файлы:** `domainAdapters/remapRefs.py` + callers (`relief.py`,
  `structure.py`, `templateBodyAdapter.py`).
- **Контракт:** `remap_pins` → return-new (решение мастера): возвращает
  новое значение `library_pins`, caller присваивает — согласуется с
  `model_copy`-стилем остальных helpers; форма — в module docstring.
- **Проверка:** `python -m unittest discover -s tests -p "test_library_write_*.py"`;
  `tests.test_bundle_remap`.
- **Done:** ни один caller не игнорирует значимый результат; стиль один.

### Шаг 9 — хардкоды: константы и дефолты моделей ✅ 2026-10-15

Выполнен: `UID_PART_SEPARATOR` экспортируется из `app.ids`
(`deterministicIds`) — 8 guard-сайтов (`memberOps`, `packOps`,
`manifest`, `writeContracts`, `writeSourceReader`, `authoringWrite`,
`legacyDomainSplit`, `legacyWorldPlan`); `version` default читается из
`LibraryPackRow.version` (`packOps`, `packService`); разделитель
`system_name` — `PACK_NAME_SEPARATOR` в `packIdentity.py` (используется
и в `packOps`); `source_file` — `SOURCE_FILE_BUNDLE` в
`worldData/bundle/__init__.py` (`reliefWorldImportService`,
`worldLibraries`); consumer-префиксы — `world_consumer` /
`named_location_consumer` / `WORLD_CONSUMER_PREFIX` /
`NAMED_LOCATION_CONSUMER_PREFIX` / `RELIEF_POLICY_FIELD` в
`lifecycleContracts` (callers: `refFields`, `referenceResolver`,
`writeRetentionPlanner`, `legacyWorldRefs`, `legacyWorldPlan`,
`remapRefs`). Проверка: `test_library_*` — 337 тестов OK.

- **Цель:** повторяющиеся литералы — одно имя.
- **ТЗ:** правило `dataModel-no-hardcode`; [packs §3](../../docs/tz_template_library_packs.md).
- **Файлы:** `memberOps.py`, `packOps.py`, `refFields.py`,
  `buildingTemplateLibraryService.py`, `reliefWorldImportService.py`,
  `libraryPacks/packService.py` (`version` default).
- **Контракт:** `'|'` — один guard/константа для local_uid и
  dependency uid; `version="1.0"` читается из `LibraryPackRow`, не
  повторяется; разделитель `system_name` — константа;
  `source_file="bundle"` — константа источника; consumer-префиксы —
  именованные константы/builder'ы.
- **Проверка:** `python -m unittest discover -s tests -p "test_library_packs_*.py"`.
- **Done:** литералы имеют одно имя; новый consumer-prefix не требует
  поиска по коду.

### Шаг 10 — `ReliefWorldImportService`: вынести world-ref валидаторы ✅ 2026-10-15

Выполнен: `reliefWorldRefValidation.py` — `validate_relief_world_refs`
+ приватные `_check_structure_refs`/`_check_structure_canal`; сервис
держит thin `validate_world_refs` (seam `ReliefBodyPreparation`
не изменён). Сервис — одна зона (import job + R34 sync). Проверка:
`test_library_packs_*` 221 тест + `test_fixture_bundle_import` — OK.
- **Цель:** сервис не смешивает import job с доменной валидацией
  structure refs.
- **ТЗ:** правило `class-size-limit`; `layer-boundaries`;
  [relief — structure refs](../../docs/tz_terrain_relief.md).
- **Файлы:** `reliefWorldImportService.py` (`_validate_structure_refs`,
  `_validate_structure_canal` → доменный relief world-ref валидатор,
  напр. рядом с `outlineCollect`).
- **Контракт:** сервис держит thin-вызов валидатора; правила
  barrier/canal — в доменном модуле с typed POJO.
- **Проверка:** `python -m unittest discover -s tests -p "test_library_packs_*.py"`;
  `tests.test_fixture_bundle_import`.
- **Done:** класс — одна зона (import job); валидаторы переиспользуемы
  preparation-слоем шага 6 без дублирования.

## Порядок и зависимости

Все шаги 0–10 закрыты — план завершён.
