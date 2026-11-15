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

### Дополнение INT-ARTIFACTS-RETENTION: usage/prune boundary

Основной план §GC ревизий относит reachability к sourceUsage, выполнение explicit prune — к revisionPrune. Exact accepted typed binding этих участников с Source root/Artifact holders не предъявлен. Владельца конкретного usage/prune implementation уточнить при возврате к интеграции, не назначать им Source по умолчанию. Условие возврата: typed preview/confirm контракт, authoritative repeat check под согласованным scope, latest protection и отсутствие окна с concurrent capture/holds. Pure Source models не импортируют holders; bool free в caller input не заменяет evidence. Подробный разбор — [границы ядра](source-core-capture-prune-configuration.md#2-prune-не-присваивать-source-чужой-reachability).

### Evidence terminal registration

Проверено чтением кода 2026-11-15: [OperationRecord](../../backend/app/dataModel/artifacts/lifecycle/operation/record.py) допускает в terminal SnapshotApplyResult, PackActivationResult, GameplayStarted, OperationCancelled либо None. SourceMutationApplied/SourceMutationRefused не зарегистрированы. Сами Source outcomes пока proposals; отсутствие регистрации не основание самостоятельно менять shared union.

Точный Source design — [mutation contract §8.1–8.2](source-core-mutation-contract.md). Пока интеграция открыта, нельзя объявлять Source mutation/recovery runtime готовыми или сохранять outcomes через обходной ledger. Pure revision и архитектура ядра продолжаются независимо.

## Границы записей

glossary_ref и morph_hydrology_role выведены пользователем из scope текущего Source-плана: не превращать их в новые задания Source или условия приёмки независимого ядра. Вопрос Hydrology уже записан в GEO. Все поля и алгоритмы других доменов остаются у их владельцев.

Точные public mutation/recovery signatures, Source error roster delta и pure checker contracts — собственная архитектурная работа Source, не внешний техдолг. Их неполнота должна быть показана в архитектурных документах, а не скрыта этим реестром.
