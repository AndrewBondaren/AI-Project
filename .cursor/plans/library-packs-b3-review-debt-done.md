# Library packs — техдолг ревью шага 4b (commit 625f786) — DONE

Шаги 1–3 исполнены и проверены (108/108 unittest). D8 waived, D9 —
отдельный scope `jsonValidation`, перенесён в «Не шаги» как запись долга.

Источник: ревью коммита `625f786` — `instantiate_pack` / `copy_pack`,
remap engine→world / publish world→engine ([`docs/tz_template_library_packs.md`](../../docs/tz_template_library_packs.md) §2).

Файл = фиксация техдолга + атомарные шаги исправления. Шаги исполняются
по одному, каждый — отдельный заход (code-gates).

## Техдолг

| # | Что | Где | Шаг |
|---|---|---|---|
| D1 | Дубль гейта идентичности пака (~25 строк): strip→required→`library_uid(LIBRARY_PACKS)`→`is_default_pack_uid`→`get_by_uid`/`get_by_system_name`→`insert`+IntegrityError→Conflict повторён в `_PackOps.create` и `_RemapOps._copy` | `packService.py` | 1 |
| D2 | Wire-ключи литералами там, где есть POJO: `system_template_uid` ×3 (`_remapped_registry`, `_swap_pointer`), `main_building`/`secondary_buildings`/`structure` (`_remap_structure_refs`), `default_template_uid` (`_remap_relief_pick_policy`), `system_name` (`StructurePackAdapter.remap_body`). Raw-dict как контейнер оправдан (см. ниже), ключи — нет (`dataModel-no-hardcode`) | `domainAdapters.py` | 2 |
| D3 | Асимметрия доступа к `relief_pick_policy` в одном адаптере: `member_usages` — typed (`relief_pick_policy(world)` + `getattr`), `_remap_relief_pick_policy` — raw dict той же колонки | `domainAdapters.py` | 2 |
| D4 | Дубль `setattr + _remapped_registry + update` в `_RegistryPointerMixin.remap_world_refs` и `ReliefPackAdapter.remap_world_refs` | `domainAdapters.py` | 3 |
| D5 | `scope.worlds.get_by_id` в refetch `_RemapOps._copy` — `HTTPException(404)` из API-слоя внутри application-транзакции; мир уже проверен, нужен `find_by_id` | `packService.py:822` | 3 |
| D6 | Два `find_by_uid` на член в `_copy` (`read_body` + `body_source_file`) | `packService.py:787-802` | 3 |
| D7 | `RemappedMember.outline: Any` — есть доменный union по образцу `DomainLibrary` | `domainAdapters.py:73-76` | 3 |
| D8 | `InstantiateTests` = 290 строк — waived: тест-кейс с фикстурами вне порога `class-size-limit` | `test_library_packs_4b.py` | — |

### D9 — найден ревью, вне зоны коммита (отдельный scope)

`worlds.update` → `normalize_world` → `merge_facade_slices` →
`resolve_root_list(WorldBuildingTemplateRegistry)` отклоняет миры, у
которых `building_template_registry` содержит embedded
`PlotLayoutTemplate`-строки (нет `system_template_uid:
StrictOnWire[str]`). Следствие: **любой** update такого мира падает 422,
включая `BuildingTemplateLibraryService._ensure_registry`, который всё
ещё идёт через `worlds.update`. Текущий коммит обходит это repo-write —
обосновано и задокументировано, но сама landmine остаётся. Зона:
`jsonValidation` (union entry-model или tolerant slice) — требует
отдельного плана, не входит в шаги ниже.

## Контекст для правок (не дублировать расследование)

- `building_template_registry` — гетерогенная колонка: pointer-строки
  (`system_template_uid`) + embedded plot-строки. Дискриминатор —
  наличие `system_template_uid`, тот же что в
  `world_building_layout_overrides` (`worldRow.py:244-281`).
- Дискриминатор тел building: `_PLOT_ONLY_FIELDS.intersection(raw)` —
  `buildingTemplateLibraryService.py:35`, используется `parse_body`.
- POJO: `PlotLayoutTemplate` / `BuildingBodyTemplate.structure:
  StrictOnWire[StructureKey]` — `frozen=True`, `extra="ignore"` →
  мутация через `model_copy(update=…)`, dump overlay поверх исходного
  dict сохраняет unknown keys.
- `ReliefContextPickPolicy.default_template_uid` — то же: frozen,
  `extra="ignore"` → `model_validate` → `model_copy` → overlay.
- `ReliefTemplateRegistryEntry` и `BuildingTemplateRegistryEntry`
  разделяют имя поля `system_template_uid`.

## Шаг 1 — общий гейт идентичности пака

**Цель.** Одна точка проверки `system_name → pack_uid → default →
uniqueness` для create и remap.

**ТЗ.** `tz_template_library_packs.md` §2 (UID только центральной
формулой `app.ids`), §1.1 (ownership), §6 (defaults read-only).

**Файлы.** `backend/app/application/worldData/libraryPacks/packService.py`.

