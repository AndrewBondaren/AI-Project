# Source — интеграционный техдолг

Актуальная сводка для обязательного координатора: [пакет Source от 2026-11-19](source-interdomain-coordination-2026-11-19.md). Он разделяет принятые направления, existing типы, proposals и OPEN; не закрывает интеграции. Локальные ответы владельцев не заменяют сверку Between domain operations и решение пользователя.

## Решение пользователя и запрос Artifacts — 2026-11-18

### X-READ — OPEN, граница ожидания уточнена пользователем 2026-11-22

Собственные Source operands/semantics уже предъявлены в source-closure-operands-2026-11-22.md: historical witnesses с finalization evidence, полные captures v1, object/collection bodies и required format dependencies с exact correlation. Source проверяет relations/closure; не читает чужое storage, не управляет holders и не запускает Artifacts.

| Недостающая гарантия/контракт | Владелец | Что ожидает |
|---|---|---|
| Exact materialized BLOB/SQL_ROWS Input/Output/Error, physical integrity и completeness transport | Artifacts | Привязка owning результатов к Source public inputs/collector; предложенные read_verified signatures не accepted |
| Read authority/issuer, protection исходного набора и непрерывное retention до target acquisition | Publication infrastructure совместно с Artifacts | Authority/evidence mapping; physical read lifetime не равен retention lifetime |
| Полный перечислимый исходный набор и его consistency/version/correlation | Concrete producer ещё не назначен; назначение через координатора | Способ получения достаточного materialized input без hidden IO или неутверждённого DAG loop |
| Mapping owning результатов в пять proof-входов и collector, original occurrences и ошибки incomplete input | Source после предъявления owning типов | Окончательная интеграционная дельта Source; отсутствие переданного объекта не даёт MISSING_BODY |

Не ожидают X-READ: собственные pure validation, normalization/union/subset, occurrence mapping, revision arithmetic, POJO rules и архитектурные контракты других независимых частей. Их собственные OPEN устраняет Source, не внешний владелец. X-READ не является общим запретом продолжать АР-2…АР-6 и не prerequisite Time/Lifecycle nodes. Полный dependent public runtime нельзя объявить готовым до закрытия owning цепочки.

### Рекомендация по защите раскрытия closure — вариант 1

2026-11-18: пользователь поручил зафиксировать первый вариант как рекомендацию для согласования с Artifacts: **удерживать исходный набор целиком на время раскрытия зависимостей**. Это не подтверждение готового API, не приёмка интеграции и не выбор нового транзитивного retention graph.

До первого чтения действует защита исходного набора публикации/preparation, покрывающего все зависимости, которые Source вправе использовать. Набор может быть шире точного результата; его состав не становится семантическим closure автоматически. Source получает подтверждённое основание использования набора, а не один root ref. Проверка наличия holder только в начале недостаточна: concurrent release/GC не должны снимать защиту до окончания раскрытия либо безопасного приобретения следующего удержания.

Source вычисляет точный closure под этой защитой. Затем через согласованный маршрут приобретается удержание полного результата; лишь после подтверждения этого удержания допускается завершить временную защиту раскрытия. Source не освобождает исходное удержание самой публикации. При финальной публикации target retention закрепляется атомарно с publication по выбранному варианту А. Окно без защиты между этапами запрещено; разрешение прямых междоменных calls из этой последовательности не следует.

Для нескольких captures, включая исторические, могут потребоваться несколько исходных удерживаемых наборов. Их совокупное покрытие и lifetime должны быть подтверждены; текущая публикация не доказывает наличие исторических dependencies. SourceCaptureRef/finalized capture сам по себе не удостоверяет действующий hold. При неподтверждённом покрытии или недоступной зависимости подготовка не завершается успехом; latest fallback запрещён, exact error mapping подлежит согласованию без выдумывания нового кода.

Вопрос Artifacts: какой existing контракт фиксирует защиту исходного набора от release/GC на всё раскрытие и позволяет приобрести удержание результата без окна, с cancellation/restart/cleanup? Сначала проверяются existing POJO/API. Собственная проверка Source: состав и срок удержания finalized capture и соответствие этому покрытию. До подтверждения обеих частей gate OPEN. Новый граф транзитивных retention-связей ради Source не проектируется; чужие домены и код этим решением не меняются.

### Статус запроса и выбранная граница публикации

Пользователь подтвердил существование домена Artifacts и разрешил запрос его контрактов. Адресный запрос отправлен в видимый чат **Artifacts** (`01a1ea09-2ab4-7f71-9d96-7a29d70269d7`); сначала требуется аудит existing/proposed POJO/errors/API, без дублей. Ответ пока не принят. Старые записи о неизвестном владельце/чате Artifacts ниже исторические.

