# АРХИВ WS — прежний план и промежуточная архитектура

Статус: ARCHIVED / SUPERSEDED, 2026-10-27. **Не действующий план реализации.**
Актуальный новый план — [доменное чтение, patches и snapshots](world-domain-patches-snapshots.md).
Содержимое ниже сохранено для истории; дальнейшие изменения архитектуры
и implementation steps фиксируются в новом плане. Старая схема центрального
CRUD, её class map и WS-1…WS-5 отменены.

<details>
<summary>Архив промежуточной архитектуры</summary>

Статус: ARCHITECTURE IN PROGRESS, 2026-10-27. Ни один implementation шаг
не разрешён этим документом. Сначала архитектура и её приёмка, затем
конкретные контракты/реализации. Ни один шаг не объявлен DONE.

## 1. Зафиксированное решение мастера

**DAG вызывает read и patch непосредственно у реализации соответствующего
домена. Контракт чтения принадлежит домену. WS не задаёт read-контракты,
не оборачивает их и не маршрутизирует вызовы. WS напрямую не обращается к БД.**

```text
DAG → domain.read(query) → domain result
DAG → domain.patch(change) → сохранение metadata/planning data или materialization
Snapshot ← patch-операции всех доменов и соответствующие данные состояния
```

`domain.read` и `domain.patch` обозначают архитектурные операции, не выбранные
имена классов/сигнатуры Python. Конкретные реализации определяются после
приёмки архитектуры. Существование DB row не определяет публичный контракт.

## 2. Ответственности

| Владелец | Обязанность |
|---|---|
| DAG | Определяет когда выполнить операцию; напрямую вызывает публичный domain API; собирает PatchSet из доменных patches |
| Debug API | Инструмент разработчика, вызывает тот же domain API и может собирать PatchSet; не заменяет production DAG |
| Домен | Владеет контрактами read/patch, typed данными, правилами изменения и сохранением своих metadata/planning/materialization |
| Domain read implementation | Возвращает данные и определяет missing/fallback/merged/raw семантику своего домена; использует собственную инфраструктуру хранения |
| Domain patch implementation | Формирует доменный patch и применяет/сохраняет изменение по доменному контракту; общего набора patches не собирает |
| Generator/materializer | Получает подготовленные inputs/план и возвращает доменный результат; без SQL, WS, patches и snapshot IO |
| Общий patcher | При необходимости применения набора делегирует доменным patch implementations; не создаёт промежуточный WS CRUD |
| Snapshot | Сохраняет общую историю patch-операций всех доменов и связанные данные состояния; не выполняет доменные алгоритмы |
| Domain storage infrastructure | Физическое хранение, mapping и DB/file IO за публичным domain API |

## 3. Что исключено из архитектуры

- Единый WorldStateService/WorldStateQueryFacade как путь доменного чтения.
- IWorldStateRead/IWorldStateCrud как общий read-контракт, навязываемый доменам.
- Обязательный маршрут domain read/patch через WS либо его adapters.
- Доступ WS к Database, connection, repositories, SQL и DB row mapping,
  включая adapters/UOW, спрятанные внутри worldState.
- DB-bound metadata context и перенос WorkingFields в общий WS payload.
- Генераторные IO/patch writes, сбор PatchSet вне DAG/debug API.

Предыдущая схема общего CRUD и её class/file map отменены, не используются
как основа реализации. Её материалы сохранены как архив инвентаризации:
[capabilities/UOW](world-state-crud-capabilities-uow.md),
[WS-0 ledger](world-state-crud-ws0-freeze.md).

## 4. Материализация и история

Metadata/planning data и результат materialization сохраняются через patches
соответствующего домена. Изменение планировки и её зависимостей определяет
домен. Materialization выполняется явным запросом из актуального плана;
read и snapshot save не запускают её автоматически.

Snapshot сохраняет операции patches всех доменов в общей истории. Журнал
операций не подменяет данные состояния snapshot: существующий норматив
immutable snapshots/authoritative state сохраняется. Точный commit protocol
операции и snapshot ещё требует архитектурной проработки, не угадывается.

## 5. Оставшиеся архитектурные вопросы

До implementation необходимо определить:

1. Domain API boundaries для read, подготовки patch и его применения;
   domain-owned типы/результаты, включая отсутствие данных и ошибки.
2. Lifecycle patch: подготовка → сбор DAG/debug → применение → передача
   операций/данных в snapshot. Кто координирует эти вызовы и их отказы.
3. Границы атомарности одной domain mutation, PatchSet/хода и сохранения
   snapshot; поведение при частичном отказе, SQL/file publication.
4. Source/planning revision, dependencies и invalidation materialization:
   domain ownership без второго revision store и без hidden generate.
5. Переход existing direct CRUD/import callers к разрешённым entry points
   без переименования production routes в debug и без обхода Gate: DAG.

Не вводить concrete WS service/storage adapters для закрытия этих вопросов.

## 6. Порядок дальнейшей работы

Архитектура и ответы §5 → приёмка мастером → exact domain contracts,
class/method/file map и проверки → согласованный implementation план → код.

Старые WS-1…WS-5 с central CRUD больше не являются действующей
последовательностью реализации. Их новая карта определяется после
архитектуры; механически переименовывать прежние классы запрещено.

Норматив: docs/tz_patch_system.md, docs/tz_world_snapshot.md,
docs/tz_world_generation_dag.md и .cursor/rules/dag-generator-interface.mdc.
DAG wiring/engine nodes остаются за существующим G1–G5 gate.

## 7. Связь с PC-11 и будущими snapshots

Read-owner остаётся у домена/его application operation. Общий WS read-owner
не создаётся. Сохраняются operation-wide region state read и передача
готовых inputs всем tiles/drains, WP-20 merge/fallback и outline early return.

Старый TODO(snapshot) про shared CRUD — задел будущего snapshot lifecycle,
не требование внедрять WorldStateService в domain read. Его формулировка и
caller mapping подлежат отдельной синхронизации после архитектуры; runtime
код этим документальным изменением не меняется. Snapshot existence lookup,
selector/freshness/restore implementation не добавляются автоматически.

</details>
