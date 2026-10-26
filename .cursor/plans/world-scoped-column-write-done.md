# Scoped world-column write — plan ✅ DONE

- **Status:** W2-0…W2-4, G-1 и отдельный PBF-1…PBF-3 выполнены 2026-10-16; временное исключение packBakeFinalize снято.
- **Depends on:** `.cursor/plans/worlddata-http-decoupling-done.md` — ✅ выполнен 2026-10-11 (единый класс доменных ошибок на месте), вход разблокирован
- **Актуализация 2026-10-16:** после 5b/B6–B7 прежние building/relief registry-writers и adapter pointer dual-write удалены. W2-3 мигрировал пять оставшихся вызовов мастерского update; W2-4 закрыл аудит scoped-контракта prepared pipeline и недостающее покрытие.

## Контекст

Исходная проблема до W2/L-4/5b — два шва записи в `worlds`:

- `WorldService.update` — семантика мастер-PATCH: merge → полный normalize всех ~45 facade-слайсов + REF-W → save. Внутренний писатель одной колонки платит полной ревалидацией и требует валидности чужих колонок (D9 был первым триггером).
- `IWorldRepository.update` — raw full-row save, ноль валидации (pack-адаптеры: `_swap_pointer`, `remap_world_refs`).

Целевая середина: валидация **только пишущейся колонки** через её slice-POJO, запись в транзакции caller'а. W2-1 добавил `resolve_world_column` / `apply_world_column`; библиотечный pipeline резолвит world-колонки при подготовке и применяет их через `apply_prepared_world_columns`. Одиночные писатели мигрированы, покрытие prepared-пути проверено в W2-3/W2-4.

Рамка (утверждено мастером):

- Вид 1 изменений (библиотека/конфиг мира = колонки `worlds`) — scoped write; `worlds.update` остаётся только мастер-PATCH/импорт.
- Вид 2 (состояние внутри мира — клетки, здания, дороги, флора, поселения) — доменные persist-сервисы, `worlds` не трогают. Отдельный план под runtime worldEdit (состояние зданий).
- Шов — НЕ метод `WorldService`: запись колонки — typed persistence-примитив, не оркестрация документа. Два явных примитива, не один вызов.
- Таблица инвалидаций — реестр в `worldData`, не на `WorldSlice` (jsonValidation не именует domain-таблицы).
- Решение 2026-10-12: POJO-покрытие и последствия изменения — независимые реестры. `fine_cells_per_map_cell` пока намеренно вне `WorldSlice`; перенос technical-контракта в POJO — отдельный шаг G-1 ниже, не зависимость W2-1…W2-4.

## Контракт

### Примитив 1 — resolve (jsonValidation)

```python
# worldSliceMerge.py или новый модуль рядом — чистый resolve, без I/O
def resolve_world_column(key: str, raw: Any, ctx: ResolveContext) -> dict[str, Any]:
    world_slice = WORLD_SLICE_BY_KEY.get(key)  # точное имя аксессора уточнить
    if world_slice is None or not world_slice.facade:
        raise ValueError(f"world column {key!r} is not a writable facade slice")
    # Диспетчеризация по форме слайса: атомарная колонка / независимый
    # скаляр / поля с общим инвариантом POJO — контракт ниже.
    # Результат содержит только явно изменяемые колонки.
```

