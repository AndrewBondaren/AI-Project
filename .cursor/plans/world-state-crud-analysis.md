# World State CRUD — анализ планов WS

Статус: ANALYSIS (2026-10-26). Ревью двух связанных планов против кода и
правил; код не изменялся, решения за мастером. Это находки для freeze WS-0
и приёмки WS-0A, не план реализации.

Объекты анализа:

- `world-state-crud-transition.md` — владелец/границы, карта классов,
  переход existing классов, шаги WS-0…WS-5, связь с PC-11.
- `world-state-crud-capabilities-uow.md` — WS-0A: capabilities,
  query/mutation фасады, UOW, selective patch; §7–12 нормативны поверх §2–6.

## 1. Проверка ссылок на existing код — подтверждено

| Утверждение плана | Факт в коде |
|---|---|
| `WorldService.{get_by_id, create, update, delete, edit_region, _write_scope}` | `application/worldData/registries/worldService.py` — все методы есть; `_write_scope` → `transaction_if_needed` |
| `NamedLocationService.{get_by_id, get_all, create, update, delete}` | `application/worldData/locations/namedLocationService.py` — есть |
| `PatchStoreService.upsert_patch` → generic upsert | Подтверждено: `patchStoreService.py` → `BaseRepository.upsert` = `INSERT OR REPLACE` (`db/repositories/sqlite/base.py:38–44`); риск потери незатронутых полей реален |
| `upsert_terrain_skeleton` при conflict обновляет только `system_terrain` | Подтверждено: `mapCellRepository.py:130–135` |
| `Database.{transaction, transaction_if_needed, transaction_on}`, BEGIN IMMEDIATE | `db/database.py:120–155` — есть |
| «Existing BaseRepository commit guard» | Есть: `if not _in_transaction.get(): conn.commit()` во всех write-методах `base.py` |
| Session task-bound / отказ join чужой UOW | Опора есть: `GuardedConnection.owns_unit_of_work` (owner=task + explicit); `transaction_if_needed` уже бросает `RuntimeError` при чужой UOW |
| PK patch row = `(world_uid, x, y, z)` | `0001_initial.sql:794` — composite PK |
| Layer-kind не определяет field presence | Подтверждено: `patchCellContribution.map_cell_to_patch_contribution` читает field-wise, игнорируя `layer_kind` (WP-FIX-DEBT-1) |
| Single-writer region_states | `IRegionStateRepository` docstring: sole writer = `StateChangeConsumer` |
| `MapCellQueryFacade.{get_cell, get_cells, get_scene_volume}`, `WorldPackReader.{chunk_exists, read_wilderness_chunk}`, `WildernessRegionReadService.outline` (sync, absent→None), `EntryRefineOrchestrator.refine_from_entry`, `SurfacePlanningCapture.capture` (sync), `RegionEvaluation`, `FineGridCoord`, `MapCellHydrology`, `CellContribution`, `merge_layers` | Все существуют по указанным путям |
| Folder counts: mapCells 6, pack/read 22, regions 8, container 9, db/repositories 28 | Проверены по директориям — все точные |
| Tests leaf `backend/tests/worldState/` | Оправдан: `backend/tests/` — плоская папка ~280 файлов; добавление root-файла нарушило бы composition |
| `*(PC-11 target)` классы (`SurfacePlanningEntry`, `*WorkingFields`) | Отсутствуют — корректно помечены как целевые |
| Порядок «WS-0/0A freeze → PC-11 с согласованными inputs» | PC-11 в `geo-1-designed-water.md` открыт (DONE снята, PC-11.1…8 не закрыты) — конфликта с влитым кодом нет |

## 2. Пробелы и риски для freeze WS-0

### 2.1 `is_structural` и прочие колонки вне whitelist (§10)

`CellContribution` содержит `is_structural` (merged view его использует),
но whitelist §10 — нет. Таблица `map_cell_patches` дополнительно имеет
колонки вне `CellContribution`: `system_danger_level_override`,
`gap_width_override`, `railing_sides`, `system_facing`, `display_facing`,
`glass_material`, `system_grade_uid`. Column-wise update сохранит их
автоматически, но граница «что в scope первого контракта» должна быть
зафиксирована явно: либо `is_structural` добавляется в whitelist, либо
записывается осознанное исключение. Иначе решение «придумается при
реализации» — то, что WS-0 запрещает.

### 2.2 NOT NULL колонки при CREATE_ONLY insert

`layer_kind` (NOT NULL DEFAULT 'structure') и `is_structural`
(NOT NULL DEFAULT 0) обязаны быть заполнены при вставке новой patch row.
План фиксирует, что layer-kind stamp не влияет на read, но не говорит,
что писать при insert. Должно быть в freeze, не в коде.

### 2.3 Предикат «пустая patch row» не задан

`CellContribution.has_data()` не учитывает `is_structural` и
`travel_modifier_override`. Строка только с `travel_modifier_override`
пуста на read, но физически содержит override. Если удалять после reset
по `has_data()` — теряется живое поле; если не удалять — мусорная строка.
§10 говорит «не считать пустой по новому whitelist», но точный предикат
(по какому набору полей) не задан — обязателен в freeze.

