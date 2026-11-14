# Source: revision storage и initial bootstrap

2026-11-14. **DESIGN OPEN, код не разрешён.** Шаг 2 основного world-source-versioning.md. Основания: pregame design P2.7/P2.11/P2.17/P3.1, Terrain dossier §7. Только Source-owned storage и требования к owning writer. Новые междоменные API/DAG — шаг 3. Cell-state разработка вне scope; legacy adaptation запрещена.

## 1. Evidence и границы

`db/migrations/0001_initial.sql` содержит worlds.terrain_registry, но в проверенном schema нет source_revision/source_collection/source_mutation таблиц. `application/worldData/registries/worldService.py::_save` вызывает repository method и region reconciliation. `db/repositories/sqlite/worldRepository.py::update` вызывает BaseRepository.save; save обновляет существующую строку и при условиях своего adapter делает commit. Это не Source append-only writer и не доказательство участия в общей publication transaction. Не использовать этот путь как готовую реализацию нового storage.

Основной план требует append-only и оставляет применение sets за Snapshot. Source хранит версии/историю/retention, но не получает права самостоятельно менять applied World state. Latest Source revision и применённое состояние мира нельзя отождествить без owning решения. Internal Source index ниже не заменяет Terrain writer или Snapshot apply.

## 2. Логические записи Source

Ниже storage schema proposal, не новые публичные POJO и не DDL. Identity/ref values переиспользуют SOURCE_PROOF_SCHEMA_V1, без параллельной UID/hash системы.

| Запись | Поля и ключ | Инварианты |
|---|---|---|
| Object revision | exact object identity, seq, semantic_hash, deleted, created_attempt_id | Unique(identity, seq); seq положительный, монотонный. Append-only. deleted=true не имеет live body |
| Collection revision | exact collection identity, seq, semantic_hash, created_attempt_id | Unique(identity, seq); body содержит полный упорядоченный membership. Удаление collection не входит в первый срез |
| Body mapping | exact object/collection revision → original ArtifactRef | Одно immutable отображение; semantic hash не приравнивается physical artifact hash. Mapping tombstone запрещён |
| Mutation linkage | operation_id + exact source ref | P2.7: полный touched set, включая no-op. Никакой копии terminal/request/fingerprint; ledger остаётся у publication |
| Prune fact | exact source ref + факт санкционированного прекращения retention | Не меняет identity/seq/hash/deleted/creation provenance и original mapping metadata. Физическая схема и explicit prune поставка здесь не утверждаются |

SourceRootHolder/holds находятся в Artifacts, не дублируются в Source SQL. created_attempt_id берётся из проверенного domain scope по P2.11, не из caller uid. Bootstrap не получает фиктивную attempt, особый bypass или отдельный receipt.

## 3. Чтение и запись index

Предлагаемая внутренняя роль `SourceRevisionIndexStore` (Source-owned storage; конкретные module/adapter signatures фиксируются при приёмке среза): читает exact revision/mapping/status и добавляет новые immutable записи. Зависит только от общего scoped storage и Source value bindings; не кодирует Terrain, не назначает semantic hash, не вызывает public CRUD/DAG/commit, не приобретает holds. Критерий отказа: исправление существующей mapping, latest fallback для exact read, самостоятельный commit или копирование publication terminal.

Отдельного mutable latest pointer не вводится. Предложение для Source accounting: текущая записанная revision identity выводится из подтверждённых append-only revisions; физический query/visibility согласуется со storage transaction. Такая revision не объявляется автоматически applied world state. Приёмка должна доказать, что candidate/rollback rows не становятся видимым committed head и что applied-state selector не подменён этим query.

Назначение seq принадлежит existing proposed SourceRegistryMutationApplier, index обеспечивает uniqueness/invariants. В общей serialized domain transaction сначала проверяются expected revisions и полный post-batch membership, затем назначаются revisions и append. No-op возвращает прежнюю exact revision/body mapping и требует прежние roots. A→B→A создаёт новый seq, а не возвращает старую semantic identity. Tombstone и REVISION_PRUNED не равны missing/corrupt bytes. Same terminal replay не выполняет append и не назначает seq.