- Supplied = atomic: caller передаёт колонку целиком; `resolve_root_list` материализует canonical overlay + dump — та же семантика, что у facade-merge.
- `wire_adapter` (legacy dict-map и т.п.) работает на том же пути, что импорт.
- **Политика значений — только на POJO (решение 2026-10-12):** default, missing, null и ограничения берутся из соответствующей модели через общий resolver, с той же семантикой, что импорт. Универсальной замены `None` на default и собственной null/default-политики в scoped write нет. Отсутствие колонки в операции — «не менять»; defaults resolve не расширяют область записи. Вопрос о выборе отдельной scoped-политики `None` закрыт.
- Проверить существующие early-return/skip при `None` в общем merge на соответствие POJO. Если они обходят контракт модели, исправить общий `worldSliceMerge` / resolver-путь для импорта и scoped write; не добавлять специальную ветку обработки null в `resolve_world_column` / `apply_world_column`.
- **Действующие политики POJO (сверено с кодом 2026-10-12):** источник — `annotationPolicy.py` и исходная Pydantic-схема; исполнение — общий `resolve_model` / `resolve_patch`. `DefaultWhenMissing` / `DefaultEnumWhenMissing`: missing полного объекта → schema default; supplied invalid → ошибка. Явный null при `T | None` сохраняется как `None`, при non-nullable `T` отклоняется, без default. `IgnoreOnWire` — wire as-is, без отдельного policy-автозаполнения; required/nullable/schema defaults определяет исходная модель, ошибки и явный null не пропускаются из-за имени Ignore. `StrictOnWire` / `StrictEnumOnWire` не дают error default. Legacy `DefaultOnWire` / `DefaultEnumOnWire` — aliases missing-only политики, metadata `DEFAULT` deprecated. Общей политики «null → сброс к default» нет; W2 её не добавляет. Отсутствующая колонка scoped-операции не меняется; допустимые `false`/`0`/пустые коллекции не считаются отсутствием. Root-коллекции используют существующий общий slice-контракт `empty_factory` / canonical overlay, проверяемый отдельно от field-политик.
- **Multi-column (решение 2026-10-12):** независимый скаляр проверяется отдельно по контракту поля исходного POJO через общий resolver; невалидный независимый сосед не блокирует изменение. Поля с общим инвариантом POJO проверяются совместно на итоговых значениях (существующие нужные поля + явно переданные изменения). Связность определяется POJO, без параллельных локальных правил; совместное нахождение в классе не является инвариантом. Для совместной проверки caller передаёт существующие значения нужных полей в чистый resolve (расширение параметров уточняется при реализации, без I/O). Возврат всегда `dict[str, Any]` только явно изменяемых колонок; defaults/нормализация соседей не расширяют запись и не выполняют repair. Для registry / JSON blob атомарна целая колонка, для отдельного скаляра — переданное значение; `partial=False` не означает обязательную полную проверку всех соседей multi-column.

### Примитив 2 — apply (worldData, свободная функция)

```python
# backend/app/application/worldData/worldColumnWrite.py (~50 строк)
COLUMN_INVALIDATES: dict[str, frozenset[str]] = {
    "fine_cells_per_map_cell": frozenset({"map_cells"}),
    # + колонки, влияющие на доменные таблицы — по мере выявления
}

def apply_world_column(world: World, key: str, raw: Any, ctx) -> frozenset[str]:
    """resolve → setattr на World. Возвращает имена инвалидированных таблиц.
    Транзакция и repo.update — у caller'а."""
```

- Не сервис, не класс — module-level функция. `World` + repo у caller'а.
- Возврат `invalidated` — caller (persist-сервис) решает, что чистить; как route решает `map_cells_invalidated` сегодня.
- После resolve сравниваются старые и новые нормализованные значения фактически записываемых колонок. Возврат — объединение `COLUMN_INVALIDATES` только для изменённых колонок; запись равного значения возвращает пустой набор. Если результат resolve записывает несколько колонок, сравнить каждую.
- Общий чистый helper расчёта инвалидаций живёт рядом с реестром и используется как scoped apply, так и мастер-путём (шаг 2). Сохранение, очистка и транзакция принадлежат caller'у; `force` — политика мастерской операции.

### Кейсы использования