### 2.4 Формулировка dispatch расходится с DI-графом

§7: facade «вызывает ровно одного typed handler». §8.1: handler —
зависимость adapter (`facade → WorldCellAdapter → CellPatchMutationHandler
→ CellPatchStorageAdapter`; аналогично metadata). Модель ациклическая и
рабочая, но фразу стоит привести к единой: facade делает capability
check + UOW, dispatch handler — внутри adapter. Также port-протокол
handler'ов (сигнатура `apply`, тип session) отсутствует в карте классов —
помечен «freeze перед реализацией», это обязательный пункт WS-0.

### 2.5 `WorldCellAdapter.read` требует `World` object

`MapCellQueryFacade.get_cell/get_cells/get_scene_volume` принимают
`World`, а query несёт `world_uid`. Шаг `world_uid → World`
(`WorldService.get_by_id` / `IWorldRepository`) нигде в карте методов не
указан — добавить в freeze, иначе это «недостающий вызов», придуманный
при коде.

### 2.6 Ambient transaction без session — поведение не определено

Existing join работает через ContextVar `_in_transaction`. Если mutation
facade вызван внутри уже открытой ambient-транзакции без `session`,
`Database.transaction` → `BEGIN IMMEDIATE` внутри открытой транзакции →
sqlite-ошибка «cannot start a transaction within a transaction», а не
typed refusal. План требует «ambient без token не подхватывается молча» —
нужно явно заморозить: refusal до BEGIN, а не падение от sqlite.

### 2.7 Дрейф формулировок между документами

Transition §3: «WorldStateService не вводит новую transaction вокруг
произвольных domains» — фактически заменено WS-0A (facade владеет root
UOW на одну команду). По смыслу совместимо (одна typed команда ≠
cross-domain batch), но строчка читается как противоречие —
синхронизировать при приёмке.

### 2.8 Два writer'а `map_cell_patches` сохранятся

Bake-путь (`MapCellService.save_pass`, `upsert_*`,
`bootstrapMapCellWriter`) и новый `CellPatchMutationHandler`. Single-writer
для patch не заявлен (в отличие от region_states). Write-write конфликт
«bake tile vs gameplay patch той же клетки» не рассмотрен; хедж «stable
pack view не входит в supported commands» покрывает read-consistency, не
этот случай. Нужна позиция: осознанный допуск или отдельный контракт.

### 2.9 Sync API в async read path

`WorldPackReader.*`, `WildernessRegionReadService.outline`,
`SurfacePlanningCapture.capture` — sync. Adapter обёртывает; для
тяжёлого `outline` это existing behavior, но read-port контракт должен
явно разрешать sync-blocking делегирование (или зафиксировать executor).

## 3. Сильные стороны

- **Grounded**: все ссылки на existing код реальны; заявленные gaps
  (`upsert_terrain_skeleton`, `INSERT OR REPLACE` в `PatchStoreService`)
  подтверждаются дословно.
- **Layer-boundaries соблюдены**: адаптеры thin, доменные handler'ы в
  своих доменах (`mapCells/mutations`, `registries/mutations`,
  `locations/mutations`, `regions/stateChange/mutations`), DI-граф
  ациклический, запрет consumer→facade→adapter→facade цикла явный.
- **Честная атомарность**: нет псевдоатомарности SQL+pack; savepoint
  сознательно исключён; snapshot — только TODO с запретом фиктивного
  backend и фразой про §7 transition-плана.
- **Composition**: counts точные; переполненные папки (`pack/read` 22,
  `db/repositories` 28) не растут; handlers вынесены в отдельные leaf
  `mutations/`; тесты — отдельный leaf, не root-файл в плоской папке.
- **Typed ошибки**: `Applied/Refused` + reasons вместо разбора
  `exception.message`; storage errors не маскируются в `Missing` —
  соответствует layer-boundaries.mdc («severity — решение producer'а»).
- **Capabilities-модель**: read-only backend не обязан иметь writer;
  три различённых исхода (нет capability / unsupported / refused) —
  корректнее обязательного full-CRUD.

## 4. Вопросы к мастеру (позиции, не блокеры кода)

1. `is_structural` — в whitelist или явное out-of-scope первого контракта?
2. Точный предикат пустой patch row после reset — по какому набору полей?
3. Facade внутри ambient-транзакции без session — typed refusal до BEGIN?
4. Кто резолвит `world_uid → World` для `WorldCellAdapter.read` —
   `WorldService.get_by_id` или `IWorldRepository` напрямую?
5. Bake-writer vs CRUD patch на одной клетке — осознанный допуск с
   документированным «last commit wins» или отдельный контракт
   сериализации?

## 5. Вердикт

План качественный, grounded и реализуемый; архитектурная схема
(capabilities → facades → adapters → handlers → existing backends)
согласована с правилами слоёв и реальной инфраструктурой
(`Database.transaction*`, `GuardedConnection`, commit guard).
WS-0A не готов к приёмке до закрытия находок §2.1–§2.6 — все они
относятся к обязательному freeze WS-0, не к имплементации. §2.7 —
документная синхронизация. §2.8–§2.9 — вопросы позиции.
