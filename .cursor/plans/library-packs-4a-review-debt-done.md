# План: техдолг ревью шага 4a — library packs ✅ DONE

## Контекст

Ревью коммитов `a14f67b` (LibraryPackService + domain adapters, шаг 4a плана
[`library-packs-model-done.md`](library-packs-model-done.md)) и `096c222` (rename
импортов cascade + `default_pack_uids`). Архитектура в целом соответствует
правилам (facade + job, POJO как SoT); ниже — зафиксированные дефекты
чистоты ответственности, типизации и дублирования.

Проверки каждого шага: `python -m unittest` из `backend/`.

## Карта находок → шаги

| Находка | Файлы | Шаг |
|---|---|---|
| Дубль `_PLOT_ONLY_FIELDS` + plot/outline sniffing | `buildingTemplateLibraryService.py` ↔ `domainAdapters.py` | 1 |
| Дубль subject-check `resource/crops/livestock` | то же | 1 |
| `_body_structure_type` — getattr duck-typing поверх union; `upsert_outline` аннотация без `PlotLayoutTemplate` | `buildingTemplateLibraryService.py` | 2 |
| Идентичные `read_body`/`delete_body` в 3 адаптерах; `ensure/drop_pointer` отличаются только `registry_field` + entry-ctor | `domainAdapters.py` | 3 |
| `get_member` → приватный `_member_ops._require_member`; teardown членов в фасаде вместо `_MemberOps` | `packService.py` | 4 |
| `diagnose_missing` не возвращает missing → warning продублирован в 3 местах | `packService.py` | 5 |
| `default_pack_uids()` пересобирает frozenset на каждый write-гейт | `defaults.py` | 5 |
| `Any` на зависимостях адаптеров; `PackImportResult.bodies` нетипизирован; untyped overrides `import_fs_pack` | `domainAdapters.py`, `packService.py` | 5 |
| `LibraryPackService` ≈ 300 строк — на грани лимита, 4b/4c переполнят | `packService.py` | 6 |

## Вне scope (не долг этих коммитов)

- `from app.db.database import _in_transaction` — импорт приватного
  ContextVar, но это устоявшаяся проектная конвенция (~15 файлов:
  repositories, library services, `canonicalLibrary`). Отдельная тема,
  не блокирует.
- `_swap_pointer` — O(реестр) на каждый pointer; в `delete_pack` это
  O(members × registry). Принимается как известное ограничение transitional
  dual-write — реестры умирают в шаге 5b, оптимизировать не нужно.
- `SMOKE_003_SYSTEM_NAME` в `uidMap.py` — миграционная карта (файловый
  one-shot артефакт), не доменный default; перенос в `defaults.py` не
  требуется — там живут только declared defaults (ТЗ §3).

## Шаги

### Шаг 1 — единый building-body seam: parse + subject-check

- **Цель:** убрать два источника одного правила — разбор тела
  (outline vs plot) и проверка доменных субъектов живут только в
  `BuildingTemplateLibraryService`, адаптер — тонкий потребитель.
- **ТЗ:** `tz_template_library_packs.md` §0.2 (доменные ограничения —
  контракт адаптера); правило `dataModel-no-hardcode.mdc` (один источник
  builtin-логики).
- **Файлы:** `backend/app/application/worldData/buildingTemplateLibraryService.py`,
  `backend/app/application/worldData/libraryPacks/domainAdapters.py`.
- **Контракт:** на `BuildingTemplateLibraryService` публичные методы
  `parse_body(raw, *, ctx) -> BuildingTemplateOutline | PlotLayoutTemplate`
  (обёртка над `_library_body`, владеет `_PLOT_ONLY_FIELDS`) и
  `subject_issues(world, body) -> list` (цепочка
  `resource_types → crops → livestock.check_template_subjects`);
  `prepare_body` переиспользует `subject_issues`. `BuildingPackAdapter`
  вызывает `self._library.parse_body` / `self._library.subject_issues`,
  свои копии `_PLOT_ONLY_FIELDS`, sniffing и `_check_world_subjects`
  удаляются; issues мапятся в `LibraryPackValidationError` (канал ошибки
  сервиса паков, не `reject_unresolved`).
- **Проверка:** `python -m unittest tests.test_library_packs_4a` +
  `python -m compileall app/application/worldData` — зелёные; grep:
  `_PLOT_ONLY_FIELDS` и `check_template_subjects` встречаются в одном
  файле.
- **Done:** один источник parse/subject-check; поведение тестов не
  изменилось.

### Шаг 2 — typed denorm structure_type

- **Цель:** union `BuildingTemplateOutline | PlotLayoutTemplate`
  выражен типами, не getattr-цепочкой.
- **ТЗ:** `tz_template_library_packs.md` §3 (denorm-поля строки);
  `tz_building_generator.md` (plot/outline — два wire-shape домена).
- **Файлы:** `backend/app/application/worldData/buildingTemplateLibraryService.py`.
- **Контракт:** `_body_structure_type(body)` — `isinstance` по
  `PlotLayoutTemplate` → `body.plot_type.value`, иначе `body.structure_type`
  (property outline). Сигнатура `upsert_outline` — union-тип.
  Поведение значений не меняется (денорм-колонка — тот же текст).
- **Проверка:** `python -m unittest tests.test_library_packs_4a` —
  `test_building_member_crud`, `test_building_member_pointer_dual_write`
  зелёные; `compileall`.