- **Одиночная колонка** (bind-writers): `apply_world_column(world, k, rows)` → `repo.update(world)` — одна строка записи.
- **Мультиколонка без prepared-плана:** `apply` ×N → один `repo.update` — атомарность у caller'а; до сохранения все изменения должны пройти проверку. Актуальный library pipeline использует следующий prepared-паттерн.
- **Prepared-мультиколонка** (актуальный library pipeline после L-4/L-5/5b): адаптеры проектируют refs/pins и relief `terrain_registry` / `relief_pick_policy`; planner резолвит итоговые изменённые facade-колонки, executor вызывает `apply_prepared_world_columns` → один `repo.update` на мир. Повторной нормализации на apply нет. Legacy building/relief template registry больше не существует.

### Что НЕ мигрирует

- `PUT /worlds/{uid}` — мастер-PATCH, полная ревалидация намеренна.
- `import_from_json` / `prepare_import` / bundle — whole-document contract.
- `repairWorldDefaults` — repair-путь, решается отдельно.
- Прежнее исключение `packBakeFinalize` снято отдельным PBF-1…PBF-3 (2026-10-16): три колонки покрыты facade POJO, finalizer использует scoped apply + repository в caller UOW; actual root/cache и atomic manifest save проверены. См. [`pack-bake-finalize-scoped-write-done.md`](pack-bake-finalize-scoped-write-done.md).

### Инварианты

- Шов не владеет транзакцией и не делает `repo.update` сам (как `PackDomainAdapter`).
- Колонка вне `WORLD_SLICES` facade — не пишется через шов (контракт расширяется только через dataModel).
- Invalid rows never disappear — reject с индексом, как сегодня.
- Контракт ошибок данных scoped resolve/apply — `ImportValidationError` с сохранением списка `FieldPathError`, путей, индексов строк, schema и code (решение 2026-10-12). Не сворачивать диагностику POJO в текстовый `WorldDataValidationError`; ошибки библиотечной операции остаются в контракте `libraryPacks`.
- Каждая колонка в `COLUMN_INVALIDATES` обязана существовать среди полей `World` (тест-гарда); принадлежность к `WORLD_SLICE_BY_KEY` не требуется.
- Наличие колонки в `COLUMN_INVALIDATES` не разрешает scoped write. `resolve_world_column` независимо требует facade-слайс; `fine_cells_per_map_cell` до G-1 отклоняется. Специальной ветки с вызовом `WorldService._validate` в scoped-примитивах нет.

## Шаги

### Шаг 0 — правка ТЗ (до кода) — выполнен 2026-10-11

- Цель: зафиксировать третий вид write-входа в `docs/tz_json_validation.md` — новый подраздел «Scoped column write (internal)» под § «Import path (write)»: два write-модели (мастер-PATCH full-doc vs internal scoped single-column), примитивы resolve/apply, supplied=atomic, владение `COLUMN_INVALIDATES` в worldData, запрет вне-facade колонок, инвариант «шов не владеет транзакцией».
- ТЗ: `tz_json_validation.md` § «Import path (write)», § «WorldSlice (целевой реестр)», § «Normalize vs reject».
- Файлы: `docs/tz_json_validation.md`.
- Проверка: ссылки из плана резолвятся в раздел ТЗ.
- Done: раздел существует, план ссылается на него.

### Шаг 1 — примитивы + реестр инвалидаций — выполнен 2026-10-12

- Реализовано: `jsonValidation/worldColumnResolve.py::resolve_world_column(..., existing=...)`, общий `resolve_model_field` на исходной Pydantic field schema, `worldData/worldColumnWrite.py::apply_world_column` и `invalidated_world_tables`. Независимое поле сохраняет atomic nested validation; модельный/root-валидатор POJO требует проверки итогового слайса с текущими значениями caller'а. Возврат содержит только явно изменяемую колонку.
- Общий merge больше не пропускает явный null у JSON blob: исходный POJO отклоняет его. Null после legacy registry-адаптера проходит общий root-контракт `empty_factory`, как прочие реестры. Scoped-специфичных null/default правил нет.
- Проверено: 18 новых тестов `test_world_column_write`; regression `test_world_row_t28`, `test_runtime_world_edit_policy`, `test_policy_field_migration`, `test_policy_revision_r1_r3`, `test_import_validation_policy`, `test_world_seam`, `test_building_registry_mixed`. W2-2…W2-4 и G-1 не реализованы этим шагом.

