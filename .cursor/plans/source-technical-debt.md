# Source — интеграционный техдолг

2026-11-15. Единый реестр статусов интеграционного техдолга Source. Основной план — [world-source-versioning.md](world-source-versioning.md). Записи не разрешают разработку чужих доменов, не блокируют архитектуру независимого ядра и не заменяют самостоятельные незавершённые Source-контракты.

Все записи ниже **OPEN / отложенная интеграция**. Закрытие требует актуального evidence владельца и отдельной приёмки соответствующего среза. Не заменять неизвестные контракты заглушками, зеркалами, legacy adaptation или вторым инфраструктурным механизмом.

| ID | Владелец и конкретная зависимость | Затронутый Source-срез | Условие возврата / закрытия |
|---|---|---|---|
| INT-TERRAIN | Terrain: body codec/projector/format остаются proposal; shared POJO compatibility и vectors не приняты | Concrete descriptor binding | Принятый owning контракт с exact imports, версиями и проверками. Source не определяет судьбу полей других доменов |
| INT-ARTIFACTS-FORMAT | Artifacts/publication + owning body domain: exact format/version, contract instance, registry/backend и borrowed scope composition | Durable read/finalize/adoption | Подтверждённая конкретная регистрация и scope binding; проверенные decode/integrity границы. Без нового lifecycle/backend |
| INT-ARTIFACTS-RETENTION | Source: политика истории/prune; Artifacts: holders/GC. Binding исторических revision bodies к Source root и освобождение root при explicit prune | Retention/prune | Принятые root ownership и атомарные acquire/release; проверка сохранения bytes при других holders. Format registration не закрывает retention |
| INT-ARTIFACTS-TERMINAL | Artifacts/publication: Source outcomes отсутствуют в текущем OperationRecord.terminal; Source владеет кандидатами outcomes | Mutation committed result и recovery replay | Сначала принять Source outcome/error delta; затем владелец подтверждает terminal registration/codec/receipt-read. Проверки reopen, fingerprint binding и replay, отсутствие второго ledger |
| INT-WRITER | Owning домен данных + Snapshot + Source: нет подтверждённого Snapshot authored-write/borrowed transaction binding, связывающего writer/bootstrap с Source revision append | Атомарное применение mutation | Exact Input/Result/Error, один commit owner, scoped write, rollback/unknown outcome и atomicity checks. Миграция чужого writer не входит в Source scope |
| INT-PACK | Pack: mapping declared usage/сохранённой provenance к proof/groups/selection/durable refs | Consumer binding Pack | Подтверждённое соответствие PackStoredProvenance Source-контракту и принятый интеграционный срез; существующие POJO не отменяются |
| INT-SNAPSHOT | Snapshot: proof request encoding, pinned origin/adoption input, target scope/fence | Consumer/retention binding Snapshot | Приёмка актуальных encoding/binding и передачи proof/holder evidence. Не дублирует authored-write INT-WRITER |
| INT-DAG | Владелец DAG: прямой вызов публичных Source операций, typed I/O/errors, передача результатов | DAG wiring | Совместно принятые пользователем конкретные ноды/маршруты; Source не назначает их и не вводит обходной orchestrator |

## Evidence INT-ARTIFACTS-TERMINAL

### INT-SOURCE-READ-LIFETIME — public proof read scope (OPEN)

2026-11-17: запрос отправлен в существующий видимый чат **SNAPSHOT** (`01a1a0c5-931c-77a0-96a5-cb5b6ca6766f`). Обязательный первый шаг владельца — аудит existing POJO/errors/scopes/methods без дублей, затем подтверждение актуального контракта. Попросили отделить Snapshot/publication ownership от неподтверждённой Artifacts части и не создавать исключение DAG. Статус: ответ ожидается; более ранняя запись «отправка не заявляется» ниже описывает состояние до этой отправки.

Владельцы подтверждения: Snapshot/publication (CommitReadScope и lifetime) и Artifacts (SqliteArtifactScope binding); Source владеет требованиями своей public boundary. Проверено 2026-11-16: existing `SqliteArtifactScope.read_scope()` открывает/закрывает scope и bind/reset либо заимствует existing binding; `SqlitePublicationCommitStore.read_scope(existing_scope=None)` предоставляет concrete lifecycle. Новая инфраструктура Source не требуется на основании одного отсутствующего constructor binding в плане.

Точный запрос: подтвердить применение этого existing read lifetime к пяти scope-free public Source proof operations; допускается ли inherited binding на этой границе или нужен owning публичный способ отказа до IO; кто гарантирует same registry/task, cleanup при failure/cancellation и допустимость композиции по INT-DAG-SCOPED. Source не вызывает private `_require_unbound`, не добавляет свой commit owner и не принимает решение за владельцев. Условие возврата: актуальные exact imports/methods и согласованный call trace с обеими lifetime ветвями либо явным запретом borrowed ветви. До ответа durable constructor signatures остаются OPEN. Запрос зафиксирован, отправка и ответ не заявляются. Pure request validation и собственный provenance design этим не блокируются.

### INT-DAG-SCOPED — нормативная граница atomic composition (OPEN)

Владельцы: пользователь/владелец правил DAG и Snapshot; Source предоставляет точный контракт своих calls. Зависимость: §5 source-pack-s1-s2-contract.md содержит Snapshot→Source check_coverage/collect_for_adoption/adopt при абсолютном запрете прямых междоменных calls. Акт проверял только public calls, чего недостаточно. Затронутый срез — S1/S2 scoped integration; независимые Source invariants не блокируются. Условие закрытия: явное решение по допустимости, согласованный ограниченный перечень calls/effects/transaction ownership и синхронизация normative rules/design/акта. Если composition запрещена — совместимый маршрут предъявляют владельцы, без самостоятельного изменения Source порядка/транзакции. Запрос подготовлен в §5; отправка владельцам и ответ не заявляются.