**Контракт.** На `_PackScope`:

- `new_pack_identity(system_name) -> tuple[str, str]` — strip →
  required → `library_uid` → `is_default_pack_uid` → ReadOnly →
  `get_by_uid`/`get_by_system_name` → Conflict; возвращает
  `(normalized system_name, pack_uid)`.
- `insert_pack_row(row)` — `packs.insert` + `IntegrityError` →
  `LibraryPackConflictError`.

`_PackOps.create` и `_RemapOps._copy` идут через них; тексты ошибок и
семантика гейтов не меняются (`_copy` остаётся внутри общей транзакции —
`insert_pack_row` сам транзакцию не открывает).

**Проверка.** `cd backend && python -m unittest tests.test_library_packs_4a tests.test_library_packs_4b tests.test_library_packs_b3 tests.test_library_packs_schema` — зелёные; существующие conflict/default-gate тесты проходят без правок.

**Done.** Дублирующего блока нет; гейт живёт в одном месте.

## Шаг 2 — typed ref-remap: wire-ключи из POJO

**Цель.** Remap-сканы читают/пишут поля через модели; raw dict — только
контейнер, в который кладётся dump overlay (unknown keys сохраняются).

**ТЗ.** `tz_template_library_packs.md` §2 (declared ref-поля — контракт
адаптера); rule `dataModel-no-hardcode`.

**Файлы.** `backend/app/application/worldData/libraryPacks/domainAdapters.py`
(при необходимости — export дискриминатора из
`buildingTemplateLibraryService.py`, без новой логики там).

**Контракт.**

- `_remap_structure_refs`: строка без `system_template_uid` и с
  plot-ключами → `resolve_model(PlotLayoutTemplate, row)`; remap —
  `main_building.model_copy(update={"structure": …})` /
  `secondary_buildings[i].model_copy(...)` через `StructureKey`;
  результат — `{**raw_row, **remapped.model_dump(mode="json")}`.
  Строка, выглядящая как layout, но не проходящая валидацию — fail
  loud (`LibraryPackValidationError` с контекстом), не silent pass.
  Pointer-строки и посторонние dict — как раньше, `None`/untouched.
- `_remap_relief_pick_policy`: per-entry
  `ReliefContextPickPolicy.model_validate` → `model_copy(update=
  {"default_template_uid": mapped})` → overlay поверх сырого entry;
  итерация `WorldReliefPickPolicy.model_fields` сохраняется.
- `"system_template_uid"` → единая модульная константа
  `_POINTER_UID_FIELD` (docstring: поле `ReliefTemplateRegistryEntry` /
  `BuildingTemplateRegistryEntry`); заменяет три литерала.
- `StructurePackAdapter.remap_body`: `system_name` — поле
  `StructureTemplate` — константа/доступ из модели вместо литерала.
- D3 закрывается этим же шагом: после typed-резолва асимметрии нет;
  в docstring — одна строка, почему dump overlay (unknown keys), а не
  чистый dump.

**Проверка.** Те же unittest-файлы; особенно
`test_instantiate_structure_pack_remaps_embedded_layout_refs`,
`test_internal_refs_remapped_external_untouched`,
`test_instantiate_remaps_pick_policy_and_pointer` — без правок тестов.

**Done.** Ни одного литерального wire-ключа там, где есть модель;
unknown keys в строках/политике сохраняются; тесты зелёные.

## Шаг 3 — adapter/ops cleanup

**Цель.** Убрать мелкие дубли и layering-smell из remap-пути.

**ТЗ.** `tz_template_library_packs.md` §2; rule `layer-boundaries`
(application-слой не бросает HTTPException).

**Файлы.** `domainAdapters.py`, `packService.py`.

**Контракт.**

- `_RegistryPointerMixin._rebuild_registry_field(world, uid_map,
  members)` — `setattr` без `update`; `ReliefPackAdapter.
  remap_world_refs` = rebuild + pick-policy + один `_world_repo.update`.
- Refetch мира в `_RemapOps._copy` — `scope.worlds.find_by_id` (мир
  уже проверен гейтом; `None` → `LibraryPackValidationError` или
  assert по вкусу — зафиксировать при реализации).
- Одно чтение тела: адаптер `read_body_row(template_uid) ->
  tuple[dict, str | None] | None` (data + source_file) для remap-пути;
  `read_body`/`body_source_file` остаются для CRUD-пути или сводятся к
  нему — решение фиксируется в шаге, не размазывать оба вызова.
- `RemappedMember.outline` → union `ReliefTemplate | StructureTemplate
  | BuildingTemplateOutline | PlotLayoutTemplate`.

**Проверка.** Те же unittest-файлы + `python -m compileall app`.

**Done.** Дубля rebuild+update нет; HTTPException не протекает в remap;
на член — одно чтение библиотеки.

## Не шаги

- D8 (тест 290 строк) — waived.
- D9 (`worlds.update` × embedded plot-строки) — отдельный scope
  `jsonValidation`, отдельный план. Записан здесь как долг, чтобы не
  потерять связь: именно он заставил remap идти repo-write.