- Цель: `resolve_world_column` (jsonValidation) + `worldColumnWrite.py` (worldData): `apply_world_column` + `COLUMN_INVALIDATES` + общий чистый расчёт инвалидаций по фактическим изменениям.
- ТЗ: `tz_json_validation.md` § «Scoped column write (internal)», § «WorldSlice (целевой реестр)».
- Файлы: `worldSliceMerge.py` (или новый `worldColumnResolve.py`), новый `worldData/worldColumnWrite.py`.
- Проверка ошибок: невалидные данные resolve/apply дают `ImportValidationError` с исходной структурированной диагностикой; до успешного resolve `World` не изменяется.
- Проверка multi-column: изменение скаляра сохраняет соседние настройки и проходит при невалидном независимом соседе; общий инвариант POJO проверяется на итоговом сочетании значений и отклоняет несовместимое изменение до мутации. Результат resolve содержит только явно изменяемые колонки, defaults не выполняют скрытый repair.
- Проверка действующих политик: `DefaultWhenMissing` при missing полного объекта использует schema default, nullable null сохраняет, non-nullable null отклоняет; `IgnoreOnWire` не обходит schema validation. Нет новой ветки «null → default». Допустимые `false`/`0`/пустая коллекция не подменяются default полей; отсутствующая колонка scoped-операции не меняется. Root-коллекции проверяются по существующему slice-контракту отдельно от field-политик.
- Проверка POJO-политики: missing/default/явный null разрешаются по контракту конкретной модели одинаково в общем import-merge и scoped resolve; nullable null сохраняется, недопустимый null отклоняется, подстановка default выполняется только когда объявлена контрактом POJO. Проверить пути `registry_list`, `registry_dict`, `json_blob`, `multi_column`, включая существующие skip при `None`; отсутствие другой колонки не приводит к её перезаписи defaults.
- Проверка: юнит-тесты resolve (валидная/невалидная колонка, non-facade ключ, multi-column слайс); guard «ключи COLUMN_INVALIDATES ⊆ поля World»; technical-колонка в реестре допустима, но scoped write `fine_cells_per_map_cell` отклоняется до G-1. Расчёт: равные значения → пустой набор; изменённые → объединение последствий, включая все фактически записанные колонки.

### Шаг 2 — worlds.update читает COLUMN_INVALIDATES — выполнен 2026-10-13

- Реализовано: `WorldService.update` считает последствия через `invalidated_world_tables(world_wire_from_row(original), world_wire_from_row(world))`; `requires_force`/`map_cells_invalidated` выводятся из `"map_cells" in invalidated`, warning сохраняет значения до/после. Хардкод-сравнение `fine_cells_per_map_cell` удалено.
- Проверено: 4 новых service-теста `test_world_column_write` (равный размер / изменён без force / с force / unrelated). Regression `test_world_row_t28`, `test_runtime_world_edit_policy`, `test_policy_field_migration`, `test_policy_revision_r1_r3`, `test_world_seam`, `test_building_registry_mixed` зелёные. Pre-existing: 2 теста `test_import_validation_policy` падают и на чистом HEAD (`import_bundle` не пишет `world_defaults_test` мир), не связано с шагом.