- **Done:** getattr-цепочки нет, сигнатура честная.

### Шаг 3 — adapter mixins: body-CRUD + параметризованный pointer

- **Цель:** убрать три идентичных `read_body`/`delete_body` и два
  почти идентичных `ensure/drop_pointer`; stringly-typed
  `registry_field` заменить ClassVar.
- **ТЗ:** `tz_template_library_packs.md` §0.2 (адаптер = body + pointer
  контракт домена).
- **Файлы:** `backend/app/application/worldData/libraryPacks/domainAdapters.py`.
- **Контракт:** `_LibraryBodyMixin` — общие `read_body`/`delete_body`
  через `self._library` (find_by_uid/dict(row.data)/delete). Все три
  адаптера наследуют его. `_RegistryPointerMixin` получает
  `registry_field: ClassVar[str]` и абстрактный
  `_pointer_entry(member, outline)`; `ensure_pointer`/`drop_pointer`
  реализованы один раз в mixin, адаптеры объявляют только ClassVar +
  entry-фабрику. `_swap_pointer` больше не принимает `registry_field`
  параметром и не ветвится по строке — реестр резолвится по
  `self.registry_field` через тот же worldRow-аксессор (if/else по
  ClassVar допустим как один dispatch, либо маппинг field→accessor).
- **Проверка:** `python -m unittest tests.test_library_packs_4a` —
  dual-write тесты (`test_world_member_visible_to_registry_readers`,
  `test_building_member_pointer_dual_write`,
  `test_delete_world_pack_drops_pointers`) зелёные.
- **Done:** тело каждого адаптера — только доменная специфика
  (validate + entry), общие механики в mixins.

### Шаг 4 — member-ops seam

- **Цель:** приватный контракт `_MemberOps` не торчит в фасад;
  mass-teardown членов — зона member write path, не фасада.
- **ТЗ:** `tz_template_library_packs.md` §0.2 (member CRUD — единый
  job); `class-size-limit.mdc` (одна зона на job).
- **Файлы:** `backend/app/application/worldData/libraryPacks/packService.py`.
- **Контракт:** `_MemberOps._require_member` → публичный
  `require_member`; `get_member` использует его без подчёркивания.
  Цикл drop_pointer/delete_body из `delete_pack` переезжает в
  `_MemberOps.teardown(members, world) -> list[str]` (возвращает
  orphan-диагностику); фасад `delete_pack` только гейты + вызов +
  delete pack row + отчёт.
- **Проверка:** `python -m unittest tests.test_library_packs_4a` —
  `test_delete_world_pack_drops_pointers`,
  `test_delete_engine_pack_does_not_break_worlds` зелёные.
- **Done:** фасад не знает о per-member teardown-механике.

### Шаг 5 — diagnostics + typing micro

- **Цель:** один эмиттер «missing dependencies»; write-гейт без
  пересборки множества; типы на швах.
- **ТЗ:** `tz_template_library_packs.md` §3 (missing dependency —
  диагностика, не блок).
- **Файлы:** `backend/app/application/worldData/libraryPacks/packService.py`,
  `.../libraryPacks/defaults.py`, `.../libraryPacks/domainAdapters.py`.
- **Контракт:** `diagnose_missing` возвращает `set[str]` missing —
  `create_pack`/`_import_fs_pack`/`set_dependencies` используют его
  вместо собственных блоков логирования. `default_pack_uids()` →
  module-level frozenset (вычисляется один раз при импорте —
  декларация `_DECLARED_DEFAULT_PACKS` константна). Конструкторы
  адаптеров типизируются конкретными сервисами
  (`ReliefTemplateLibraryService`, `StructureTemplateLibraryService`,
  `BuildingTemplateLibraryService`, `WorldService`,
  `ReliefWorldImportService | None`); `import_fs_pack` outcome —
  типизированный контракт (typed dataclass/результат FS-импортёров),
  `PackImportResult.bodies` получает его тип вместо `tuple[Any, ...]`.
- **Проверка:** `python -m unittest tests.test_library_packs_4a` —
  `test_missing_dependencies_diagnosed_not_blocked`,
  `test_fs_import_creates_engine_library` зелёные; grep `Any` в
  сигнатурах адаптеров пуст (кроме `outline: Any` контракта).
- **Done:** diagnostics едины, швы типизированы.

### Шаг 6 — фасад: вынос pack-CRUD в `_PackOps`

- **Цель:** `LibraryPackService` вернуть под порог — pack-level CRUD
  переезжает в `_PackOps` по образцу `_MemberOps`, фасад остаётся
  thin delegation. Выполнить до старта шага 4b родительского плана —
  remap-операции иначе переполнят фасад.
- **ТЗ:** `tz_template_library_packs.md` §0.2/§3; `class-size-limit.mdc`.
- **Файлы:** `backend/app/application/worldData/libraryPacks/packService.py`.
- **Контракт:** `_PackOps(scope)` владеет create/get/find/list/
  update_metadata/delete/set_dependencies/missing_dependencies/
  import_fs_pack; публичный API фасада и сигнатуры не меняются —
  pure move внутри файла. Тело фасада после шага < 150 строк.
- **Проверка:** `python -m unittest tests.test_library_packs_4a`
  tests.test_library_packs_b3 — зелёные.
- **Done:** фасад под порогом, шаг 4b стартует с чистого слоя.