Зафиксировано ранее выбранное пользователем направление **А**: DAG → публичная Source preparation → DAG → publication. Source вычисляет и проверяет собственный closure; финальная публикация и target retention должны быть атомарны через согласованную общую infrastructure boundary. Прямой Snapshot → Source check_coverage/collect_for_adoption/adopt пользователь признал некорректным: это отклонённый маршрут, а не ожидаемое исключение DAG. Старые S1/S2/spec scoped traces не разрешают такую реализацию; требуется адресная согласованная замена без утраты атомарности. Сам вариант А не является готовым API и не назначает новые DAG-ноды.

Распределение требований: Source — proof/closure semantics; Artifacts — защита catalog/body от GC и durable holders/pins; Publication — transaction/capability/rollback/recovery; Snapshot/Publication — граница атомарного закрепления target retention с публикацией; DAG — порядок публичных вызовов и передача результатов. Конкретное разделение binding между Artifacts и Publication должен подтвердить owning ответ, не расположение Python-папок.

Запрошены exact imports/Input/Result/Error, защита roots при раскрытии closure, удержание между read и publication без окна GC, admission evidence связи proof/closure с публикуемыми данными, restart/cancellation/unknown outcome и ограничения task/thread/connection. Concurrent DAG invocations и внутренние compute workers рассматриваются отдельно. До подтверждения нельзя выдавать read result за retention authority либо маскировать междоменную операцию инфраструктурной dependency. Новые DTO, transaction owner и holder engine не вводятся. Интеграционный gate остаётся OPEN; реализация чужого домена в Source scope не входит.

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

### INT-SOURCE-READ-LIFETIME — SUPERSEDED / HISTORICAL

Снято как актуальное требование: Source не открывает/заимствует storage read scope. Все записи этого раздела ниже — история исследования, не OPEN задача и не условие возврата. Текущая внешняя зависимость — X-READ materialized transport/authority/protection/producer binding, EXTERNAL / DEFERRED. Physical read lifetime остаётся у owning reader, не constructor dependency Source.

#### Совместное уточнение конкурентности — 2026-11-17

Требование пользователя: различать конкурентность DAG и внутренний параллелизм доменной операции; выбирать scope policy только с учётом обоих уровней и совместного решения владельцев. Проверенный runtime DAG запускает invocations через asyncio.create_task с лимитом workers; PythonNodeExecutor напрямую await-ит node.execute. Внутри materialize существующий ChunkComputePool использует ThreadPoolExecutor/run_in_executor. Наличие одного уровня не разрешает передачу scope на другой.

Source требует: изоляция mutable request/diagnostics между конкурентными вызовами; явно определённая принадлежность scope task/thread/connection; согласованность exact reads; отсутствие implicit передачи живого scope в workers; определённое завершение workers/cleanup при cancellation до выдачи результата. Не требовать однопоточного DAG. Immutable вычислительные данные могут передаваться workers без authority на storage.

Варианты для совместной оценки, не принятые решения:

1. Public Source entry требует unbound context и получает собственный read lifetime. Внутренние workers вычисляют по immutable captured данным. Нужен существующий либо owning-уточнённый публичный unbound отказ; private _require_unbound не подходит.
2. Явно согласованный borrowed scope только в одной owning task для атомарной внутренней композиции; workers не заимствуют scope. Нужно подтвердить допустимость DAG-маршрута, видимость uncommitted данных и provisional смысл результата. Это не автоматическое разрешение для scope-free public API.
3. Если worker действительно нужен storage read: отдельный owning read contract с connection allocation и evidence одной требуемой версии. Независимые транзакции сами по себе не гарантируют общий snapshot; shared live scope не передаётся без подтверждённого механизма.

Владельцы: DAG — execution/context/cancellation; Source — public entry и собственные pure checks; Snapshot/publication — capability/transaction/connection lifetime; Artifacts — binding policy и physical read/GC coordination. Перед предложением новых контрактов каждый проверяет existing POJO/errors/API и сообщает exact imports, статусы accepted/proposed и недостающую дельту, без зеркал и placeholders. Общее решение должно содержать caller trace для обоих уровней конкурентности, отказ при недопустимом scope и проверки cleanup/изоляции/версии. Отдельный ответ одного владельца не закрывает gate.

Полученный ответ Snapshot подтвердил существующий механизм read lifetime и cleanup, но не архитектурный допуск borrowed scope. Static evidence не объявляется тестами. Более ранние записи ожидания ниже исторические; теперь предмет уточнения — совместная политика по указанным требованиям.

2026-11-17: запрос отправлен в существующий видимый чат **SNAPSHOT** (`01a1a0c5-931c-77a0-96a5-cb5b6ca6766f`). Обязательный первый шаг владельца — аудит existing POJO/errors/scopes/methods без дублей, затем подтверждение актуального контракта. Попросили отделить Snapshot/publication ownership от неподтверждённой Artifacts части и не создавать исключение DAG. Статус: ответ ожидается; более ранняя запись «отправка не заявляется» ниже описывает состояние до этой отправки.