- Цель: заменить хардкод-сравнение `fine_cells_per_map_cell` в `worldService.update` на общий helper и реестр — один источник политики инвалидаций. Сравнивать исходное состояние с нормализованным результатом мастер-PATCH; technical-колонки участвуют независимо от наличия facade-слайса.
- ТЗ: `tz_json_validation.md` § «Import path (write)» (точка входа `PUT /worlds/{uid}`); `project_data_storage_tz.md` — колонки `worlds`/map_cells.
- Файлы: `worldService.py`, `worldColumnWrite.py`.
- Проверка: существующее поведение `map_cells_invalidated` и `requires_force` сохранено; равный размер клетки не требует `force` и не инвалидирует `map_cells`, изменённый требует подтверждения, после подтверждения сообщает очистку. Добавление POJO для размера клетки на этом шаге не требуется.

### Шаг 3 — миграция оставшихся одиночных писателей, паттерн A — выполнен 2026-10-16

- Реализовано: все пять сайтов переведены на `apply_world_column` + repository update; DI race/perk/relief получает `IWorldRepository`. Общий `worldLookup.require_world` сохраняет `WorldDataNotFoundError` при отсутствии мира. Ошибки чтения целевого race/perk registry преобразуются в `ImportValidationError` с исходными issues, индексами, schema/code. Relief sync используется legacy-путём; проекция собирается на копии, чтобы не мутировать загруженный мир до успешной проверки.
- Приёмка: `test_world_scoped_writers` — 6 тестов, включая реальный SQLite/Container bind/unbind, duplicate-bind/no-op, посторонние невалидные колонки, structured rejection без сохранения и relief sync без мутации при ошибке. `test_world*.py` — 93 теста до добавления SQLite-кейса, затем новый модуль целиком зелёный; `test_e6_consumers` — 13, `test_pack_bake_modes` — 20. Конкретные требования шага ниже сохранены как критерии приёмки.

- Вход: W1, W2-1 и W2-2 выполнены; 5b завершён. Состав сверён с кодом 2026-10-16: пять вызовов `WorldService.update` вместо прежних семи.
- Цель: заменить мастерский update на `apply_world_column(world, key, raw, ctx)` + `world_repository.update(world)`. Чтение мира, сохранение, транзакция и обработка последствий остаются у caller'а; зависимость от `WorldService` сокращается до repository и нужных helpers. Обновить DI wiring и test doubles этих сервисов.
- Сайты: `worldPerkService.py::_ensure_registry` / `_unbind_registry` (`perk_template_registry`); `raceService.py::_ensure_registry` / `_unbind_registry` (`race_template_registry`); `reliefWorldImportService.py::_sync_terrain_from_outline` (`terrain_registry`). Проверить вызывающий путь relief sync; если helper уже недостижим, удалить его и лишние зависимости вместо миграции мёртвого кода.
- `buildingTemplateLibraryService.py` исключён: после B6/B7 availability определяется membership, world registry-writer удалён. У relief legacy template registry также удалён; возвращать эти записи нельзя.
- ТЗ: `tz_json_validation.md` § «Scoped column write (internal)» (паттерн A — одиночная колонка).
- Проверка: bind/unbind, duplicate-bind/no-op и relief terrain sync сохраняют поведение; изменение валидной колонки проходит при невалидной посторонней facade-колонке. Невалидная целевая колонка даёт структурированный `ImportValidationError` до сохранения, строки не исчезают. Сохранение затрагивает только целевую колонку; не добавлять repair соседей. Проверить существующие профильные тесты и `test_world_column_write`.
- Done: пять сайтов мигрированы либо подтверждённо удалены как недостижимые; в этих сервисах нет мастерского update для внутренних колоночных записей; DI и проверки зелёные. Это открывает приёмку W2-4.

### Шаг 4 — аудит и закрытие prepared pack-write, паттерн B — выполнен 2026-10-16