### Дополнение INT-WRITER / INT-DAG — authoritative phase boundary (OPEN)

Snapshot/Artifacts-publication должны подтвердить exact reader/guard фазы мира и атомарность с переходом gameplay, typed refusal и включение Source changes в Snapshot-owned apply. Source-owned pregame apply/recover ограничения перечислены в source-core-mutation-contract.md §8.1. Условие возврата: согласованы phase authority/serialization/refusal и сценарии concurrent gameplay start, terminal replay после старта и запрет нового pregame attempt после старта. Source не создаёт второй commit owner; неизвестный phase отказ не подменяется proof error. Это детализация существующих долгов, не задание реализовать внешнюю инфраструктуру.

### Дополнение INT-ARTIFACTS-RETENTION: usage/prune boundary

Основной план §GC ревизий относит reachability к sourceUsage, выполнение explicit prune — к revisionPrune. Exact accepted typed binding этих участников с Source root/Artifact holders не предъявлен. Владельца конкретного usage/prune implementation уточнить при возврате к интеграции, не назначать им Source по умолчанию. Условие возврата: typed preview/confirm контракт, authoritative repeat check под согласованным scope, latest protection и отсутствие окна с concurrent capture/holds. Pure Source models не импортируют holders; bool free в caller input не заменяет evidence. Подробный разбор — [границы ядра](source-core-capture-prune-configuration.md#2-prune-не-присваивать-source-чужой-reachability).

### Evidence terminal registration

Проверено чтением кода 2026-11-15: [OperationRecord](../../backend/app/dataModel/artifacts/lifecycle/operation/record.py) допускает в terminal SnapshotApplyResult, PackActivationResult, GameplayStarted, OperationCancelled либо None. SourceMutationApplied/SourceMutationRefused не зарегистрированы. Сами Source outcomes пока proposals; отсутствие регистрации не основание самостоятельно менять shared union.

Точный Source design — [mutation contract §8.1–8.2](source-core-mutation-contract.md). Пока интеграция открыта, нельзя объявлять Source mutation/recovery runtime готовыми или сохранять outcomes через обходной ledger. Pure revision и архитектура ядра продолжаются независимо.

## Границы записей

### Lifecycle — условие уточнения, не активная интеграционная зависимость

2026-11-17. Основание: [entity-lifecycle.md](entity-lifecycle.md) и [ТЗ Lifecycle](../../docs/tz_entity_lifecycle.md). В рассмотренных документах прямой согласованный контракт Source ↔ Lifecycle и потребность включать lifecycle-записи в Source proof не установлены. Эта запись не входит в перечень OPEN bindings выше, не блокирует ядро Source и не добавляет шаг реализации.

Граница: Lifecycle владеет актуальностью сущности, predecessor links и историей замещения; Source — ревизиями исходных данных и proof их зависимостей. Изменение revision при сохранении UID не означает замещение сущности. Source не вводит собственные lifecycle status/predecessor/end POJO. Lifecycle не владеет transaction lifetime, leases/holds/GC и не является адресатом вопроса public read borrowed scope.

Обращение требуется, если конкретный consumer заявит lifecycle-данные как dependency Source либо Source-проект затронет семантику актуальности/замещения/завершения сущности. До этого запрос владельцу не нужен. При появлении основания сначала записать конкретный consumer, данные и сценарий; затем запросить у Lifecycle:

1. Сначала аудит existing и proposed POJO/errors/методов с exact imports и статусом принятия; переиспользование без зеркальных DTO. Проекты EntityLifecycle/LifecycleCapture не считать уже поставленными контрактами.
2. Какой публичный read/result предоставляет нужные записи и evidence exact publication/revision, полноты и исторического чтения; что означает отсутствие записи. Не требовать нового API, если существующий закрывает сценарий.
3. Различие изменения той же сущности, замещения новым UID и завершения; какие из этих фактов должен учитывать конкретный Source consumer. Не переносить проверку lifecycle-переходов в Source.
4. Только при необходимости Source proof — owning identity/body/format contract и соответствие существующим Source refs; полный durable closure и границы retention согласовать с фактическими владельцами. Запрет удаления lifecycle history не приравнивать автоматически к политике хранения всех Source revisions.
5. Путь передачи через DAG, отдельно от Snapshot/Pack publication binding; никаких прямых вызовов или чтения чужих внутренних таблиц. Недостающие решения Snapshot/Artifacts/DAG адресовать их владельцам, не Lifecycle.

Условие возврата: конкретная потребность подтверждена и владелец предъявил актуальный контракт/точный gap. Только тогда создаётся адресная запись интеграционного техдолга с затронутым Source шагом. Автоматическое расширение текущего плана Source на реализацию Lifecycle запрещено. Запрос не отправлялся.

glossary_ref и morph_hydrology_role выведены пользователем из scope текущего Source-плана: не превращать их в новые задания Source или условия приёмки независимого ядра. Вопрос Hydrology уже записан в GEO. Все поля и алгоритмы других доменов остаются у их владельцев.

Точные public mutation/recovery signatures, Source error roster delta и pure checker contracts — собственная архитектурная работа Source, не внешний техдолг. Их неполнота должна быть показана в архитектурных документах, а не скрыта этим реестром.