Обязательная атомарность: owning authored write, object revisions, collection revision, full mutation links, root acquisition и publication terminal должны иметь согласованный rollback/commit outcome по принятому lifecycle. Index не может обещать это отдельно от owning writer. Прерывание после любого append не оставляет частично принятого mutation. Unknown outcome не означает разрешение повторить writer напрямую.

## 4. Initial bootstrap: только authored нового контракта

1. Получить полный явно подготовленный authored registry нового strict roster и зафиксированного execution/encoding version. Не вызывать normalize_world, canonical overlay, repairWorldDefaults или inferred hills_authored. Defaults/landcover — отдельные dependencies.
2. Проверить shape, world/descriptor, unique member identities, exact order и полноту membership. Проверки ссылок следуют принятому итоговому графу, не import skips. Нет полного целевого input — отказ.
3. До начальной записи проверить отсутствие прежнего Source accounting для данной collection и её member identities, включая tombstones. Нельзя считать частичную историю пустой или чинить её bootstrap. Наличие old World JSON не делает его автоматически допустимым input.
4. Подготовить exact immutable body/collection refs; использовать обычный согласованный staging/attempt lifecycle. Bootstrap не обход lifecycle и не новая операция под чужим OperationKind. Публичный вход определяет шаг 3.
5. В общей domain transaction повторить проверки отсутствия history/expected и согласованности input, записать первые object/collection revisions с seq=1 и настоящей creation attempt, full touched linkage и удержание bodies. Owning writer должен записать то же authored состояние без отдельного commit. Snapshot/application граница требует подтверждения владельца, см. §5.
6. Успех только после общего confirmed commit. Restart той же операции — terminal replay. Новый bootstrap поверх существующей истории отвергается; не заменяет данные и не достраивает missing members. Cancel/unknown идут через существующий recovery protocol, без нового bootstrap retry loop.

## 5. Единственная внешняя развилка этого шага

### Адресная сверка Snapshot на 2026-11-14

Получен [ответ владельца Snapshot](snapshot-source-authored-binding-status-2026-11-14.md). Общий runtime Snapshot freeze принят, scoped core реализован частично. Но его runtime entry требует gameplay_started/pack и не является готовым pregame authored mutation entry. В проверенном контракте/коде отсутствует принятый конкретный binding authored Terrain/Source set writer. WorldPublicationRef — applied publication identity, а не Source latest revision; max Source seq не определяет применённое состояние мира.

Source вправе опираться на общие immutable-ref/capability/atomicity требования. Нельзя считать §4 bootstrap исполнимым или обещать атомарность с applied World state до конкретного binding. Existing Source mutation/recovery proposals этот пробел не закрывают. Статус **сверен на дату ответа, не freeze зависимости**: перед общей приёмкой перечитать актуальный Snapshot ТЗ, 4D2/terminal-retry статусы, public integration proposals и signatures context/handler/transaction. Новые API здесь не проектируются. Продолжение writer/bootstrap части за этой границей требует отдельного определения scope пользователем.

Ответ Terrain получен и записан в §5c owning dossier: в проверенном маршруте append-only scoped durable writer не найден. Конкретное препятствие — утверждённая связь Snapshot apply/set с borrowed domain transaction и представление append-only transition/head/commit. Основной план от 2026-10-27 не разрешает назначить apply owner самостоятельно. **Дальнейшая конкретизация owning writer/bootstrap остановлена на этой внешней границе** по указанию пользователя. Source не меняет WorldService, не проектирует Snapshot apply и не строит параллельный world mutation механизм. Сначала требуется предъявить существующее принятое решение Snapshot либо отдельно разрешить проработку именно этой зависимости; до этого writer не считается готовым.

Пока это не доказано, §2–4 — конкретный storage proposal, не accepted implementation. Не выполнять SQL/POJO/runtime edits. Byte limits, physical rows/guards, конкретные classes/files и rollback/bootstrap tests должны войти в принятый implementation-план; их отсутствие не маскируется заявлением о готовом index.