- Аудит: building/plot/structure проецируют `library_pins`; relief дополнительно `relief_pick_policy` и `terrain_registry`. Изменяемые колонки проверяются в planner, единственная запись мира в library pipeline — executor через prepared apply. Delete member/pack не переписывает мир: сохраняет текущую политику in-use/diagnostics. Актуальные колонки W2-3/W2-4 не пересекаются с `COLUMN_INVALIDATES` (`fine_cells_per_map_cell`), последствий для очистки доменных таблиц сейчас нет.
- Исправлено: stale/отсутствующий мир проверяется до любых executor SQL-записей, отсутствие мира даёт `LibraryPackConflictError`. Prepared apply сохраняет свежие значения чужих колонок без повторного resolve. Валидация итоговых pins сохраняет путь `library_pins[index].field` и отдаёт `ImportValidationError` с исходными issues.
- Приёмка: 6 новых `test_library_world_column_write` (prepare без SQL; invalid final column; prepared apply без resolve с одним save; stale/deleted world до записей; caller rollback; запрет non-facade и pin POJO). Library discovery: 336 тестов прошли, один модуль первоначально не загрузился из-за старого `_remap_relief_pick_policy`; импорт обновлён на `remap_relief_pick_policy`, все 7 тестов `test_library_pack_refs` затем прошли. Всего проверено 343 library-теста. Повторный поиск внутренних мастерских update оставил только объявленное исключение `packBakeFinalize`.

- Вход: W2-3; L-4/L-5 и 5b уже изменили реализацию. `_swap_pointer` / `remap_world_refs` и registry dual-write удалены, поэтому прежняя механическая миграция этих методов больше не применяется.
- Текущий путь: `domainAdapters/*::prepare_world_refs` → `writeRetentionPlanner.py::_world` → prepared world changes → `writeExecutor.py::apply` → `apply_prepared_world_columns` + один repository update на мир. Planner вызывает `resolve_world_column` для изменённых facade-колонок. `library_pins` — явное исключение из facade resolve: planner валидирует записи через `LibraryPinEntry` и сохраняет canonical dumps.
- Цель: проверить все изменяемые world-колонки и пути instantiate/copy/replace/remap/delete в этом pipeline; закрыть найденные обходы подготовки или сохранения. Использовать существующий `apply_prepared_world_columns`, не заменять его на повторный `apply_world_column` в executor. Проекции могут менять рабочую копию мира; сохранение допустимо только после успешной подготовки всех изменений.
- Согласование с L-4/L-5: итоговые значения нормализуются и проверяются до записи; executor применяет prepared-значения без повторной нормализации. Защитные проверки не меняют подготовленные значения. Ownership/dependencies/refs/copy/replace/stale и UOW остаются ответственностью библиотечного pipeline. Проверить, что последствия из общего реестра инвалидаций не теряются; очисткой при необходимости владеет caller.
- ТЗ: `tz_json_validation.md` § «Scoped column write (internal)» (паттерн B — мультиколонка); `tz_template_library_packs.md` §2; `library-write-l4-architecture.md` (prepared apply).
- Файлы: `libraryPacks/writeRetentionPlanner.py`, `writeExecutor.py`, `writePlanContracts.py`, `domainAdapters/contract.py`, `domainAdapters/remapRefs.py`, `domainAdapters/relief.py`, `domainAdapters/structure.py`, `domainAdapters/building.py`, `domainAdapters/plot.py`, `worldColumnWrite.py`. `domainAdapters/mixins.py` проверить на отсутствие возврата pointer dual-write.
- Проверка: существующие `test_library_write_plan`, `test_library_write_service`, `test_library_write_policy`, `test_library_pack_refs`, `test_library_packs_4b`, `test_library_packs_4c`, `test_library_packs_4d`, профильные `test_library_packs_5b_*` и `test_world_column_write`. Число тестов не фиксировать: старые «108 pack-тестов + test_building_registry_mixed» не описывают актуальную приёмку после удаления registry.
- Доказать тестами или существующим покрытием: invalid final column отклоняется до SQL-записей; pins проходят собственный POJO-контракт; посторонняя невалидная колонка не блокирует scoped-изменение; executor сохраняет подготовленные значения без второго resolve, не перетирает чужие колонки, обнаруживает stale-состояние и работает в caller UOW; ошибка откатывает все связанные записи. Добавлять только отсутствующие проверки.
- Done: все актуальные adapter world writes проходят prepare → prepared apply; нет raw persistence обходов и повторной нормализации в executor; исключение `library_pins` явно покрыто. Провести итоговый поиск внутренних `WorldService.update` и сверить каждый остаток с разделом исключений.