Владельцы подтверждения: Snapshot/publication (CommitReadScope и lifetime) и Artifacts (SqliteArtifactScope binding); Source владеет требованиями своей public boundary. Проверено 2026-11-16: existing `SqliteArtifactScope.read_scope()` открывает/закрывает scope и bind/reset либо заимствует existing binding; `SqlitePublicationCommitStore.read_scope(existing_scope=None)` предоставляет concrete lifecycle. Новая инфраструктура Source не требуется на основании одного отсутствующего constructor binding в плане.

Точный запрос: подтвердить применение этого existing read lifetime к пяти scope-free public Source proof operations; допускается ли inherited binding на этой границе или нужен owning публичный способ отказа до IO; кто гарантирует same registry/task, cleanup при failure/cancellation и допустимость композиции по INT-DAG-SCOPED. Source не вызывает private `_require_unbound`, не добавляет свой commit owner и не принимает решение за владельцев. Условие возврата: актуальные exact imports/methods и согласованный call trace с обеими lifetime ветвями либо явным запретом borrowed ветви. До ответа durable constructor signatures остаются OPEN. Запрос зафиксирован, отправка и ответ не заявляются. Pure request validation и собственный provenance design этим не блокируются.

### INT-DAG-SCOPED — REJECTED ROUTE / HISTORICAL

Прямой Snapshot/Publication → Source adoption отклонён; shared transaction/internal method не дают исключения из запрета. Старое согласование scoped вызова не ожидается и не является prerequisite ядра. Ни adopt, ни collect_for_adoption, ни SourceAdoptionPreflight не возвращаются. Новая междоменная цепочка идёт через координатора по выбранному варианту А; следующие прежние формулировки этого раздела не действуют.

Владельцы: пользователь/владелец правил DAG и Snapshot; Source предоставляет точный контракт своих calls. Зависимость: §5 source-pack-s1-s2-contract.md содержит Snapshot→Source check_coverage/collect_for_adoption/adopt при абсолютном запрете прямых междоменных calls. Акт проверял только public calls, чего недостаточно. Затронутый срез — S1/S2 scoped integration; независимые Source invariants не блокируются. Условие закрытия: явное решение по допустимости, согласованный ограниченный перечень calls/effects/transaction ownership и синхронизация normative rules/design/акта. Если composition запрещена — совместимый маршрут предъявляют владельцы, без самостоятельного изменения Source порядка/транзакции. Запрос подготовлен в §5; отправка владельцам и ответ не заявляются.

### Дополнение INT-WRITER / INT-DAG — authoritative phase boundary (OPEN)

Snapshot/Artifacts-publication должны подтвердить exact reader/guard фазы мира и атомарность с переходом gameplay, typed refusal и включение Source changes в Snapshot-owned apply. Source-owned pregame apply/recover ограничения перечислены в source-core-mutation-contract.md §8.1. Условие возврата: согласованы phase authority/serialization/refusal и сценарии concurrent gameplay start, terminal replay после старта и запрет нового pregame attempt после старта. Source не создаёт второй commit owner; неизвестный phase отказ не подменяется proof error. Это детализация существующих долгов, не задание реализовать внешнюю инфраструктуру.

### Дополнение INT-ARTIFACTS-RETENTION: usage/prune boundary

Основной план §GC ревизий относит reachability к sourceUsage, выполнение explicit prune — к revisionPrune. Exact accepted typed binding этих участников с Source root/Artifact holders не предъявлен. Владельца конкретного usage/prune implementation уточнить при возврате к интеграции, не назначать им Source по умолчанию. Условие возврата: typed preview/confirm контракт, authoritative repeat check под согласованным scope, latest protection и отсутствие окна с concurrent capture/holds. Pure Source models не импортируют holders; bool free в caller input не заменяет evidence. Подробный разбор — [границы ядра](source-core-capture-prune-configuration.md#2-prune-не-присваивать-source-чужой-reachability).

### Evidence terminal registration

Проверено чтением кода 2026-11-15: [OperationRecord](../../backend/app/dataModel/artifacts/lifecycle/operation/record.py) допускает в terminal SnapshotApplyResult, PackActivationResult, GameplayStarted, OperationCancelled либо None. SourceMutationApplied/SourceMutationRefused не зарегистрированы. Сами Source outcomes пока proposals; отсутствие регистрации не основание самостоятельно менять shared union.

Точный Source design — [mutation contract §8.1–8.2](source-core-mutation-contract.md). Пока интеграция открыта, нельзя объявлять Source mutation/recovery runtime готовыми или сохранять outcomes через обходной ledger. Pure revision и архитектура ядра продолжаются независимо.

## Границы записей

Актуальная привязка каждого внешнего долга к классу Source и отделение собственной незавершённой работы — [матрица ответственности, §5](source-core-responsibility-matrix.md#5-выход-проверки), актуализация 2026-11-22. Request validation, pure algorithms, собственные revision/candidate/prune contracts, POJO predicates и configuration lifecycle не объявляются заблокированными целиком из-за X-READ/foreign writer. Исторические scoped/adoption упоминания в реестре не разрешают отозванный маршрут; текущий X-READ описан в source-closure-operands-2026-11-22.md.

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