## Отдельный шаг G-1 — POJO настроек сетки — выполнен 2026-10-16

- Анализ и приёмка: [`world-grid-settings-g1-analysis-done.md`](world-grid-settings-g1-analysis-done.md). Реализован согласованный объём: только `fine_cells_per_map_cell` в `WorldGridSettings`, без изменения допустимых значений; padding и pack metadata — отдельные задачи. Прямой `prepare_import` использует общий grid-slice resolver до конструктора World; ручной блок размера удалён. Дубли terrain-проверок сохранены: strictness POJO и сервиса расходится.
- Реализовано: strict POJO с существующим default, facade slice, runtime accessor/export, startup guard, structured ошибки на всех write-входах. Scoped size write разрешён; `map_cells` возвращается только при изменении. Существующий force-контракт сохранён.
- Проверено: 183 теста, включая 11 новых grid-кейсов и regression world/import/bundle copy/pack bake/policies/prepared world write. Все прошли; прежние pre-existing import validation failures не воспроизвелись. ТЗ актуализировано, включая исправление устаревшего `map_subsurface_depth ≥10` на ≥0 по профильному ТЗ.
- Цель: перенести существующий контракт допустимости единственного поля `fine_cells_per_map_cell` из ad-hoc technical validation в `WorldGridSettings` + facade `WorldSlice`, без переименования wire/SQL-поля и без изменения допустимых значений.
- ТЗ: `tz_json_validation.md` § «Technical validation (SCH-WORLD-ROW-TECH)», § «WorldSlice (целевой реестр)», § «Scoped column write (internal)».
- Файлы: новый `dataModel/worldPack/worldGridSettings.py::WorldGridSettings` и wire projection; `worldSlices.py`; `worldRow.py`; startup guard в `core/app.py`; `worldService.py`; тесты контракта.
- Единый владелец допустимости значения — POJO. После подключения всех write-путей удалить дубли соответствующих ограничений из `WorldService._validate`; существующие ограничения `WorldTerrainScalars` не копировать в новый POJO. Сервис сохраняет orchestration, `worldData` — инвалидации.
- Проверка: строгий int без bool, ≥1000, кратно 1000; одинаковый контракт допустимости на create/import/master-PATCH/scoped write; после регистрации слайса scoped write размера клетки доступен и возвращает `map_cells` только при изменении. Мастерское подтверждение `force` сохраняется.
- Отдельно проверить устаревшие формулировки technical-раздела (например, нижнюю границу `map_subsurface_depth`) по профильному ТЗ; перенос POJO не является разрешением менять числовые ограничения.
- Вне G-1: перенос очистки `map_cells` из route в атомарную orchestration. Сейчас route очищает после сохранения мира; вопрос общей транзакции требует отдельного решения и не расширяет W2-1.

## Done (W2-1…W2-4; G-1 отдельно)

- Одиночные писатели W2-3 проходят slice-POJO через scoped apply; библиотечные world writes W2-4 — через prepare + prepared apply. `library_pins` проверяется через `LibraryPinEntry` при подготовке.
- В охвате W2-3/W2-4 нет внутренних вызовов мастерского `WorldService.update`. Мастер-PATCH/импорт и отдельный repair-путь сохраняют свои контракты. Прежнее исключение `packBakeFinalize` снято отдельным завершённым PBF-планом; не является скрытой частью W2.
- Инвалидации — один реестр в worldData, читаемый и мастер-путём, и scoped-швом.
